from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest import mock
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dashboard_retrieval_integration', ROOT / 'runtime/wiki_dashboard.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class RetrievalIntegrationTests(unittest.TestCase):
    def test_probe_cache_is_copied_and_force_refreshes(self):
        app = dashboard.Dashboard()
        result = {'version': 1, 'root': None, 'sqlite': {'state': 'not_applicable'}}
        with mock.patch.object(dashboard.retrieval_status_module, 'inspect_status', return_value=result) as probe:
            first = app.action('retrieval-status', {'expectedRoot': None})
            first['sqlite']['state'] = 'altered'
            self.assertEqual(app.action('retrieval-status', {})['sqlite']['state'], 'not_applicable')
            self.assertEqual(probe.call_count, 1)
            app.action('retrieval-status', {'force': True})
            self.assertEqual(probe.call_count, 2)

    def test_root_and_force_validation_precedes_io(self):
        app = dashboard.Dashboard()
        app.root = Path('/current')
        with mock.patch.object(dashboard.retrieval_status_module, 'inspect_status') as probe:
            for body in ({}, {'expectedRoot': '/other'}, {'expectedRoot': '/current', 'force': 'true'}):
                with self.assertRaises(ValueError):
                    app.action('retrieval-status', body)
            probe.assert_not_called()

    def test_cache_does_not_cross_roots(self):
        app = dashboard.Dashboard()
        with mock.patch.object(dashboard.retrieval_status_module, 'inspect_status', side_effect=lambda root, mode: {'root': str(root)}) as probe:
            for root in ('/first', '/second'):
                app.root = Path(root)
                self.assertEqual(app.action('retrieval-status', {'expectedRoot': root})['root'], root)
            self.assertEqual(probe.call_count, 2)

    def test_probe_does_not_hold_chat_lock_and_drops_changed_root(self):
        app = dashboard.Dashboard()
        app.root = Path('/first')
        entered, finish = threading.Event(), threading.Event()
        errors = []
        def probe(root, mode):
            entered.set()
            finish.wait(3)
            return {'root': str(root)}
        def run():
            try:
                app.action('retrieval-status', {'expectedRoot': '/first'})
            except ValueError as exc:
                errors.append(str(exc))
        with mock.patch.object(dashboard.retrieval_status_module, 'inspect_status', side_effect=probe):
            thread = threading.Thread(target=run)
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(app.lock.acquire(blocking=False))
                app.root = Path('/second')
                app.lock.release()
            finally:
                finish.set()
                thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsNone(app.retrieval_status_cache)

    def test_http_status_keeps_token_and_origin_guards(self):
        app = dashboard.Dashboard()
        server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        server.app = app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        def post(headers):
            return request.urlopen(request.Request(origin + '/api/retrieval-status', data=b'{}', headers={'Content-Type': 'application/json', **headers}), timeout=3)
        try:
            with mock.patch.object(dashboard.retrieval_status_module, 'inspect_status', return_value={'root': None, 'version': 1}) as probe:
                for headers in ({'Origin': origin}, {'Origin': 'https://other.example', 'X-Dashboard-Token': app.token}):
                    with self.assertRaises(error.HTTPError) as caught:
                        post(headers)
                    self.assertEqual(caught.exception.code, 403)
                probe.assert_not_called()
                with post({'Origin': origin, 'X-Dashboard-Token': app.token}) as response:
                    self.assertEqual(json.load(response)['version'], 1)
                probe.assert_called_once_with(None, 'wiki')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    unittest.main()
