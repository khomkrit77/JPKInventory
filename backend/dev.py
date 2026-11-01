"""Local development only. Production uses Gunicorn."""
from wsgiref.simple_server import make_server
from .app import create_app
if __name__ == '__main__':
    with make_server('127.0.0.1', 8084, create_app()) as server:
        print('Development: http://127.0.0.1:8084', flush=True)
        server.serve_forever()
