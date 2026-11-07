"""Complete delivery acceptance flow, using a disposable database and no network."""
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from backup import create_backup, verify_restore
from core import Store, now
from director_reports import build
from miniapp import MiniService, initialize
from reports import workbook, SECTIONS


class HandoffFlowTests(unittest.TestCase):
    def test_receipt_sale_payment_refund_stock_ledgers_and_bilingual_excel(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'DIRECTOR_DEBT_CHAT_ID':''}):
            path=Path(directory)/'test.sqlite3'
            s=Store(path);s.configure([10],[20,21]);initialize(path)
            self.addCleanup(s.db.close)
            api=MiniService(s,'fixture-token-no-network')
            today=now()[:10];sequence=0
            def write(cmd,data,uid=10,key=None):
                nonlocal sequence
                sequence+=1
                return api.write(uid,key or f'handoff-flow-{sequence:04}',cmd,data)['id']
            with s.db:
                warehouse=s.add('points',name='Warehouse')
                showcase=s.add('points',name='Showcase',kind='vitrina')
                product=s.product(10,'Acceptance tyre','150.50')
                client=s.client(20,'Own acceptance customer','+998901234567','','')
                supplier=s.supplier_save(10,'Acceptance supplier')
                s.receive(20,product,supplier,'100.25',[{'point':warehouse,'qty':6},{'point':showcase,'qty':4}],'Fixture',today,'USD')
                s.transfer(10,product,warehouse,showcase,2,'Acceptance transfer')
            def stock():return {r['point']:r['qty'] for r in s.rows('SELECT point,qty FROM stock WHERE product=?',(product,))}
            self.assertEqual(stock(),{warehouse:4,showcase:6})
            write('manager_record',dict(manager=20,kind='fund',amount='100.25'))
            sale_data=dict(client=client,point=warehouse,items=[dict(product=product,qty=1,price='150.50',point=warehouse),dict(product=product,qty=2,price='150.50',point=showcase)],paid='50.25',payment='card')
            sale=write('sell',sale_data,20,'handoff-sale-same-001')
            self.assertEqual(write('sell',sale_data,20,'handoff-sale-same-001'),sale)
            self.assertEqual(stock(),{warehouse:3,showcase:4})
            payment=dict(sale=sale,amount='100.25',payment='bank transfer',expected_paid='5025')
            paid=write('collect_debt',payment,20,'handoff-pay-same-0001')
            self.assertEqual(write('collect_debt',payment,20,'handoff-pay-same-0001'),paid)
            self.assertEqual(s.one('sales',sale)['paid'],15050)
            self.assertEqual(s.debts(20)[0]['debt'],30100)
            with s.db:s.supplier_pay(20,supplier,'100.25','Supplier settlement',today,'USD',20,'transfer')
            write('cancel_sale',dict(sale=sale,reason='Acceptance full return',settlement=True,expected_paid=15050))
            self.assertEqual(stock(),{warehouse:4,showcase:6})
            refund=s.rows('SELECT * FROM refunds WHERE sale=?',(sale,))[0]
            self.assertEqual(refund['amount'],15050)
            self.assertEqual(s.one('sales',sale)['paid'],15050)
            write('manager_assign_refund',dict(refund=refund['id'],manager=20,note='Actual refund payer verified'))
            active=write('sell',dict(client=client,point=showcase,items=[dict(product=product,qty=2,price='150.50')],paid='100',payment='cash'),20)
            with s.db:
                lot=s.rows('SELECT id FROM inventory_lots WHERE product=? AND point=? AND receipt IS NOT NULL AND qty>0',(product,warehouse))[0]['id']
                s.supplier_return(10,lot,1,'Acceptance supplier return',today)
            self.assertEqual(stock(),{warehouse:3,showcase:4})
            self.assertEqual(s.suppliers(10)['balances'][0]['balance'],80200)
            self.assertEqual(s.debts(20)[0]['debt'],20100)
            self.assertEqual(s.manager_account(10,20)['balances'][0]['balance'],10000)
            write('manager_accept_cash',dict(manager=20,amount='100',note='Director accepted actual receipt'))
            write('manager_close_day',dict(manager=20,date=today,note='Acceptance reconciliation'))
            self.assertEqual(s.manager_account(10,20)['balances'][0]['balance'],0)
            self.assertEqual(s.rows('PRAGMA integrity_check'),[{'integrity_check':'ok'}])
            self.assertEqual(s.rows('PRAGMA foreign_key_check'),[])
            for lang in ('uz','ru'):
                data=build(s,10,dict(start=today,end=today,categories='sales,payments,debts,stock,suppliers,receipts,managers'))
                wb=load_workbook(io.BytesIO(workbook(data,lang)))
                for section in ('sales','payments','refunds','stock','supplier_entries','supplier_balances','manager_entries','manager_balances'):
                    sheet=wb[SECTIONS[section][lang=='ru'][:31]]
                    self.assertGreater(sheet.max_row,1,section)
                values=lambda section:[cell.value for row in wb[SECTIONS[section][lang=='ru'][:31]].iter_rows(min_row=2) for cell in row]
                self.assertIn(802,values('supplier_balances'))
                self.assertIn(150.5,values('refunds'))
                self.assertIn(201,values('current_debts'))
                self.assertEqual(data['current_debts'][0]['debt'],20100)
                self.assertEqual(sum(row['qty'] for row in data['stock']),7)
            # Another employee's sale must never enter an employee's export.
            with s.db:
                other_product=s.product(10,'Other private product','99')
                s.move(21,other_product,warehouse,2,'in','Fixture')
                other_client=s.client(21,'Other private customer','+998901234568','','')
                s.order(21,other_client,[dict(product=other_product,qty=1,price='99')],point=warehouse,payment='cash')
            write('report',dict(start=today,end=today,section='sales'),20)
            queued=[json.loads(row['payload']) for row in s.rows('SELECT payload FROM outbox WHERE chat=20')]
            report=next(row for row in reversed(queued) if 'document' in row)
            wb=load_workbook(io.BytesIO(base64.b64decode(report['document'])))
            visible=' '.join(str(cell.value) for sheet in wb for row in sheet for cell in row)
            self.assertNotIn('Other private customer',visible)
            self.assertNotIn('Other private product',visible)
            self.assertIn('Own acceptance customer',visible)
            backup=create_backup(path,Path(directory)/'backups',verify=True)
            counts=verify_restore(backup)
            self.assertEqual(counts['sales'],3)
            self.assertEqual(counts['refunds'],1)
            self.assertEqual(s.one('sales',active)['paid'],10000)
            s.db.close()
