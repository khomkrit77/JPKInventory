import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ProjectTests(unittest.TestCase):
    def test_production_build_contains_only_web_assets(self):
        spec = importlib.util.spec_from_file_location('build', ROOT / 'scripts/build.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.build()
        self.assertEqual((ROOT / 'dist/index.html').read_bytes(), (ROOT / 'index.html').read_bytes())
        for name in ['app.js', 'data.js', 'storage.js', 'styles.css']:
            self.assertEqual((ROOT / 'dist/src' / name).read_bytes(), (ROOT / 'src' / name).read_bytes())
        self.assertFalse((ROOT / 'dist/.env').exists())
        self.assertFalse((ROOT / 'dist/scripts').exists())

    def test_entrypoint_local_asset_references(self):
        import re
        html = (ROOT / 'index.html').read_text()
        for path in re.findall(r'(?:src|href)="([^\"]+)"', html):
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertIn('lang="th"', html)

if __name__ == '__main__':
    unittest.main()
