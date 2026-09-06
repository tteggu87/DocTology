"""Local-only launch contracts for Wiki Studio wrappers and dashboard startup."""
from __future__ import annotations

import contextlib
import errno
import importlib.util
import io
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SCRIPT = RUNTIME / "wiki_dashboard.py"

spec = importlib.util.spec_from_file_location("wiki_dashboard_launcher_tests", SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class _Server:
    def __init__(self, port=4317, interrupt=True):
        self.server_port = port
        self.interrupt = interrupt
        self.closed = False

    def serve_forever(self):
        if self.interrupt:
            raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


class _App:
    def __init__(self, worker_error=None):
        self.automation = mock.Mock()
        if worker_error:
            self.automation.start_worker.side_effect = worker_error
        self.stop_all = mock.Mock()


class DashboardServerTests(unittest.TestCase):
    def test_real_ephemeral_server_binds_loopback_only(self):
        app = object()
        server = dashboard.dashboard_server(app, 0)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertGreater(server.server_port, 0)
            self.assertIs(server.app, app)
        finally:
            server.server_close()

    def test_occupied_port_falls_forward_when_auto_port_enabled(self):
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        try:
            server = dashboard.dashboard_server(object(), port, auto_port=True)
            try:
                self.assertNotEqual(server.server_port, port)
                self.assertGreaterEqual(server.server_port, port + 1)
                self.assertLessEqual(server.server_port, min(65535, port + 99))
            finally:
                server.server_close()
        finally:
            occupied.close()

    def test_auto_port_retries_only_address_in_use_candidates(self):
        created = []

        class FakeServer:
            def __init__(self, address, handler):
                created.append((address, handler))
                if len(created) == 1:
                    raise OSError(errno.EADDRINUSE, "busy")
                self.server_port = address[1]

        with mock.patch.object(dashboard, "ThreadingHTTPServer", FakeServer):
            server = dashboard.dashboard_server(object(), 52000, auto_port=True)
        self.assertEqual([row[0] for row in created], [("127.0.0.1", 52000), ("127.0.0.1", 52001)])
        self.assertEqual(server.server_port, 52001)

    def test_occupied_port_does_not_fallback_without_auto_port(self):
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        try:
            with self.assertRaises(OSError) as caught:
                dashboard.dashboard_server(object(), occupied.getsockname()[1])
            self.assertEqual(caught.exception.errno, errno.EADDRINUSE)
        finally:
            occupied.close()

    def test_permission_error_is_not_swallowed_as_port_fallback(self):
        with mock.patch.object(dashboard, "ThreadingHTTPServer", side_effect=OSError(errno.EACCES, "denied")):
            with self.assertRaises(OSError) as caught:
                dashboard.dashboard_server(object(), 52000, auto_port=True)
        self.assertEqual(caught.exception.errno, errno.EACCES)

    def test_port_bounds_are_rejected_before_binding(self):
        for port in (-1, 65536):
            with self.subTest(port=port):
                with self.assertRaisesRegex(ValueError, "0 and 65535"):
                    dashboard.dashboard_server(object(), port)
                with mock.patch.object(dashboard, "Dashboard") as app, \
                     contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        dashboard.main(["--port", str(port)])
                self.assertEqual(caught.exception.code, 2)
                app.assert_not_called()


class DashboardStartupTests(unittest.TestCase):
    def test_browser_open_failure_never_throws(self):
        for effect in (False, RuntimeError("desktop unavailable")):
            with self.subTest(effect=effect), contextlib.redirect_stdout(io.StringIO()) as output:
                with mock.patch.object(dashboard.webbrowser, "open", side_effect=effect if isinstance(effect, Exception) else None,
                                       return_value=effect if isinstance(effect, bool) else mock.DEFAULT):
                    dashboard.open_dashboard_browser("http://127.0.0.1:4317/")
            self.assertIn("http://127.0.0.1:4317/", output.getvalue())

    def test_browser_option_opens_only_the_bound_url_after_worker_start(self):
        app, server = _App(), _Server(port=53001)
        order = []
        app.automation.start_worker.side_effect = lambda: order.append("worker")

        class ImmediateThread:
            def __init__(self, *, target, args, daemon):
                self.target, self.args = target, args
                self.daemon = daemon

            def start(self):
                order.append("browser")
                self.target(*self.args)

        with mock.patch.object(dashboard, "Dashboard", return_value=app), \
             mock.patch.object(dashboard, "dashboard_server", return_value=server) as bind, \
             mock.patch.object(dashboard.threading, "Thread", ImmediateThread), \
             mock.patch.object(dashboard.webbrowser, "open", return_value=True) as browser, \
             contextlib.redirect_stdout(io.StringIO()):
            dashboard.main(["--port", "53000", "--open-browser", "--auto-port"])
        bind.assert_called_once_with(app, 53000, auto_port=True)
        browser.assert_called_once_with("http://127.0.0.1:53001/", new=2)
        self.assertEqual(order, ["worker", "browser"])
        self.assertTrue(server.closed)

    def test_main_defaults_to_no_browser_thread(self):
        app, server = _App(), _Server()
        with mock.patch.object(dashboard, "Dashboard", return_value=app), \
             mock.patch.object(dashboard, "dashboard_server", return_value=server), \
             mock.patch.object(dashboard.threading, "Thread") as thread, \
             contextlib.redirect_stdout(io.StringIO()):
            dashboard.main([])
        app.automation.start_worker.assert_called_once_with()
        thread.assert_not_called()
        app.stop_all.assert_called_once_with()
        self.assertTrue(server.closed)

    def test_startup_worker_failure_stops_app_and_closes_server(self):
        app, server = _App(worker_error=RuntimeError("worker failed")), _Server(interrupt=False)
        with mock.patch.object(dashboard, "Dashboard", return_value=app), \
             mock.patch.object(dashboard, "dashboard_server", return_value=server), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "worker failed"):
                dashboard.main([])
        app.stop_all.assert_called_once_with()
        self.assertTrue(server.closed)


