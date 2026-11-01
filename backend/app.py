"""Same-origin JSON API and allowlisted static assets, served by Gunicorn."""
import json
import logging
import mimetypes
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from .store import Store, Conflict

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 8 * 1024 * 1024

def create_app(db_path=None):
    store = Store(db_path or os.environ.get('DATABASE_PATH', '/data/inventory.sqlite3'))
    def app(environ, start_response):
        def respond(status, payload, content_type='application/json; charset=utf-8'):
            body = json.dumps(payload, ensure_ascii=False).encode() if content_type.startswith('application/json') else payload
            start_response(status, [('Content-Type', content_type), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'SAMEORIGIN'), ('Referrer-Policy', 'strict-origin-when-cross-origin')])
            return [b'' if environ['REQUEST_METHOD'] == 'HEAD' else body]
        path, method = environ.get('PATH_INFO', '/'), environ['REQUEST_METHOD']
        try:
            if path == '/api/health' and method == 'GET':
                store.read()
                return respond('200 OK', {'status': 'ok', 'database': 'sqlite', 'schema': 1})
            if path in ('/api/state', '/api/import'):
                if method == 'GET' and path == '/api/state':
                    return respond('200 OK', store.read())
                if method not in ('PUT', 'POST') or (path == '/api/state' and method != 'PUT') or (path == '/api/import' and method != 'POST'):
                    return respond('405 Method Not Allowed', {'error': 'Method not allowed'})
                # JSON-only + same-origin protects writes against cross-site browser requests.
                origin = environ.get('HTTP_ORIGIN')
                if origin and urlsplit(origin).netloc != environ.get('HTTP_HOST'):
                    return respond('403 Forbidden', {'error': 'Cross-origin write denied'})
                if environ.get('HTTP_SEC_FETCH_SITE') == 'cross-site':
                    return respond('403 Forbidden', {'error': 'Cross-site write denied'})
                if environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                    return respond('415 Unsupported Media Type', {'error': 'JSON required'})
                length = int(environ.get('CONTENT_LENGTH') or 0)
                if not 0 < length <= MAX_BODY:
                    return respond('413 Content Too Large', {'error': 'Request must be 1 byte to 8 MiB'})
                body = json.loads(environ['wsgi.input'].read(length))
                if not isinstance(body, dict):
                    raise ValueError('Invalid request object')
                return respond('200 OK', store.write(body.get('data'), body.get('revision'), merge=path == '/api/import'))
            if method not in ('GET', 'HEAD'):
                return respond('405 Method Not Allowed', {'error': 'Method not allowed'})
            allowed = {'/', '/index.html', '/src/app.js', '/src/storage.js', '/src/data.js', '/src/styles.css'}
            if path not in allowed:
                return respond('404 Not Found', {'error': 'Not found'})
            file = ROOT / ('index.html' if path == '/' else path.lstrip('/'))
            return respond('200 OK', file.read_bytes(), (mimetypes.guess_type(file.name)[0] or 'application/octet-stream') + '; charset=utf-8')
        except Conflict as exc:
            return respond('409 Conflict', {'error': str(exc)})
        except (ValueError, TypeError, KeyError, sqlite3.IntegrityError) as exc:
            return respond('400 Bad Request', {'error': str(exc)})
        except Exception:
            logging.exception('Inventory request failed')
            return respond('503 Service Unavailable', {'error': 'Database unavailable; changes were not saved'})
    return app
