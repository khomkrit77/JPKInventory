"""Local accounts and revocable, expiring cookie sessions."""
import hashlib
import hmac
import os
import re
import secrets
import time


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def check_password(password, encoded):
    return hmac.compare_digest(password_hash(password, encoded.split(':')[0]), encoded)


def validate_password(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 256 or not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
        raise ValueError('Password must be 8–256 characters and contain letters and numbers')


def temporary_password():
    return 'Aa7' + secrets.token_urlsafe(12)


class Auth:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS accounts (
                  id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                  password TEXT NOT NULL, role TEXT NOT NULL, permission TEXT NOT NULL,
                  active INTEGER NOT NULL, must_change INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                  token TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                  expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS login_attempts (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
            ''')
            db.execute('BEGIN IMMEDIATE')
            # Never recreate a deleted account or reset a password on restart.
            if not db.execute('SELECT 1 FROM accounts LIMIT 1').fetchone():
                password = os.environ.get('ADMIN_PASSWORD', 'JpkAdmin2026')
                validate_password(password)
                db.execute('INSERT INTO accounts VALUES (?,?,?,?,?,?,?)',
                           (secrets.token_hex(16), 'admin', password_hash(password), 'admin', 'read/write', 1, 1))

    @staticmethod
    def public(row):
        return dict(zip(('id', 'username', 'role', 'permission', 'active', 'mustChange'), row))

    def user(self, token):
        with self.store.connect() as db:
            row = db.execute('SELECT a.id,username,role,permission,active,must_change FROM accounts a JOIN sessions s ON a.id=s.account_id WHERE s.token=? AND s.expires>? AND active=1', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            return self.public(row) if row else None

    def login(self, body, address):
        username, password = body.get('username', ''), body.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 256:
            raise ValueError('Invalid credentials')
        key = address
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            attempt = db.execute('SELECT count,expires FROM login_attempts WHERE key=?', (key,)).fetchone()
            if attempt and attempt[0] >= 10 and attempt[1] > time.time():
                return None, 'Too many attempts; try again in 15 minutes'
            row = db.execute('SELECT id,password,active FROM accounts WHERE username=?', (username,)).fetchone()
            valid = check_password(password, row[1] if row else password_hash('DummyPassword123', '00'*16))
            if not row or not valid or not row[2]:
                count = attempt[0] + 1 if attempt and attempt[1] > time.time() else 1
                db.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)', (key, count, time.time()+900))
                return None, 'Invalid username or password'
            db.execute('DELETE FROM login_attempts WHERE key=?', (key,))
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row[0], time.time()+28800))
            return token, None

    def logout(self, token):
        with self.store.connect() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def change_password(self, user, body):
        validate_password(body.get('password'))
        with self.store.connect() as db:
            old = db.execute('SELECT password FROM accounts WHERE id=?', (user['id'],)).fetchone()[0]
            current = body.get('currentPassword', '')
            if not isinstance(current, str) or len(current)>256 or not check_password(current, old):
                raise ValueError('Current password is incorrect')
            if check_password(body['password'], old):
                raise ValueError('Choose a different password')
            db.execute('UPDATE accounts SET password=?,must_change=0 WHERE id=?', (password_hash(body['password']), user['id']))
            db.execute('DELETE FROM sessions WHERE account_id=?', (user['id'],))

    def accounts(self):
        with self.store.connect() as db:
            return [self.public(row) for row in db.execute('SELECT id,username,role,permission,active,must_change FROM accounts ORDER BY username')]

    def manage(self, method, account_id, body, actor):
        generated = None
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT role,active FROM accounts WHERE id=?', (account_id,)).fetchone() if account_id else None
            if account_id and not old:
                raise ValueError('Account not found')
            if method == 'DELETE':
                if account_id == actor['id']:
                    raise ValueError('You cannot delete your own account')
                db.execute('DELETE FROM accounts WHERE id=?', (account_id,))
            else:
                role = body.get('role', 'user')
                permission = body.get('permission', 'read-only')
                active = body.get('active', True)
                must_change = body.get('mustChange', False)
                if role not in ('admin', 'user') or permission not in ('read-only', 'read/write') or type(active) is not bool or type(must_change) is not bool:
                    raise ValueError('Invalid role, permission or status')
                if account_id == actor['id'] and (role != 'admin' or not active):
                    raise ValueError('You cannot disable or demote your own account')
                password = body.get('password')
                if body.get('generatePassword'):
                    password = generated = temporary_password()
                    must_change = True
                if password is not None:
                    validate_password(password)
                if not account_id:
                    username = body.get('username', '')
                    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}', username):
                        raise ValueError('Username must be 3–80 letters, numbers or _.@-')
                    if password is None:
                        raise ValueError('Password required')
                    account_id = secrets.token_hex(16)
                    db.execute('INSERT INTO accounts VALUES (?,?,?,?,?,?,?)', (account_id, username, password_hash(password), role, permission, active, must_change))
                else:
                    db.execute('UPDATE accounts SET role=?,permission=?,active=?,must_change=? WHERE id=?', (role, permission, active, must_change, account_id))
                    if password is not None:
                        db.execute('UPDATE accounts SET password=? WHERE id=?', (password_hash(password), account_id))
                    db.execute('DELETE FROM sessions WHERE account_id=?', (account_id,))
            if not db.execute("SELECT 1 FROM accounts WHERE role='admin' AND active=1").fetchone():
                raise ValueError('At least one active administrator is required')
        return {'temporaryPassword': generated}
