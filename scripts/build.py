"""Assemble production static assets without third-party dependencies."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build():
    import runpy
    runpy.run_path(str(ROOT / 'scripts/make_preview.py'))['generate']()
    target = ROOT / 'dist'
    target.mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'index.html', target / 'index.html')
    shutil.copytree(ROOT / 'src', target / 'src', dirs_exist_ok=True)
    print(f'Production build ready: {target}')

if __name__ == '__main__':
    build()
