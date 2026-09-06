"""Transport and frontend-admission contracts independent of application code."""
import importlib.util
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.request import urlopen
from urllib.error import HTTPError
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_http.py'
spec = importlib.util.spec_from_file_location('dashboard_http_tests', SCRIPT)
http = importlib.util.module_from_spec(spec)
spec.loader.exec_module(http)


class PartialError(ValueError):
    payload = {}


class DashboardHttpTests(unittest.TestCase):
    def test_manifest_admits_only_declared_scripts_and_fixed_entries(self):
        assets = ROOT / '.agents/skills/llm-wiki-loop/dashboard'
        admitted = http.frontend_assets(assets)
        self.assertIn('/app.js', admitted)
        self.assertNotIn('/example.json', admitted)
        self.assertNotIn('/README.md', admitted)
        with self.assertRaises(TypeError):
            admitted['/new'] = ('new', 'text/plain')

    def test_unsafe_duplicate_missing_and_inline_scripts_fail(self):
        for declaration in ('', '<script src="./app.js" defer></script>', '<script>alert(1)</script>', '<script src="https://example.com/x.js" defer></script>',
                            '<script src="/../private.js" defer></script>', '<script src="/%2e%2e/x.js" defer></script>',
                            '<script src="/app.js"></script>', '<script src="/missing.js" defer></script>',
                            '<script src="/app.js" defer></script><script src="app.js" defer></script>'):
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'index.html').write_text(declaration)
                (root / 'style.css').write_text('')
                (root / 'app.js').write_text('')
                with self.assertRaises(ValueError):
                    http.frontend_assets(root)

    def test_every_production_script_is_served_with_same_bytes_and_csp(self):
        assets = ROOT / '.agents/skills/llm-wiki-loop/dashboard'
        handler = http.make_handler(asset_root=assets, document_payload=lambda *args: {},
                                    chat_not_found_error=LookupError, save_partial_error=PartialError,
                                    workflow_error=RuntimeError)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        server.app = SimpleNamespace()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            for route, (relative, mime) in http.frontend_assets(assets).items():
                with urlopen(base + route, timeout=3) as response:
                    self.assertEqual(response.read(), (assets / relative).read_bytes())
                    self.assertEqual(response.headers['Content-Type'], mime)
                    self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
            for route in ('/README.md', '/example.json', '/../SKILL.md', '/modules/not-declared.js'):
                with self.assertRaises(HTTPError) as caught:
                    urlopen(base + route, timeout=3)
                self.assertEqual(caught.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    unittest.main()
