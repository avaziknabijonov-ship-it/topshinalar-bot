import tempfile
import unittest
from pathlib import Path
from core import Store, now
from miniapp import MiniService, initialize
from test_miniapp import TOKEN


class ProductValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'db'
        self.s = Store(self.path)
        self.s.configure([10], [20])
        initialize(self.path)
        self.api = MiniService(self.s, TOKEN)
        self.n = 0
        with self.s.db:
            for u in (10, 20):
                self.s.set_contact_phone(u, '+9989055500' + str(u))
            self.point = self.s.add('points', name='Sklad')

    def tearDown(self):
        self.s.db.close()
        self.temp.cleanup()

    def write(self, uid, cmd, data):
        self.n += 1
        return self.api.write(uid, 'product-check-%04d-abcdefgh' % self.n, cmd, data)['id']

    def new(self, **extra):
        data = {'name': 'Michelin', 'brand': 'Michelin', 'size': '315/80 R22.5', 'price': '100'}
        data.update(extra)
        return self.write(10, 'product', data)

    def test_brand_and_size_are_saved_with_the_product(self):
        ref = self.new()
        row = self.s.one('products', ref)
        self.assertEqual((row['brand'], row['size'], row['price']), ('Michelin', '315/80 R22.5', 10000))

    def test_duplicate_is_rejected_even_with_case_and_spacing_differences(self):
        self.new()
        for variant in ({}, {'name': ' michelin ', 'brand': 'MICHELIN', 'size': '315/80  r22.5'}):
            with self.assertRaisesRegex(ValueError, 'product_exists'):
                self.new(**variant)
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)

    def test_employee_income_product_cannot_duplicate_either(self):
        self.new()
        with self.assertRaisesRegex(ValueError, 'product_exists'):
            self.write(20, 'income_product', {'name': 'Michelin', 'brand': 'Michelin', 'size': '315/80 R22.5', 'price': '1'})

    def test_different_size_or_brand_is_a_different_product(self):
        self.new()
        self.new(size='295/80 R22.5')
        self.new(brand='Bridgestone')
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM products').fetchone()[0], 3)

    def test_edit_cannot_turn_a_product_into_a_duplicate_but_can_keep_itself(self):
        first = self.new()
        second = self.new(size='295/80 R22.5')
        with self.assertRaisesRegex(ValueError, 'product_exists'):
            self.write(10, 'editproduct', {'product': second, 'name': 'Michelin', 'brand': 'Michelin', 'size': '315/80 R22.5', 'price': '100'})
        self.write(10, 'editproduct', {'product': first, 'name': 'Michelin', 'brand': 'Michelin', 'size': '315/80 R22.5', 'price': '120'})
        self.assertEqual(self.s.one('products', first)['price'], 12000)

    def test_archived_product_does_not_block_a_new_one(self):
        first = self.new()
        with self.s.db:
            self.s.db.execute('UPDATE products SET active=0 WHERE id=?', (first,))
        self.new()

    def test_zero_negative_and_missing_price_are_rejected(self):
        for price in ('0', '-5', '', 'abc'):
            with self.assertRaises(ValueError, msg=price):
                self.new(price=price)

    def test_overlong_text_is_rejected(self):
        for field, size in (('name', 201), ('brand', 151), ('size', 151)):
            with self.assertRaisesRegex(ValueError, '^(product_text|text)$'):
                self.new(**{field: 'x' * size})

    def test_failed_creation_leaves_no_partial_product_or_stock(self):
        with self.assertRaises(ValueError):
            self.write(10, 'product', {'name': 'Q', 'price': '5', 'point': self.point, 'qty': '-3'})
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_opening_stock_still_works_with_new_product(self):
        ref = self.write(10, 'product', {'name': 'Stocked', 'price': '5', 'point': self.point, 'qty': '4'})
        self.assertEqual(self.s.db.execute('SELECT qty FROM stock WHERE product=? AND point=?', (ref, self.point)).fetchone()[0], 4)


if __name__ == '__main__':
    unittest.main()
