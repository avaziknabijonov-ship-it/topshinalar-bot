import io
import tempfile
import threading
import unittest
from pathlib import Path
from core import Store,now
from miniapp import MiniService,initialize
from openpyxl import load_workbook
from reports import workbook
import manager_money as mm
import director


class ManagerMoneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'money.sqlite3';self.s=Store(self.path);self.s.configure([10],[20,21]);initialize(self.path);self.api=MiniService(self.s,'test-token');self.today=now()[:10];self.seq=0
        with self.s.db:
            self.point=self.s.add('points',name='Warehouse');self.product=self.s.product(10,'Tire','125');self.s.move(20,self.product,self.point,100,'in','fixture');self.client=self.s.client(20,'Client','+998900000000','','')

    def tearDown(self):self.s.db.close();self.tmp.cleanup()

    def write(self,cmd,d,uid=10,key=None):
        self.seq+=1;return self.api.write(uid,key or f'manager-money-test-{self.seq:05}',cmd,d)['id']

    def sell(self,paid='100',method='cash',uid=20):
        return self.write('sell',dict(client=self.client,point=self.point,items=[dict(product=self.product,qty=1,price='125')],paid=paid,payment=method),uid)

    def balance(self,manager=20,currency='USD'):
        return next((r for r in self.s.manager_account(10,manager)['balances'] if r['currency']==currency),{'balance':0})

    def accept(self,amount='100',manager=20,date=None):return self.write('manager_accept_cash',dict(manager=manager,amount=amount,currency='USD',date=date or self.today,note='Physically accepted'))

    def close(self,date=None,manager=20):return self.write('manager_close_day',dict(manager=manager,date=date or self.today,note='Checked',))

    def test_all_payment_methods_actual_amount_and_client_debt_separate(self):
        for method in ('cash','card','bank transfer'):self.sell('10',method)
        self.sell('0')
        b=self.balance();self.assertEqual(b['received'],3000);self.assertEqual((b['received_cash'],b['received_card'],b['received_transfer']),(1000,1000,1000));self.assertEqual(b['balance'],3000)
        self.assertEqual(sum(r['debt'] for r in self.s.debts(10)),47000)
        self.assertEqual(len([r for r in self.s.manager_account(10)['entries'] if r['kind']=='sale_receipt']),3)
        self.assertEqual(self.s.rows('SELECT * FROM manager_entries'),[])

    def test_later_payment_belongs_to_collector_and_receipt_date(self):
        sale=self.sell('10')
        with self.s.db:self.s.db.execute("UPDATE sales SET created='2026-01-01T08:00:00+05:00' WHERE id=?",(sale,))
        self.write('pay',dict(sale=sale,amount='20',payment='card'),uid=10)
        self.assertEqual(self.balance(20)['received'],1000);self.assertEqual(self.balance(10)['received'],2000)
        data=director.read(self.api,10,'managers',{'start':self.today,'end':self.today})
        self.assertEqual(sum(r['amount'] for r in data['entries'] if r['source']=='payment'),3000)

    def test_pending_handover_does_not_reduce_balance_until_director_acceptance(self):
        self.sell();ref=self.write('manager_record',dict(manager=20,kind='return',amount='40',note='Handed over'),20)
        b=self.balance();self.assertEqual((b['balance'],b['pending_return'],b['returned']),(10000,4000,0))
        with self.assertRaises(PermissionError):self.write('manager_accept_return',{'entry':ref},20)
        self.write('manager_accept_return',{'entry':ref},key='accept-return-same-1');self.write('manager_accept_return',{'entry':ref},key='accept-return-same-1')
        b=self.balance();self.assertEqual((b['balance'],b['pending_return'],b['returned']),(6000,0,4000))
        with self.assertRaises(ValueError):self.write('manager_accept_return',{'entry':ref})
        self.assertTrue(self.s.rows("SELECT * FROM audit WHERE action='manager_handover_accepted'"))

    def test_rejection_keeps_debt_and_allows_correct_resubmission(self):
        self.sell();ref=self.write('manager_request_return',dict(manager=20,amount='100',note='Mistaken submission'),20)
        with self.assertRaises(PermissionError):self.write('manager_reject_return',dict(entry=ref,note='No'),20)
        self.write('manager_reject_return',dict(entry=ref,note='Cash not delivered'))
        self.assertEqual((self.balance()['balance'],self.balance()['pending_return']),(10000,0))
        with self.assertRaises(ValueError):self.write('manager_accept_return',dict(entry=ref))
        self.accept();self.assertEqual(self.balance()['balance'],0)

    def test_direct_cash_acceptance_once_and_overdraw_rollback(self):
        self.sell();data=dict(manager=20,amount='80',note='Received in cash desk',date=self.today)
        self.write('manager_accept_cash',data,key='accept-cash-same-001');self.write('manager_accept_cash',data,key='accept-cash-same-001')
        self.assertEqual(self.balance()['balance'],2000)
        before=self.s.rows('SELECT * FROM manager_entries')
        with self.assertRaises(ValueError):self.accept('21')
        self.assertEqual(before,self.s.rows('SELECT * FROM manager_entries'))

    def test_manual_received_fund_expense_and_currency_separation(self):
        self.write('manager_received',dict(manager=20,amount='12.50',currency='USD',note='Other verified receipt'))
        self.write('manager_record',dict(manager=20,kind='fund',amount='10'))
        self.write('manager_record',dict(manager=20,kind='expense',amount='2'),20)
        self.write('manager_received',dict(manager=20,amount='100000',currency='UZS',note='Legacy currency receipt'))
        self.assertEqual(self.balance()['balance'],2050);self.assertEqual(self.balance(currency='UZS')['balance'],10000000)
        for uid in (20,21):
            with self.assertRaises(PermissionError):self.write('manager_received',dict(manager=20,amount='1',note='No'),uid)
        with self.assertRaises(ValueError):self.write('manager_received',dict(manager=20,amount='1',note=''))

    def test_shift_end_does_not_close_financial_day_or_clear_manager_debt(self):
        self.sell()
        with self.s.db:self.s.start(20);self.s.end(20,'Completed work')
        self.assertEqual(self.balance()['balance'],10000)
        self.assertEqual(mm.days(self.s,10,self.today,self.today)[0]['day_status'],'open')
        with self.assertRaisesRegex(ValueError,'manager_day_unsettled'):self.close()
        self.accept();self.close()
        self.assertEqual(mm.days(self.s,10,self.today,self.today)[0]['day_status'],'closed')
        with self.assertRaisesRegex(ValueError,'manager_day_closed'):self.close()

    def test_prior_day_carry_blocks_close_and_historical_change_reopens(self):
        self.sell()
        with self.s.db:self.s.db.execute("UPDATE payments SET created='2026-01-01T08:00:00+05:00'")
        with self.assertRaisesRegex(ValueError,'manager_day_unsettled'):self.close()
        self.accept(date='2026-01-01');self.close(date='2026-01-01')
        self.assertEqual(mm.days(self.s,10,'2026-01-01','2026-01-01')[0]['day_status'],'closed')
        with self.s.db:self.s.db.execute("UPDATE users SET name='Renamed manager' WHERE id=20")
        self.write('manager_received',dict(manager=20,amount='1',date=self.today,note='Later day receipt'))
        self.assertEqual(mm.days(self.s,10,'2026-01-01','2026-01-01')[0]['day_status'],'closed')
        self.write('manager_received',dict(manager=20,amount='5',date='2026-01-01',note='Late recorded receipt'))
        self.assertEqual(mm.days(self.s,10,'2026-01-01','2026-01-01')[0]['day_status'],'reopened')
        self.accept('5',date='2026-01-01');self.close(date='2026-01-01')
        self.assertEqual(self.s.rows('SELECT COUNT(*) n FROM manager_day_closings')[0]['n'],2)

    def test_refund_payer_must_be_confirmed_and_not_inferred_from_cancel_actor(self):
        sale=self.sell()
        self.write('cancel_sale',dict(sale=sale,reason='Cancel',settlement=True,expected_paid=10000))
        self.assertEqual(self.balance()['balance'],10000)
        refund=self.s.rows('SELECT * FROM refunds')[0]['id']
        self.assertTrue(self.s.manager_account(10)['refund_review'])
        with self.assertRaises(ValueError):self.close()
        self.write('manager_assign_refund',dict(refund=refund,manager=20,note='Refund paid by collector'))
        self.assertEqual(self.balance()['balance'],0);self.assertEqual(self.balance()['refunds'],10000)
        self.close()
        with self.assertRaises(Exception):self.write('manager_assign_refund',dict(refund=refund,manager=21,note='Duplicate'))

    def test_company_pays_refund_collector_still_owes_collected_funds(self):
        sale=self.sell();self.write('cancel_sale',dict(sale=sale,reason='Cancel',settlement=True,expected_paid=10000));ref=self.s.rows('SELECT id FROM refunds')[0]['id']
        self.write('manager_assign_refund',dict(refund=ref,manager=None,note='Company cash desk paid refund'))
        self.assertEqual(self.balance()['balance'],10000);self.assertFalse(self.s.manager_account(10)['refund_review'])
        self.accept();self.close()

    def test_director_collector_and_inactive_employee_can_be_settled(self):
        self.sell(uid=10);self.assertEqual(self.balance(10)['balance'],10000);self.accept(manager=10)
        self.sell()
        with self.s.db:self.s.db.execute('UPDATE users SET active=0 WHERE id=20')
        self.accept(manager=20);self.assertEqual(self.balance()['balance'],0)
        with self.assertRaises(PermissionError):self.s.manager_account(20)

    def test_migration_preserves_old_returns_and_does_not_duplicate_historical_payments(self):
        self.sell()
        with self.s.db:self.s.add('manager_entries',manager=20,kind='return',amount=3000,currency='USD',actor=20,note='Old recorded return',date=self.today,created=now())
        before={t:self.s.rows('SELECT * FROM '+t) for t in ('payments','manager_entries','sales')}
        self.assertEqual(self.balance()['balance'],7000)
        for _ in range(2):
            s=Store(self.path)
            self.assertEqual(s.manager_account(10,20)['balances'][0]['balance'],7000)
            for table,data in before.items():self.assertEqual(s.rows('SELECT * FROM '+table),data)
            self.assertEqual(s.rows('SELECT * FROM manager_return_receipts'),[]);s.db.close()

    def test_concurrent_acceptance_cannot_double_spend_same_balance(self):
        self.sell();results=[]
        def run(key):
            s=Store(self.path)
            try:
                api=MiniService(s,'test');api.write(10,key,'manager_accept_cash',dict(manager=20,amount='60',note='Accepted'));results.append('ok')
            except ValueError:results.append('rejected')
            finally:s.db.close()
        ts=[threading.Thread(target=run,args=(f'parallel-receipt-{i:04}',)) for i in range(2)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertEqual(sorted(results),['ok','rejected']);self.assertEqual(self.balance()['balance'],4000)

    def test_legacy_currency_unknown_methods_and_future_date_validation(self):
        self.sell()
        with self.s.db:self.s.db.execute("UPDATE payments SET currency='UZS',method='historic custom'")
        b=self.balance(currency='UZS');self.assertEqual(b['balance'],10000);self.assertEqual(b['received_other'],10000)
        with self.assertRaises(ValueError):self.write('manager_received',dict(manager=20,amount='1',date='2999-01-01',note='Future'))
        with self.assertRaises(ValueError):self.close(date='2999-01-01')

    def test_restricted_reads_and_export_actual_receipts_and_cents(self):
        self.sell();self.sell(uid=21)
        self.assertEqual({r['manager'] for r in self.s.manager_account(20)['entries']},{20})
        with self.assertRaises(PermissionError):self.s.manager_account(20,21)
        with self.assertRaises(PermissionError):self.write('manager_close_day',dict(manager=20,date=self.today,note='No'),20)
        data=self.s.manager_account(10)
        wb=load_workbook(io.BytesIO(workbook({'manager_balances':data['balances'],'manager_entries':data['entries']})))
        ws=wb['Menejer pul saldosi'];headers=[c.value for c in ws[1]];col=headers.index('Qabul qilgan pul')+1
        self.assertEqual(ws.cell(2,col).value,100)
        self.assertIn('source_id',data['entries'][0])
