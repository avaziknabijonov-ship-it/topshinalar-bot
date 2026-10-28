import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from core import Store
from bot import Bot
from miniapp import MiniService, initialize
from staff import StaffAccess


class StaffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'staff.sqlite3'
        self.s=Store(self.path)
        self.s.configure([10],[20])
        initialize(self.path)
        with self.s.db:self.s.db.execute("INSERT INTO meta VALUES('bot_username','example_staff_bot')")
        self.access=StaffAccess(self.s)
        self.bot=Bot(self.s)
        self.service=MiniService(self.s,'unit-test-secret-only')

    def tearDown(self):
        self.s.db.close();self.tmp.cleanup()

    def invite(self,label='New employee'):
        return self.service.write(10,'invite-'+str(time.time_ns()),'staff_invite',{'label':label})['id']

    def join(self,url,uid=100,update=1):
        self.bot.process({'update_id':update,'message':{'from':{'id':uid,'first_name':'Aziz','last_name':'Aliyev'},'chat':{'id':uid,'type':'private'},'text':'/start '+url.split('start=')[1]}})

    def test_join_without_id_and_restart_keeps_access(self):
        invite=self.invite();self.join(invite['url'])
        self.assertEqual(self.s.user(100)['name'],'Aziz Aliyev')
        self.assertEqual(self.s.user(100)['role'],'employee')
        self.s.configure([10],[20])
        self.assertEqual(self.s.user(100)['active'],1)
        self.assertEqual(self.s.rows('SELECT status,joined_by FROM staff_invites'),[{'status':'used','joined_by':100}])
        messages=[json.loads(r['payload'])['text'] for r in self.s.rows('SELECT payload FROM outbox')]
        self.assertTrue(any('/app' in m for m in messages))
        # The stable invitation table does not store the bearer token in plaintext.
        token=invite['url'].split('?start=staff_',1)[1]
        self.assertNotIn(token,str(self.s.rows('SELECT * FROM staff_invites')))

    def test_single_use_and_update_replay(self):
        invite=self.invite();self.join(invite['url']);self.join(invite['url'])
        self.join(invite['url'],101,2)
        self.assertEqual(len(self.s.rows('SELECT * FROM staff_access')),1)
        with self.assertRaises(ValueError):self.s.user(101)

    def test_disable_enable_survives_legacy_environment_and_preserves_history(self):
        with self.s.db:client=self.s.client(20,'Client','+998901234567','','')
        self.service.write(10,'staff-disable-0001','staff_set',{'employee':20,'active':False})
        self.s.configure([10],[20])
        with self.assertRaises(PermissionError):self.s.user(20)
        self.assertEqual(self.s.one('clients',client)['owner'],20)
        with self.assertRaises(PermissionError):self.service.write(20,'client-disabled-01','client',{'name':'x','phone':'+998901234567'})
        self.service.write(10,'staff-enable-00001','staff_set',{'employee':20,'active':True})
        self.s.configure([10],[20])
        self.assertTrue(self.s.user(20)['active'])

    def test_employee_cannot_manage_or_view_team_or_choose_director_role(self):
        for cmd,data in [('staff_invite',{'label':'x'}),('staff_set',{'employee':10,'active':False}),('staff_cancel_invite',{'invite':1})]:
            with self.assertRaises(PermissionError):self.service.write(20,'forbidden-'+cmd,cmd,data)
        with self.assertRaises(PermissionError):self.access.team(20)
        with self.assertRaises(ValueError):self.service.write(10,'director-disable-1','staff_set',{'employee':10,'active':False})
        invite=self.service.write(10,'role-extra-field-1','staff_invite',{'label':'x','role':'director'})['id']
        self.join(invite['url'])
        self.assertEqual(self.s.user(100)['role'],'director')

    def test_capacity_reserves_pending_invites_and_cancel_frees_slot(self):
        invitations=[self.invite(str(i)) for i in range(3)]
        self.invite()
        self.assertIsNone(self.access.team(10)['limit'])
        self.service.write(10,'cancel-invite-001','staff_cancel_invite',{'invite':invitations[0]['invite_id']})
        self.invite('replacement')
        self.join(invitations[0]['url'])
        with self.assertRaises(ValueError):self.s.user(100)

    def test_expiry_and_revoked_inviter_cannot_join(self):
        invite=self.invite()
        with self.s.db:self.s.db.execute('UPDATE staff_invites SET expires=?',(int(time.time())-1,))
        self.join(invite['url'])
        with self.assertRaises(ValueError):self.s.user(100)
        invite=self.invite()
        self.s.configure([11],[20])
        self.join(invite['url'],101,2)
        with self.assertRaises(ValueError):self.s.user(101)

    def test_suspended_employee_cannot_reactivate_with_invitation(self):
        self.service.write(10,'disable-old-staff1','staff_set',{'employee':20,'active':False})
        invite=self.invite();self.join(invite['url'],20)
        with self.assertRaises(PermissionError):self.s.user(20)
        self.assertEqual(self.access.team(10)['invites'][0]['id'],invite['invite_id'])

    def test_invitation_is_private_chat_only(self):
        invite=self.invite()
        self.bot.process({'update_id':1,'message':{'from':{'id':100,'first_name':'x'},'chat':{'id':-100,'type':'group'},'text':'/start '+invite['url'].split('start=')[1]}})
        with self.assertRaises(ValueError):self.s.user(100)

    def test_invite_idempotency_and_atomic_race(self):
        a=self.service.write(10,'same-invite-key-01','staff_invite',{'label':'One'})
        b=self.service.write(10,'same-invite-key-01','staff_invite',{'label':'One'})
        self.assertEqual(a,b)
        with self.assertRaises(ValueError):self.service.write(10,'same-invite-key-01','staff_invite',{'label':'Other'})
        token=a['id']['url'].split('?start=staff_',1)[1]
        barrier=threading.Barrier(2);results=[]
        def accept(uid):
            store=Store(self.path)
            try:
                barrier.wait()
                with store.db:
                    store.db.execute('BEGIN IMMEDIATE')
                    StaffAccess(store).accept(token,uid,'Employee')
                results.append('joined')
            except ValueError:results.append('rejected')
            finally:store.db.close()
        threads=[threading.Thread(target=accept,args=(uid,)) for uid in (100,101)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10)
        self.assertCountEqual(results,['joined','rejected'])

    def test_reactivation_cannot_exceed_limit_or_accept_strings_as_boolean(self):
        self.s.configure([10],[20,21,22,23])
        self.service.write(10,'disable-employee20','staff_set',{'employee':20,'active':False})
        self.invite()
        self.service.write(10,'enable-full-staff1','staff_set',{'employee':20,'active':True})
        with self.assertRaisesRegex(ValueError,'staff_target'):self.service.write(10,'boolean-staff-0001','staff_set',{'employee':21,'active':'false'})
        self.assertTrue(self.s.user(21)['active'])

    def test_http_team_is_director_only_and_suspension_revokes_existing_login(self):
        from miniapp import MiniServer
        from test_miniapp import signed, TOKEN
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        server=MiniServer(('127.0.0.1',0),self.path,TOKEN)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,uid,data=None):
            headers={'X-Telegram-Init-Data':signed(uid),'Content-Type':'application/json','Idempotency-Key':'http-staff-disable-1'}
            return urlopen(Request(base+path,data=json.dumps(data).encode() if data else None,headers=headers),timeout=5)
        try:
            with self.assertRaises(HTTPError) as denied:request('/api/team',20)
            self.assertEqual(denied.exception.code,403)
            with request('/api/team',10) as response:self.assertIn(20,[u['id'] for u in json.load(response)['employees']])
            with request('/api/action',10,{'cmd':'staff_set','data':{'employee':20,'active':False}}) as response:self.assertTrue(json.load(response)['ok'])
            with self.assertRaises(HTTPError) as denied:request('/api/me',20)
            self.assertEqual(denied.exception.code,403)
        finally:
            server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':unittest.main()
