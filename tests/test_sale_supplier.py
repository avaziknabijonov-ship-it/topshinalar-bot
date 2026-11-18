from pathlib import Path
import tempfile
import unittest
from core import Store, now
from miniapp import MiniService, initialize
from test_miniapp import TOKEN


class SaleSupplierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.s = Store(self.path)
        self.s.configure([10], [20, 21])
        initialize(self.path)
        self.api = MiniService(self.s, TOKEN)
        with self.s.db:
            for person in (10, 20, 21):
                self.s.set_contact_phone(person, '+9989055500' + str(person))
            self.point = self.s.add('points', name='Sklad')
            self.product = self.s.product(10, 'Tyre 315/80 R22.5', '20')
            self.client = self.s.client(20, 'Customer', '+998901234567', '', '')
            self.a = self.s.supplier_save(10, 'Alpha', '+998901234567', '')
            self.b = self.s.supplier_save(10, 'Beta', '+998907654321', '')
        self.today = now()[:10]
        # Same tyre from two suppliers; Alpha arrived first, so it is the automatic (oldest) choice.
        self.receive(self.a, 5)
        self.receive(self.b, 5)

    def tearDown(self):
        self.s.db.close()
        self.temp.cleanup()

    def receive(self, supplier, qty):
        with self.s.db:
            return self.s.receive(20, self.product, supplier, '10.00', [{'point': self.point, 'qty': qty}], 'Invoice', self.today, 'USD')

    def sell(self, qty, supplier=None, key='sale-supplier-0001', uid=20, **extra):
        item = {'product': self.product, 'qty': qty, 'price': '20', 'point': self.point}
        if supplier is not None:
            item['supplier'] = supplier
        return self.api.write(uid, key, 'sell', {'client': self.client, 'point': self.point, 'items': [item], 'paid': '0', 'payment': 'naqd', **extra})['id']

    def lot_qty(self, supplier):
        return self.s.db.execute('SELECT COALESCE(SUM(l.qty),0) FROM inventory_lots l JOIN receipts r ON r.id=l.receipt WHERE r.supplier=? AND l.product=?', (supplier, self.product)).fetchone()[0]

    def stock(self):
        return self.s.db.execute('SELECT qty FROM stock WHERE product=? AND point=?', (self.product, self.point)).fetchone()[0]

    def allocated_suppliers(self, sale):
        return {r['supplier']: r['qty'] for r in self.s.rows('SELECT r.supplier,SUM(a.qty) qty FROM sale_allocations a JOIN sale_items i ON i.id=a.item JOIN inventory_lots l ON l.id=a.lot JOIN receipts r ON r.id=l.receipt WHERE i.sale=? GROUP BY r.supplier', (sale,))}

    def test_chosen_supplier_is_the_only_one_sold_from(self):
        sale = self.sell(3, self.b)
        self.assertEqual(self.allocated_suppliers(sale), {self.b: 3})
        self.assertEqual((self.lot_qty(self.a), self.lot_qty(self.b), self.stock()), (5, 2, 7))

    def test_without_a_choice_the_oldest_batch_is_used_as_before(self):
        sale = self.sell(3)
        self.assertEqual(self.allocated_suppliers(sale), {self.a: 3})
        sale = self.sell(4, key='sale-supplier-0002')
        self.assertEqual(self.allocated_suppliers(sale), {self.a: 2, self.b: 2})
        self.assertEqual((self.lot_qty(self.a), self.lot_qty(self.b), self.stock()), (0, 3, 3))

    def test_blank_supplier_means_automatic(self):
        sale = self.sell(2, '')
        self.assertEqual(self.allocated_suppliers(sale), {self.a: 2})

    def test_not_enough_stock_from_the_chosen_supplier_changes_nothing(self):
        before = (self.lot_qty(self.a), self.lot_qty(self.b), self.stock(), self.s.db.execute('SELECT COUNT(*) FROM sales').fetchone()[0])
        with self.assertRaisesRegex(ValueError, 'supplier_stock'):
            self.sell(6, self.a)
        after = (self.lot_qty(self.a), self.lot_qty(self.b), self.stock(), self.s.db.execute('SELECT COUNT(*) FROM sales').fetchone()[0])
        self.assertEqual(before, after)
        # The same quantity is fine automatically (10 in total), so the error is about the chosen supplier only.
        self.sell(6, key='sale-supplier-0003')

    def test_unknown_or_invalid_supplier_is_rejected_without_side_effects(self):
        for bad in (9999, 0, -1, 'abc', True):
            with self.assertRaises(ValueError):
                self.sell(1, bad, key=f'sale-bad-supplier-{abs(hash(str(bad))) % 10**6:06d}')
        self.assertEqual((self.lot_qty(self.a), self.lot_qty(self.b), self.stock()), (5, 5, 10))
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM sales').fetchone()[0], 0)

    def test_repeating_the_same_request_does_not_sell_twice(self):
        first = self.sell(2, self.b, key='sale-idempotent-0001')
        second = self.sell(2, self.b, key='sale-idempotent-0001')
        self.assertEqual(first, second)
        self.assertEqual((self.lot_qty(self.b), self.stock()), (3, 8))

    def test_cancelling_returns_units_to_the_suppliers_batch(self):
        sale = self.sell(3, self.b)
        with self.s.db:
            self.s.cancel_sale(10, sale, 'mistake', False)
        self.assertEqual((self.lot_qty(self.a), self.lot_qty(self.b), self.stock()), (5, 5, 10))

    def test_catalog_lists_stock_by_supplier_for_each_point(self):
        self.sell(2, self.b)
        item = self.api.catalog(20)['items'][0]
        suppliers = {r['name']: r['qty'] for r in item['points'][0]['suppliers']}
        self.assertEqual(suppliers, {'Alpha': 5, 'Beta': 3})
        self.assertEqual(item['qty'], 8)

    def test_sale_history_names_the_supplier_for_the_seller_and_the_director(self):
        sale = self.sell(2, self.b)
        mine = [r for r in self.api.history(20, 'sales') if r['id'] == sale][0]
        self.assertEqual(mine['items'][0]['suppliers'], 'Beta')
        from employee_sales import history
        rows = history(self.s, 20, {})['items']
        self.assertEqual([i['suppliers'] for r in rows for i in r['items']], ['Beta'])

    def test_supplier_cost_data_is_not_exposed_to_sellers(self):
        item = self.api.catalog(20)['items'][0]
        for supplier in item['points'][0]['suppliers']:
            self.assertEqual(set(supplier), {'id', 'name', 'qty'})

    def test_quotes_ignore_a_supplier_field(self):
        ref = self.api.write(20, 'quote-supplier-0001', 'quote', {'client': self.client, 'items': [{'product': self.product, 'qty': 1, 'price': '20', 'supplier': self.b}], 'payment': 'naqd', 'fulfillment': 'pickup', 'exchange_rate': '1'})['id']
        self.assertTrue(ref)
        self.assertEqual((self.lot_qty(self.a), self.lot_qty(self.b), self.stock()), (5, 5, 10))


if __name__ == '__main__':
    unittest.main()
