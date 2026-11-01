"""Dependency-free local preview. All paths resolve relative to the project."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_env():
    path = ROOT / '.env'
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                values[k.strip()] = v.strip().strip('\"\'')
    return values

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import unquote, urlparse
        path = Path(unquote(urlparse(self.path).path))
        if any(part.startswith('.') for part in path.parts) or any(part in {'tests', 'scripts', '__pycache__'} for part in path.parts) or path.name in {'Dockerfile', 'docker-compose.yml', 'nginx.conf'}:
            self.send_error(404)
            return
        super().do_GET()

    def list_directory(self, path):
        self.send_error(404)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

if __name__ == '__main__':
    import os
    env = read_env()
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=os.environ.get('HOST', env.get('HOST', '127.0.0.1')))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', env.get('PORT', '5173'))))
    parser.add_argument('--dist', action='store_true')
    args = parser.parse_args()
    directory = ROOT / 'dist' if args.dist else ROOT
    if not (directory / 'index.html').exists():
        parser.error('Run python3 scripts/build.py first')
    handler = functools.partial(Handler, directory=str(directory))
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f'JPK Inventory: http://{args.host}:{args.port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
