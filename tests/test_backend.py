import copy
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from backend.app import create_app
from backend.store import Store, Conflict, DEFAULT_SITES


def sample():
    return {'version': 2, 'sites': copy.deepcopy(DEFAULT_SITES), 'users': [{'id': 'u1', 'name': 'ทดสอบ', 'department': 'IT', 'site': 'HQ', 'contact': '', 'phone': '', 'notes': ''}], 'devices': [{'id': 'd1', 'type': 'pc', 'hostname': 'HQ-PC-01', 'site': 'HQ', 'ip': '192.168.1.10', 'mac': '', 'os': '', 'startMA': '', 'endMA': '', 'ownerId': 'u1', 'model': '', 'notes': '', 'customType': '', 'antivirusActive': 'yes', 'folders': [{'name': 'Shared', 'permission': 'Read'}]}], 'services': [{'id': 's1', 'name': 'Email'}], 'issues': [{'id': 'i1', 'occurredOn': '2026-11-01', 'resolvedOn': '', 'targetKind': 'device', 'targetId': 'd1', 'targetName': 'HQ-PC-01', 'reporterKind': 'user', 'reporterId': 'u1', 'reporterName': 'ทดสอบ', 'notes': 'ทดสอบบันทึก'}]}

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'inventory.sqlite3'
        self.store = Store(self.path)
        self.app = create_app(self.path)
        self.cookie = ''
        self.request('POST', '/api/auth/login', {'username': 'admin', 'password': 'JpkAdmin2026'})
        self.request('POST', '/api/auth/password', {'currentPassword': 'JpkAdmin2026', 'password': 'ChangedAdmin123'})
        self.request('POST', '/api/auth/login', {'username': 'admin', 'password': 'ChangedAdmin123'})

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, method, path, value=None, **headers):
        body = json.dumps(value).encode() if value is not None else b''
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'HTTP_HOST': 'inventory.test:8084', 'HTTP_COOKIE': self.cookie, 'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(body)), 'wsgi.input': io.BytesIO(body), **headers}
        response = []
        payload = b''.join(self.app(env, lambda status, hdr: response.append((status, hdr))))
        for key, value in response[0][1]:
            if key == 'Set-Cookie':
                self.cookie = value.split(';')[0]
        return int(response[0][0].split()[0]), json.loads(payload)

    def test_all_collections_roundtrip_edit_delete_and_reopen(self):
        data = sample()
        result = self.store.write(data, 0)
        self.assertEqual(Store(self.path).read(), result)
        data['users'][0]['name'] = 'ชื่อใหม่'
        data['devices'][0]['notes'] = 'แก้ไข'
        data['sites'].append({'id': 'NEW', 'name': 'สาขาใหม่'})
        data['services'][0]['name'] = 'Mail'
        data['issues'][0]['resolvedOn'] = '2026-11-02'
        self.store.write(data, 1)
        self.assertEqual(self.store.read()['data'], data)
        data['issues'][0].update(reporterKind='other', reporterId='', reporterName='ชื่อใหม่')
        data['devices'][0]['ownerId'] = ''
        data['users'] = []
        self.store.write(data, 2)
        self.assertEqual(Store(self.path).read()['data']['users'], [])
        self.assertEqual(self.store.read()['data']['issues'][0]['reporterName'], 'ชื่อใหม่')
        data['issues'][0].update(targetKind='other', targetId='', targetName='HQ-PC-01')
        data['devices'] = []
        data['services'] = []
        data['sites'] = [data['sites'][0]]
        data['issues'] = []
        self.store.write(data, 3)
        self.assertEqual(Store(self.path).read()['data'], data)
        with self.store.connect() as db:
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute('SELECT count(*) FROM history').fetchone()[0], 4)

    def test_stale_revision_and_invalid_reference_preserve_database(self):
        result = self.store.write(sample(), 0)
        with self.assertRaises(Conflict):
            self.store.write(sample(), 0)
        broken = sample(); broken['devices'][0]['ownerId'] = 'missing'
        with self.assertRaises(ValueError):
            self.store.write(broken, 1)
        self.assertEqual(self.store.read(), result)
        broken = sample(); broken['devices'][0]['hostname'] = ''
        self.assertEqual(self.request('PUT', '/api/state', {'revision': 1, 'data': broken})[0], 400)
        self.assertEqual(self.store.read(), result)

    def test_legacy_import_merge_conflict_and_backup_restore(self):
        old = sample(); old['version'] = 1
        del old['users'][0]['phone']; del old['users'][0]['notes']
        del old['devices'][0]['customType']; del old['devices'][0]['antivirusActive']
        result = self.store.write(old, 0, merge=True)
        self.assertEqual(result['data']['users'][0]['phone'], '')
        other = sample(); other['users'][0]['name'] = 'conflicting'
        with self.assertRaises(Conflict):
            self.store.write(other, 1, merge=True)
        self.assertEqual(self.store.read(), result)
        target = Path(self.tmp.name) / 'backup.sqlite3'
        self.store.backup(target)
        self.assertEqual(Store(target).read(), result)
        with self.assertRaises(ValueError):
            self.store.backup(target)

    def test_api_validation_health_and_static_allowlist(self):
        self.assertEqual(self.request('GET', '/api/health')[1]['status'], 'ok')
        self.assertEqual(self.request('PUT', '/api/state', {'revision': 0, 'data': sample()})[0], 200)
        self.assertEqual(self.request('GET', '/api/state')[1]['data'], sample())
        self.assertEqual(self.request('PUT', '/api/state', {'revision': 0, 'data': sample()})[0], 409)
        self.assertEqual(self.request('PUT', '/api/state', {'revision': 1, 'data': sample()}, HTTP_ORIGIN='https://other.test')[0], 403)
        self.assertEqual(self.request('PUT', '/api/state', {'revision': 1, 'data': sample()}, CONTENT_TYPE='text/plain')[0], 415)
        for path in ['/.env', '/backend/app.py', '/data/inventory.sqlite3', '/src/../backend/app.py']:
            self.assertEqual(self.request('GET', path)[0], 404)
        self.assertEqual(self.request('POST', '/api/state', {})[0], 405)

    def test_migration_does_not_reset_existing_database(self):
        result = self.store.write(sample(), 0)
        for _ in range(3):
            self.assertEqual(Store(self.path).read(), result)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA user_version=99')
        with self.assertRaises(RuntimeError):
            Store(self.path)

    def test_concurrent_writers_and_restore_command(self):
        self.store.write(sample(), 0)
        def write_once(index):
            data = sample()
            data['users'][0]['notes'] = str(index)
            try:
                self.store.write(data, 1)
                return 'saved'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(write_once, range(2))), ['saved', 'conflict'])
        saved = self.store.read()
        target = Path(self.tmp.name) / 'restore-source.sqlite3'
        self.store.backup(target)
        self.store.write(sample(), saved['revision'])
        run = subprocess.run([sys.executable, '-m', 'backend.manage', 'restore', str(target)], env={**os.environ, 'DATABASE_PATH': str(self.path)}, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.store.read(), saved)
        self.assertEqual(len(list((Path(self.tmp.name) / 'backups').glob('before-restore-*'))), 1)
