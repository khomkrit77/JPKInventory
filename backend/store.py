"""Transactional SQLite inventory store. No database is created at import time."""
import copy
import datetime as dt
import json
import re
import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path

COLLECTIONS = ('sites', 'users', 'devices', 'services', 'issues')
DEFAULT_SITES = [
    {'id': 'HQ', 'name': 'ลาดพร้าว', 'detail': 'สำนักงานใหญ่ · ศูนย์กลางระบบไอที'},
    {'id': 'AKM', 'name': 'เอกมัย', 'detail': 'สำนักงานสาขาเอกมัย'},
    {'id': 'RYT', 'name': 'รัชโยธิน', 'detail': 'สำนักงานสาขารัชโยธิน'},
    {'id': 'RST', 'name': 'รังสิต', 'detail': 'สำนักงานสาขารังสิต'},
]

class Conflict(Exception):
    pass


def validate(raw):
    if not isinstance(raw, dict) or raw.get('version') not in (1, 2):
        raise ValueError('Unsupported inventory version')
    data = copy.deepcopy(raw)
    data['version'] = 2
    for key, default in [('sites', DEFAULT_SITES), ('services', []), ('issues', [])]:
        data.setdefault(key, copy.deepcopy(default))
    for key in COLLECTIONS:
        if not isinstance(data.get(key), list) or len(data[key]) > 10000:
            raise ValueError(f'Invalid collection: {key}')
    ids = set()
    def strings(item, fields, limit=10000):
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or len(item[k]) > limit for k in fields):
            raise ValueError('Invalid text fields: ' + ', '.join(fields))
    for key in COLLECTIONS:
        for row in data[key]:
            strings(row, ['id'], 128)
            if not row['id'] or (key != 'sites' and row['id'] in ids):
                raise ValueError('Duplicate or empty ID')
            if key != 'sites':
                ids.add(row['id'])
    site_ids = {s['id'] for s in data['sites']}
    if len(site_ids) != len(data['sites']) or 'HQ' not in site_ids:
        raise ValueError('Duplicate sites or missing HQ')
    for s in data['sites']:
        strings(s, ['name'])
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{1,11}', s['id']) or not s['name'].strip():
            raise ValueError('Invalid site')
    user_ids = {u['id'] for u in data['users']}
    device_ids = {d['id'] for d in data['devices']}
    service_ids = {s['id'] for s in data['services']}
    for u in data['users']:
        u.setdefault('phone', '')
        u.setdefault('notes', '')
        strings(u, ['name', 'department', 'site', 'contact', 'phone', 'notes'])
        if not u['name'].strip() or not u['department'].strip() or u['site'] not in site_ids:
            raise ValueError('Invalid user name, department or site')
    hosts = set()
    def date(value, required=False):
        if value == '' and not required:
            return
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('Invalid date')
        dt.date.fromisoformat(value)
    for d in data['devices']:
        d.setdefault('customType', '')
        d.setdefault('antivirusActive', None)
        strings(d, ['hostname', 'type', 'site', 'ip', 'mac', 'os', 'startMA', 'endMA', 'ownerId', 'model', 'notes', 'customType'])
        if d['type'] not in ('server', 'pc', 'notebook', 'nas', 'router', 'other') or d['site'] not in site_ids:
            raise ValueError('Invalid device type/site')
        if not d['hostname'].strip() or d['hostname'].lower() in hosts:
            raise ValueError('Empty or duplicate hostname')
        hosts.add(d['hostname'].lower())
        # Match the browser IPv4 validator, including legacy zero-padded octets.
        if not re.fullmatch(r'(\d{1,3}\.){3}\d{1,3}', d['ip']) or any(int(n) > 255 for n in d['ip'].split('.')):
            raise ValueError('Invalid IPv4')
        if d['mac'] and not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}', d['mac']):
            raise ValueError('Invalid MAC address')
        if d['ownerId'] and d['ownerId'] not in user_ids:
            raise ValueError('Unknown device owner')
        if d['type'] in ('server', 'nas') and d['site'] != 'HQ':
            raise ValueError('Server/NAS must be at HQ')
        if d['type'] == 'other' and not d['customType'].strip():
            raise ValueError('Missing custom type')
        if d['antivirusActive'] not in (None, 'yes', 'no'):
            raise ValueError('Invalid antivirus status')
        date(d['startMA']); date(d['endMA'])
        if d['startMA'] and d['endMA'] and d['endMA'] < d['startMA']:
            raise ValueError('Invalid MA date range')
        if not isinstance(d.get('folders'), list):
            raise ValueError('Invalid folders')
        for f in d['folders']:
            strings(f, ['name', 'permission'])
            if not f['name'].strip() or f['permission'] not in ('Read', 'Write', 'Read/Write'):
                raise ValueError('Invalid folder permission')
    for s in data['services']:
        strings(s, ['name'])
        if not s['name'].strip():
            raise ValueError('Empty service name')
    for i in data['issues']:
        strings(i, ['occurredOn', 'resolvedOn', 'targetKind', 'targetId', 'targetName', 'reporterKind', 'reporterId', 'reporterName', 'notes'])
        date(i['occurredOn'], True); date(i['resolvedOn'])
        if i['resolvedOn'] and i['resolvedOn'] < i['occurredOn']:
            raise ValueError('Invalid resolution date')
        if i['targetKind'] not in ('device', 'service', 'other') or (i['targetKind'] == 'device' and i['targetId'] not in device_ids) or (i['targetKind'] == 'service' and i['targetId'] not in service_ids) or (i['targetKind'] == 'other' and not i['targetName'].strip()):
            raise ValueError('Invalid issue target')
        if i['reporterKind'] not in ('user', 'other') or (i['reporterKind'] == 'user' and i['reporterId'] not in user_ids) or (i['reporterKind'] == 'other' and not i['reporterName'].strip()) or not i['notes'].strip():
            raise ValueError('Invalid issue reporter/notes')
    return data


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise RuntimeError('Database schema is newer than this application')
            if version == 0:
                db.executescript('''
                    BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, extra TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, site TEXT NOT NULL REFERENCES sites(id), payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, site TEXT NOT NULL REFERENCES sites(id), owner_id TEXT REFERENCES users(id), payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS services (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS issues (id TEXT PRIMARY KEY, device_id TEXT REFERENCES devices(id), service_id TEXT REFERENCES services(id), reporter_id TEXT REFERENCES users(id), payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS history (revision INTEGER PRIMARY KEY, saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, payload TEXT NOT NULL);
                    INSERT OR IGNORE INTO metadata VALUES (1, 0, '{"version":2}');
                    PRAGMA user_version=1;
                    COMMIT;
                ''')
            if not db.execute('SELECT 1 FROM sites LIMIT 1').fetchone() and db.execute('SELECT revision FROM metadata').fetchone()[0] == 0:
                for s in DEFAULT_SITES:
                    db.execute('INSERT OR IGNORE INTO sites VALUES (?,?)', (s['id'], json.dumps(s, ensure_ascii=False)))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    def _read(self, db):
        revision, extra = db.execute('SELECT revision,extra FROM metadata WHERE id=1').fetchone()
        data = json.loads(extra)
        for key in COLLECTIONS:
            data[key] = [json.loads(row[0]) for row in db.execute(f'SELECT payload FROM {key} ORDER BY rowid')]
        return {'revision': revision, 'data': data}

    def read(self):
        with self.connect() as db:
            db.execute('BEGIN')
            return self._read(db)

    def write(self, raw, revision, merge=False, allow_delete=True):
        incoming = validate(raw)
        if type(revision) is not int or revision < 0:
            raise ValueError('Invalid revision')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = self._read(db)
            if previous['revision'] != revision:
                raise Conflict('ข้อมูลบนเซิร์ฟเวอร์เปลี่ยนแล้ว กรุณาคัดลอกข้อมูลในฟอร์ม แล้วโหลดหน้าใหม่ก่อนบันทึก')
            if not allow_delete and not merge:
                for key in COLLECTIONS:
                    ids = {row['id'] for row in incoming[key]}
                    if any(row['id'] not in ids for row in previous['data'][key]):
                        raise PermissionError('Only administrators can delete inventory records')
            data = incoming
            if merge:
                data = copy.deepcopy(previous['data'])
                for key in COLLECTIONS:
                    existing = {x['id']: x for x in data[key]}
                    for item in incoming[key]:
                        if item['id'] in existing and item != existing[item['id']]:
                            raise Conflict(f'Import conflict in {key}: {item["id"]}; existing data was preserved')
                        if item['id'] not in existing:
                            data[key].append(item)
                for key, value in incoming.items():
                    if key not in COLLECTIONS:
                        if key in data and data[key] != value:
                            raise Conflict(f'Import conflict in field: {key}')
                        data[key] = value
                data = validate(data)
            db.execute('INSERT INTO history(revision,payload) VALUES (?,?)', (revision, json.dumps(previous['data'], ensure_ascii=False)))
            for key in ('issues', 'devices', 'users', 'services', 'sites'):
                db.execute(f'DELETE FROM {key}')
            for key in COLLECTIONS:
                for row in data[key]:
                    payload = json.dumps(row, ensure_ascii=False)
                    if key == 'users':
                        db.execute('INSERT INTO users VALUES (?,?,?)', (row['id'], row['site'], payload))
                    elif key == 'devices':
                        db.execute('INSERT INTO devices VALUES (?,?,?,?)', (row['id'], row['site'], row['ownerId'] or None, payload))
                    elif key == 'issues':
                        db.execute('INSERT INTO issues VALUES (?,?,?,?,?)', (row['id'], row['targetId'] if row['targetKind'] == 'device' else None, row['targetId'] if row['targetKind'] == 'service' else None, row['reporterId'] if row['reporterKind'] == 'user' else None, payload))
                    else:
                        db.execute(f'INSERT INTO {key} VALUES (?,?)', (row['id'], payload))
            extra = {k: v for k, v in data.items() if k not in COLLECTIONS}
            db.execute('UPDATE metadata SET revision=?,extra=? WHERE id=1', (revision + 1, json.dumps(extra, ensure_ascii=False)))
            db.execute('DELETE FROM history WHERE revision < ?', (max(0, revision - 49),))
            return {'revision': revision + 1, 'data': data}

    def backup(self, destination):
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError('Backup destination already exists')
        with self.connect() as source, closing(sqlite3.connect(target)) as dest:
            source.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
