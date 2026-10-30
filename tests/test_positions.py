"""Regression tests for the two-role staff model."""
import unittest
import test_staff as fixtures
from staff import permissions,PERMISSIONS

class RoleTests(unittest.TestCase):
    setUp=fixtures.StaffTests.setUp
    tearDown=fixtures.StaffTests.tearDown
    invite=fixtures.StaffTests.invite
    join=fixtures.StaffTests.join

    def test_director_invitation_survives_restart(self):
        invite=self.service.write(10,'director-invite-01','staff_invite',{'label':'Director','role':'director'})['id']
        self.join(invite['url']);self.s.configure([10],[20])
        self.assertEqual(self.s.user(100)['role'],'director')
        self.assertTrue(self.access.team(100))

    def test_existing_employee_role_and_demotion_survive_restart(self):
        self.service.write(10,'promote-employee-01','staff_role',{'employee':20,'role':'director'})
        self.s.configure([10],[20]);self.assertEqual(self.s.user(20)['role'],'director')
        self.service.write(10,'demote-employee-001','staff_role',{'employee':20,'role':'employee'})
        self.s.configure([10],[20]);self.assertEqual(self.s.user(20)['role'],'employee')
        with self.assertRaises(PermissionError):self.access.team(20)

    def test_employee_cannot_escalate_or_create_arbitrary_role(self):
        for cmd,data in [('staff_role',{'employee':20,'role':'director'}),('staff_invite',{'label':'x','role':'director'})]:
            with self.assertRaises(PermissionError):self.service.write(20,'denied-0000-'+cmd,cmd,data)
        with self.assertRaises(ValueError):self.access.assign_role(10,20,'Warehouse manager')
        self.assertEqual(self.s.user(20)['role'],'employee')

    def test_self_guard_and_reserved_director_seat(self):
        for cmd,data in [('staff_role',{'employee':10,'role':'employee'}),('staff_set',{'employee':10,'active':False})]:
            with self.assertRaisesRegex(ValueError,'staff_self'):self.service.write(10,'self-guard-0000-'+cmd,cmd,data)
        invite=self.service.write(10,'reserved-director-1','staff_invite',{'label':'Director','role':'director'})['id']
        self.service.write(10,'reserved-director-2','staff_invite',{'label':'Third director','role':'director'})
        with self.assertRaisesRegex(ValueError,'director_limit'):self.access.assign_role(10,20,'director')
        self.service.write(10,'cancel-director-01','staff_cancel_invite',{'invite':invite['invite_id']})
        self.service.write(10,'promote-after-0001','staff_role',{'employee':20,'role':'director'})
        self.service.write(10,'disable-other-dir1','staff_set',{'employee':20,'active':False})
        self.s.configure([10],[20])
        with self.assertRaises(PermissionError):self.s.user(20)
        self.assertTrue(self.s.user(10)['active'])

    def test_legacy_custom_positions_ignored(self):
        with self.s.db:
            ref=self.s.add('positions',name='Old role',permissions='[]')
            self.s.add('staff_access',user_id=20,active=1,position_id=ref)
        self.assertEqual(set(permissions(self.s,20)),set(PERMISSIONS))
        self.service.write(20,'startwork-legacy1','startwork',{})
        for cmd in ['position_save','staff_position']:
            with self.assertRaises(ValueError):self.service.write(10,'removed-0000-'+cmd,cmd,{})

    def test_unlimited_employees_default_employee(self):
        for i in range(8):self.join(self.invite(str(i))['url'],100+i,i+1)
        self.s.configure([10],[20]);team=self.access.team(10)
        self.assertEqual(sum(p['role']=='employee' for p in team['employees']),9)
        self.assertIsNone(team['limit']);self.assertNotIn('positions',team)

    def test_attendance_employee_only(self):
        self.assertNotIn('attendance',permissions(self.s,10))
        self.assertIn('attendance',permissions(self.s,20))
        for cmd,data in [('startwork',{}),('endwork',{'report':'x'})]:
            with self.assertRaises(PermissionError):self.service.write(10,'director-day-0000-'+cmd,cmd,data)
        self.service.write(20,'employee-day-start1','startwork',{})
        self.service.write(20,'employee-day-end001','endwork',{'report':'Done'})
        self.assertEqual(self.s.rows('SELECT actor FROM shifts'),[{'actor':20}])
        labels=[b['text'] for row in self.bot.keyboard(10)['keyboard'] for b in row]
        from i18n import label
        self.assertNotIn(label('startwork','uz'),labels)

    def test_three_configured_directors_and_fourth_rejected(self):
        self.s.configure([10, 30, 40], [20])
        self.assertEqual(sum(u['role']=='director' for u in self.s.rows('SELECT * FROM users WHERE active=1')),3)
        with self.assertRaisesRegex(ValueError,'director_limit'):
            self.access.assign_role(10,20,'director')
        with self.assertRaises(ValueError):
            self.s.configure([10,30,40,50],[20])

    def test_third_director_promotion_survives_restart(self):
        self.s.configure([10,30],[20])
        with self.s.db:
            self.access.assign_role(10,20,'director')
        self.s.configure([10,30],[20])
        self.assertEqual(self.s.user(20)['role'],'director')
        with self.assertRaisesRegex(ValueError,'director_limit'):
            self.access.invite(10,'Fourth director','topshinalar_test_bot','director')