class LauncherContractTests(unittest.TestCase):
    def test_command_launchers_are_executable(self):
        for launcher in (ROOT / "Wiki-Studio.command", RUNTIME / "start_dashboard.command"):
            with self.subTest(launcher=launcher):
                self.assertTrue(launcher.is_file())
                self.assertTrue(launcher.stat().st_mode & stat.S_IXUSR)

    @unittest.skipUnless(os.name == "posix", "macOS shell launcher contract")
    def test_root_command_uses_runtime_launcher_from_any_cwd_and_preserves_args(self):
        with tempfile.TemporaryDirectory(prefix="wiki studio 한글 ") as directory:
            copied = Path(directory) / "복사본 with spaces"
            runtime = copied / "runtime"
            runtime.mkdir(parents=True)
            shutil.copy2(ROOT / "Wiki-Studio.command", copied / "Wiki-Studio.command")
            shutil.copy2(RUNTIME / "start_dashboard.command", runtime / "start_dashboard.command")
            recorder = copied / "fake python.py"
            record = copied / "record.json"
            recorder.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "if sys.argv[1:2] == ['-c']: sys.exit(0)\n"
                "open(os.environ['WIKI_STUDIO_RECORD'], 'w', encoding='utf-8').write(json.dumps(sys.argv[1:], ensure_ascii=False))\n"
                "sys.exit(int(os.environ.get('WIKI_STUDIO_EXIT', '0')))\n",
                encoding="utf-8",
            )
            recorder.chmod(recorder.stat().st_mode | stat.S_IXUSR)
            env = os.environ | {"WIKI_STUDIO_PYTHON": str(recorder), "WIKI_STUDIO_RECORD": str(record), "WIKI_STUDIO_EXIT": "7"}
            result = subprocess.run(["/bin/bash", str(copied / "Wiki-Studio.command"), "--port", "5500", "한글 값"],
                                    cwd=Path(tempfile.gettempdir()), env=env, text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(__import__("json").loads(record.read_text(encoding="utf-8")),
                             [str(runtime / "wiki_dashboard.py"), "--open-browser", "--auto-port", "--port", "5500", "한글 값"])

    @unittest.skipUnless(os.name == "posix", "macOS shell launcher contract")
    def test_missing_python_override_exits_one_without_tty_pause(self):
        result = subprocess.run(["/bin/bash", str(RUNTIME / "start_dashboard.command")], cwd=tempfile.gettempdir(),
                                env=os.environ | {"WIKI_STUDIO_PYTHON": "/definitely/missing/python"},
                                stdin=subprocess.DEVNULL, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Python 3.11", result.stdout)
        self.assertNotIn("Press Enter", result.stdout)

    def test_windows_launchers_have_static_safe_contracts(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.command text eol=lf", attributes)
        self.assertIn("*.bat text eol=crlf", attributes)
        root = (ROOT / "Wiki-Studio.bat").read_text(encoding="utf-8")
        runtime = (RUNTIME / "start_dashboard.bat").read_text(encoding="utf-8")
        self.assertIn('"%~dp0runtime\\start_dashboard.bat" %*', root)
        self.assertIn("setlocal DisableDelayedExpansion", root)
        self.assertIn("if defined WIKI_STUDIO_PYTHON goto custom_python", runtime)
        self.assertIn('"%WIKI_STUDIO_PYTHON%" "%~dp0wiki_dashboard.py" --open-browser --auto-port %*', runtime)
        self.assertIn('set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"', runtime)
        self.assertIn('set "PYLAUNCHER_ALLOW_INSTALL="', runtime)
        self.assertIn('set "PYLAUNCHER_ALWAYS_INSTALL="', runtime)
        self.assertIn("goto missing_python", runtime)
        self.assertIn("exit /b %STUDIO_EXIT%", runtime)


if __name__ == "__main__":
    unittest.main()
