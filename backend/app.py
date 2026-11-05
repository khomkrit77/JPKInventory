"""Same-origin JSON API and allowlisted static assets, served by Gunicorn."""
import json
import logging
import mimetypes
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from .store import Store, Conflict, COLLECTIONS
from .auth import Auth
from http.cookies import SimpleCookie

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 8 * 1024 * 1024

def create_app(db_path=None):
    store = Store(db_path or os.environ.get('DATABASE_PATH', '/data/inventory.sqlite3'))
    auth = Auth(store)
    def app(environ, start_response):
        extra_headers = []
        def respond(status, payload, content_type='application/json; charset=utf-8'):
            body = json.dumps(payload, ensure_ascii=False).encode() if content_type.startswith('application/json') else payload
            start_response(status, [('Content-Type', content_type), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'SAMEORIGIN'), ('Referrer-Policy', 'strict-origin-when-cross-origin')] + extra_headers)
            return [b'' if environ['REQUEST_METHOD'] == 'HEAD' else body]
        path, method = environ.get('PATH_INFO', '/'), environ['REQUEST_METHOD']
        try:
            if path == '/api/health' and method == 'GET':
                store.read()
                return respond('200 OK', {'status': 'ok', 'database': 'sqlite', 'schema': 1})
            if path.startswith('/api/'):
                cookie = SimpleCookie()
                cookie.load(environ.get('HTTP_COOKIE', ''))
                token = cookie['jpk_session'].value if 'jpk_session' in cookie else ''
                user = auth.user(token)
                body = {}
                if method not in ('GET', 'HEAD'):
                    origin = environ.get('HTTP_ORIGIN')
                    if (origin and urlsplit(origin).netloc != environ.get('HTTP_HOST')) or environ.get('HTTP_SEC_FETCH_SITE') == 'cross-site':
                        return respond('403 Forbidden', {'error': 'Cross-origin write denied'})
                    if environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                        return respond('415 Unsupported Media Type', {'error': 'JSON required'})
                    length = int(environ.get('CONTENT_LENGTH') or 0)
                    if not 0 < length <= MAX_BODY:
                        return respond('413 Content Too Large', {'error': 'Request must be 1 byte to 8 MiB'})
                    body = json.loads(environ['wsgi.input'].read(length))
                    if not isinstance(body, dict):
                        raise ValueError('Invalid request object')
                secure = '; Secure' if environ.get('wsgi.url_scheme') == 'https' or os.environ.get('COOKIE_SECURE') == '1' else ''
                def session_cookie(value, age):
                    extra_headers.append(('Set-Cookie', f'jpk_session={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}' + secure))
                if path == '/api/auth/login' and method == 'POST':
                    new_token, error = auth.login(body, environ.get('REMOTE_ADDR', 'unknown'))
                    if error:
                        return respond('401 Unauthorized', {'error': error})
                    session_cookie(new_token, 28800)
                    return respond('200 OK', {'user': auth.user(new_token)})
                if not user:
                    return respond('401 Unauthorized', {'error': 'Please sign in'})
                if path == '/api/auth/me' and method == 'GET':
                    return respond('200 OK', {'user': user})
                if path == '/api/auth/logout' and method == 'POST':
                    auth.logout(token)
                    session_cookie('', 0)
                    return respond('200 OK', {'ok': True})
                if path == '/api/auth/password' and method == 'POST':
                    auth.change_password(user, body)
                    session_cookie('', 0)
                    return respond('200 OK', {'ok': True})
                if user['mustChange']:
                    return respond('403 Forbidden', {'error': 'Change your password before continuing'})
                if path == '/api/accounts' or path.startswith('/api/accounts/'):
                    if user['role'] != 'admin':
                        return respond('403 Forbidden', {'error': 'Administrator access required'})
                    account_id = path.split('/api/accounts/')[1] if path != '/api/accounts' else None
                    if method == 'GET' and not account_id:
                        return respond('200 OK', {'users': auth.accounts()})
                    if (method == 'POST' and not account_id) or (method in ('PUT', 'DELETE') and account_id):
                        return respond('200 OK', auth.manage(method, account_id, body, user))
                    return respond('405 Method Not Allowed', {'error': 'Method not allowed'})
                if path in ('/api/state', '/api/import'):
                    if method == 'GET' and path == '/api/state':
                        return respond('200 OK', store.read())
                    if (path == '/api/state' and method != 'PUT') or (path == '/api/import' and method != 'POST'):
                        return respond('405 Method Not Allowed', {'error': 'Method not allowed'})
                    if user['role'] != 'admin':
                        if user['permission'] != 'read/write':
                            return respond('403 Forbidden', {'error': 'Read-only account: changes are not allowed'})
                    return respond('200 OK', store.write(body.get('data'), body.get('revision'), merge=path == '/api/import', allow_delete=user['role'] == 'admin'))
                return respond('404 Not Found', {'error': 'Not found'})
            if method not in ('GET', 'HEAD'):
                return respond('405 Method Not Allowed', {'error': 'Method not allowed'})
            allowed = {'/', '/index.html', '/src/app.js', '/src/storage.js', '/src/data.js', '/src/styles.css'}
            if path not in allowed:
                return respond('404 Not Found', {'error': 'Not found'})
            file = ROOT / ('index.html' if path == '/' else path.lstrip('/'))
            return respond('200 OK', file.read_bytes(), (mimetypes.guess_type(file.name)[0] or 'application/octet-stream') + '; charset=utf-8')
        except PermissionError as exc:
            return respond('403 Forbidden', {'error': str(exc)})
        except Conflict as exc:
            return respond('409 Conflict', {'error': str(exc)})
        except (ValueError, TypeError, KeyError, sqlite3.IntegrityError) as exc:
            return respond('400 Bad Request', {'error': str(exc)})
        except Exception:
            logging.exception('Inventory request failed')
            return respond('503 Service Unavailable', {'error': 'Database unavailable; changes were not saved'})
    return app
