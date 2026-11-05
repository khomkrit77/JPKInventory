import json
import io
import tempfile
import unittest
from pathlib import Path
from backend.app import create_app
from backend.auth import Auth, validate_password, check_password
from backend.store import Store
from tests.test_backend import sample


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'test.sqlite'
        self.app = create_app(self.path)
        self.cookie = ''

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, method, path, value=None, **headers):
        body = json.dumps(value).encode() if value is not None else b''
        env = {'REQUEST_METHOD':method,'PATH_INFO':path,'HTTP_HOST':'test','HTTP_COOKIE':self.cookie,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body), **headers}
        response=[]
        data=b''.join(self.app(env,lambda status,h:response.append((status,h))))
        for k,v in response[0][1]:
            if k=='Set-Cookie':
                self.cookie=v.split(';')[0]
                self.assertIn('HttpOnly',v)
                self.assertIn('SameSite=Strict',v)
        return int(response[0][0].split()[0]),json.loads(data)

    def login(self, username='admin', password='JpkAdmin2026'):
        return self.request('POST','/api/auth/login',{'username':username,'password':password})

    def admin(self):
        self.assertEqual(self.login()[0],200)
        self.assertEqual(self.request('POST','/api/auth/password',{'currentPassword':'JpkAdmin2026','password':'Changed123'})[0],200)
        self.assertEqual(self.login(password='Changed123')[0],200)

    def test_seed_password_gate_and_revocation(self):
        self.assertEqual(self.request('GET','/api/state')[0],401)
        self.assertEqual(self.login(password='wrong')[0],401)
        self.assertEqual(self.login()[1]['user']['mustChange'],1)
        self.assertEqual(self.request('GET','/api/state')[0],403)
        self.assertEqual(self.request('POST','/api/auth/password',{'currentPassword':'wrong','password':'NewPass123'})[0],400)
        token=self.cookie
        self.assertEqual(self.request('POST','/api/auth/password',{'currentPassword':'JpkAdmin2026','password':'NewPass123'})[0],200)
        self.cookie=token
        self.assertEqual(self.request('GET','/api/state')[0],401)
        self.app=create_app(self.path)
        self.assertEqual(self.login(password='JpkAdmin2026')[0],401)
        self.assertEqual(self.login(password='NewPass123')[0],200)
        self.assertEqual(self.request('GET','/api/state')[0],200)
        self.request('POST','/api/auth/logout',{})
        self.assertEqual(self.request('GET','/api/state')[0],401)

    def test_permissions_admin_actions_and_sessions(self):
        self.admin()
        admin_cookie=self.cookie
        body={'username':'reader','password':'Reader123','permission':'read-only'}
        self.assertEqual(self.request('POST','/api/accounts',body)[0],200)
        self.assertEqual(self.request('POST','/api/accounts',body)[0],400)
        users=self.request('GET','/api/accounts')[1]['users']
        self.assertNotIn('password',str(users))
        reader=next(u for u in users if u['username']=='reader')
        self.login('reader','Reader123')
        reader_cookie=self.cookie
        self.assertEqual(self.request('GET','/api/state')[0],200)
        self.assertEqual(self.request('PUT','/api/state',{'revision':0,'data':sample()})[0],403)
        self.assertEqual(self.request('POST','/api/import',{'revision':0,'data':sample()})[0],403)
        self.assertEqual(self.request('GET','/api/accounts')[0],403)
        self.cookie=admin_cookie
        self.assertEqual(self.request('PUT','/api/accounts/'+reader['id'],{'permission':'read/write'})[0],200)
        self.cookie=reader_cookie
        self.assertEqual(self.request('GET','/api/state')[0],401)
        self.login('reader','Reader123')
        self.assertEqual(self.request('PUT','/api/state',{'revision':0,'data':sample()})[0],200)
        data=sample();data['users'][0]['notes']='updated'
        self.assertEqual(self.request('PUT','/api/state',{'revision':1,'data':data})[0],200)
        data['issues']=[]
        self.assertEqual(self.request('PUT','/api/state',{'revision':2,'data':data})[0],403)
        reader_cookie=self.cookie
        self.cookie=admin_cookie
        self.assertEqual(self.request('DELETE','/api/accounts/'+reader['id'],{})[0],200)
        self.cookie=reader_cookie
        self.assertEqual(self.request('GET','/api/state')[0],401)

    def test_generation_status_last_admin_and_cross_origin(self):
        self.admin()
        self.assertEqual(self.request('POST','/api/accounts',{'username':'temp','generatePassword':True},HTTP_ORIGIN='https://evil.test')[0],403)
        status,result=self.request('POST','/api/accounts',{'username':'temp','generatePassword':True})
        self.assertEqual(status,200)
        password=result['temporaryPassword'];validate_password(password)
        users=self.request('GET','/api/accounts')[1]['users']
        admin=next(u for u in users if u['role']=='admin')
        temp=next(u for u in users if u['username']=='temp')
        self.assertEqual(self.request('DELETE','/api/accounts/'+admin['id'],{})[0],400)
        self.assertEqual(self.request('PUT','/api/accounts/'+admin['id'],{'role':'user'})[0],400)
        cookie=self.cookie
        self.login('temp',password)
        self.assertEqual(self.request('GET','/api/state')[0],403)
        self.cookie=cookie
        self.assertEqual(self.request('PUT','/api/accounts/'+temp['id'],{'active':False})[0],200)
        self.assertEqual(self.login('temp',password)[0],401)
        with Store(self.path).connect() as db:
            encoded=db.execute("SELECT password FROM accounts WHERE username='temp'").fetchone()[0]
            self.assertNotEqual(encoded,password)
            self.assertTrue(check_password(password,encoded))

    def test_password_policy_expiry_and_throttle(self):
        for password in ['short1','abcdefgh','12345678','a1'*129,None]:
            with self.assertRaises(ValueError):validate_password(password)
        self.admin()
        with Store(self.path).connect() as db:db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.request('GET','/api/state')[0],401)
        for _ in range(10):self.login(password='bad')
        self.assertIn('Too many',self.login(password='Changed123')[1]['error'])
