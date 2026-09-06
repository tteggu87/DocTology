from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
from urllib import request, error

SCRIPT = Path(__file__).resolve().parents[1] / '.agents/skills/llm-wiki-loop/scripts/wiki_dashboard.py'
spec = importlib.util.spec_from_file_location('dashboard_folder_picker_tests', SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class FolderPickerTests(unittest.TestCase):
    def test_macos_selection_preserves_unicode_and_never_passes_path_to_command(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory) / "한글 '폴더"
            selected.mkdir()
            with mock.patch.object(dashboard.sys, 'platform', 'darwin'), mock.patch.object(
                dashboard.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, str(selected) + '/\n', '')
            ) as run:
                self.assertEqual(dashboard.choose_workspace_folder(), {'cancelled': False, 'root': str(selected.resolve())})
            command = run.call_args.args[0]
            self.assertEqual(command[:2], ['/usr/bin/osascript', '-e'])
            self.assertIn('choose folder', command[2])
            self.assertNotIn(str(selected), command[2])
            self.assertFalse(run.call_args.kwargs.get('shell', False))
            self.assertEqual(run.call_args.kwargs['timeout'], 120)

    def test_cancel_returns_no_path(self):
        for platform in ('darwin', 'win32'):
            with self.subTest(platform=platform), mock.patch.object(dashboard.sys, 'platform', platform), mock.patch.object(
                dashboard.shutil, 'which', return_value='powershell.exe'
            ), mock.patch.object(dashboard.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '\n', '')):
                self.assertEqual(dashboard.choose_workspace_folder(), {'cancelled': True})

    def test_windows_uses_sta_native_folder_dialog_and_utf8_output(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(dashboard.sys, 'platform', 'win32'), mock.patch.object(
            dashboard.shutil, 'which', return_value='powershell.exe'
        ), mock.patch.object(dashboard.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, directory, '')) as run:
            dashboard.choose_workspace_folder()
            command = run.call_args.args[0]
            self.assertIn('-STA', command)
            self.assertIn('-NoProfile', command)
            self.assertIn('FolderBrowserDialog', command[-1])
            self.assertIn('ShowNewFolderButton = $false', command[-1])
            self.assertIn('UTF8Encoding', command[-1])
            self.assertIn('Dispose()', command[-1])
            self.assertEqual(run.call_args.kwargs['encoding'], 'utf-8')

    def test_failure_timeout_and_unavailable_environment_keep_manual_fallback(self):
        failures = [OSError('unavailable'), subprocess.TimeoutExpired(['osascript'], 120)]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), mock.patch.object(dashboard.sys, 'platform', 'darwin'), mock.patch.object(
                dashboard.subprocess, 'run', side_effect=failure
            ):
                with self.assertRaisesRegex(ValueError, '경로를 직접 입력'):
                    dashboard.choose_workspace_folder()
        with mock.patch.object(dashboard.sys, 'platform', 'linux'):
            with self.assertRaisesRegex(ValueError, '직접 입력'):
                dashboard.choose_workspace_folder()
        with mock.patch.object(dashboard.sys, 'platform', 'win32'), mock.patch.object(dashboard.shutil, 'which', return_value=None):
            with self.assertRaises(ValueError):
                dashboard.choose_workspace_folder()

    def test_native_error_does_not_expose_stderr(self):
        with mock.patch.object(dashboard.sys, 'platform', 'darwin'), mock.patch.object(
            dashboard.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'private diagnostics')
        ):
            with self.assertRaises(ValueError) as caught:
                dashboard.choose_workspace_folder()
            self.assertNotIn('private diagnostics', str(caught.exception))

    def test_relative_or_missing_selected_path_is_rejected(self):
        for selected in ('relative/path', '/nonexistent-folder-picker-test'):
            with self.subTest(selected=selected), mock.patch.object(dashboard.sys, 'platform', 'darwin'), mock.patch.object(
                dashboard.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, selected, '')
            ):
                with self.assertRaises(ValueError):
                    dashboard.choose_workspace_folder()

    def test_picker_does_not_hold_dashboard_lock_and_duplicate_is_rejected(self):
        app = dashboard.Dashboard()
        entered, finish = threading.Event(), threading.Event()
        def choose():
            entered.set()
            finish.wait(3)
            return {'cancelled': True}
        with mock.patch.object(dashboard, 'choose_workspace_folder', side_effect=choose):
            thread = threading.Thread(target=app.action, args=('choose-folder', {}))
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(app.lock.acquire(blocking=False))
                app.lock.release()
                with self.assertRaisesRegex(ValueError, '이미'):
                    app.action('choose-folder', {})
            finally:
                finish.set()
                thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(app.root)
        self.assertTrue(app.folder_picker_lock.acquire(blocking=False))
        app.folder_picker_lock.release()

    def test_error_releases_picker_lock(self):
        app = dashboard.Dashboard()
        with mock.patch.object(dashboard, 'choose_workspace_folder', side_effect=ValueError('native error')):
            with self.assertRaises(ValueError):
                app.action('choose-folder', {})
        self.assertTrue(app.folder_picker_lock.acquire(blocking=False))
        app.folder_picker_lock.release()

    def test_http_picker_requires_token_origin_and_preserves_connection(self):
        app = dashboard.Dashboard()
        server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        server.app = app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        def post(headers):
            req = request.Request(origin + '/api/choose-folder', data=b'{}', headers={'Content-Type': 'application/json', **headers})
            return request.urlopen(req, timeout=3)
        try:
            with mock.patch.object(dashboard, 'choose_workspace_folder', return_value={'root': '/chosen', 'cancelled': False}) as choose:
                for headers in ({'Origin': origin}, {'Origin': 'https://other.example', 'X-Dashboard-Token': app.token}):
                    with self.assertRaises(error.HTTPError) as caught:
                        post(headers)
                    self.assertEqual(caught.exception.code, 403)
                choose.assert_not_called()
                with post({'Origin': origin, 'X-Dashboard-Token': app.token}) as response:
                    self.assertEqual(json.load(response)['root'], '/chosen')
                choose.assert_called_once_with()
                self.assertIsNone(app.root)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    unittest.main()

class FolderBrowserFallbackTests(unittest.TestCase):
    def test_unicode_space_path_excludes_hidden_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / '한글 space'
            root.mkdir()
            visible = root / 'Alpha folder'
            visible.mkdir()
            (root / 'beta').mkdir()
            (root / '.hidden').mkdir()
            (root / 'note.md').write_text('not a directory', encoding='utf-8')
            link = root / 'linked'
            try:
                link.symlink_to(visible, target_is_directory=True)
            except OSError:
                link = None
            payload = dashboard.browse_folders({'path': str(root)}, None)
            self.assertEqual(payload['path'], str(root.resolve()))
            self.assertEqual(payload['parent'], str(root.parent.resolve()))
            self.assertEqual([item['name'] for item in payload['directories']], ['Alpha folder', 'beta'])
            self.assertNotIn('note.md', [item['name'] for item in payload['directories']])
            if link is not None:
                self.assertNotIn('linked', [item['name'] for item in payload['directories']])
            self.assertTrue(any(item['name'] == 'Home' for item in payload['shortcuts']))

    def test_path_validation_and_friendly_missing_or_permission_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            for value in (123, 'relative/path', 'x' * 4097, 'bad\x00path'):
                with self.subTest(value=repr(value)):
                    with self.assertRaises(ValueError):
                        dashboard.browse_folders({'path': value}, None)
            with self.assertRaisesRegex(ValueError, '찾을 수 없거나 읽을 수'):
                dashboard.browse_folders({'path': str(Path(directory) / 'missing')}, None)
            with mock.patch.object(dashboard.os, 'scandir', side_effect=PermissionError):
                with self.assertRaisesRegex(ValueError, '권한'):
                    dashboard.browse_folders({'path': directory}, None)

    def test_connected_default_and_browse_do_not_change_root_or_take_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'wiki root'
            child = root / 'child'
            child.mkdir(parents=True)
            app = dashboard.Dashboard()
            app.root = child.resolve()
            original = app.root
            with mock.patch.object(dashboard, 'browse_folders', wraps=dashboard.browse_folders) as browse:
                payload = app.action('browse-folders', {})
            self.assertEqual(payload['path'], str(root.resolve()))
            self.assertEqual(app.root, original)
            self.assertTrue(app.lock.acquire(blocking=False))
            app.lock.release()
            self.assertIn({'name': 'Current wiki', 'path': str(child.resolve())}, payload['shortcuts'])

    def test_directory_return_cap_is_sorted_and_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(205):
                (root / f'dir-{204 - index:03d}').mkdir()
            payload = dashboard.browse_folders({'path': directory}, None)
            names = [item['name'] for item in payload['directories']]
            self.assertEqual(len(names), 200)
            self.assertEqual(names, sorted(names, key=str.casefold))
            self.assertTrue(payload['truncated'])

    def test_scan_stops_after_five_thousand_entries_even_when_hidden(self):
        class Entry:
            name = '.hidden'

        class Entries:
            def __init__(self):
                self.count = 0
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def __iter__(self):
                return self
            def __next__(self):
                if self.count >= 5000:
                    raise AssertionError('scandir exceeded the entry bound')
                self.count += 1
                return Entry()

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(dashboard.os, 'scandir', return_value=Entries()):
            payload = dashboard.browse_folders({'path': directory}, None)
        self.assertEqual(payload['directories'], [])
        self.assertTrue(payload['truncated'])

    def test_http_browser_requires_existing_auth_guard(self):
        app = dashboard.Dashboard()
        server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        server.app = app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        def post(headers):
            req = request.Request(origin + '/api/browse-folders', data=b'{}', headers={'Content-Type': 'application/json', **headers})
            return request.urlopen(req, timeout=3)
        try:
            with mock.patch.object(dashboard, 'browse_folders', return_value={'path': '/', 'parent': None, 'directories': [], 'shortcuts': [], 'truncated': False}) as browse:
                with self.assertRaises(error.HTTPError) as caught:
                    post({'Origin': origin})
                self.assertEqual(caught.exception.code, 403)
                browse.assert_not_called()
                with post({'Origin': origin, 'X-Dashboard-Token': app.token}) as response:
                    self.assertEqual(json.load(response)['path'], '/')
                browse.assert_called_once_with({}, None)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
