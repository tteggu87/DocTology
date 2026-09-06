"""Local HTTP transport. Application policy and document access are injected.

index.html owns the ordered frontend script list. Only those declared local
scripts and the fixed HTML/CSS entrypoints are admitted, never a directory tree.
"""
from __future__ import annotations

from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path, PurePosixPath
import re
import secrets
from types import MappingProxyType
from urllib.parse import parse_qs, urlparse


class _ScriptManifest(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag != 'script':
            return
        attributes = dict(attrs)
        source = attributes.get('src')
        if not source or 'defer' not in attributes:
            raise ValueError('Dashboard scripts must be external and deferred.')
        if not re.fullmatch(r'/?[A-Za-z0-9_./-]+\.js', source) or source.startswith('//'):
            raise ValueError('Dashboard script must use a local JavaScript path.')
        relative = source.lstrip('/')
        if ('..' in PurePosixPath(relative).parts or PurePosixPath(relative).as_posix() != relative
                or relative in self.scripts):
            raise ValueError('Dashboard script path is duplicated or unsafe.')
        self.scripts.append(relative)
        if len(self.scripts) > 32:
            raise ValueError('Dashboard script manifest is too large.')


def frontend_assets(asset_root: Path):
    """Read the trusted UI declaration once; validate every admitted file."""
    parser = _ScriptManifest()
    parser.feed((asset_root / 'index.html').read_text(encoding='utf-8'))
    if not parser.scripts:
        raise ValueError('Dashboard has no declared frontend scripts.')
    assets = {'/': ('index.html', 'text/html; charset=utf-8'),
              '/style.css': ('style.css', 'text/css; charset=utf-8')}
    for relative in parser.scripts:
        assets['/' + relative] = (relative, 'text/javascript; charset=utf-8')
    for relative, _mime in assets.values():
        path = (asset_root / relative).resolve()
        if not path.is_relative_to(asset_root.resolve()) or not path.is_file():
            raise ValueError('Declared dashboard asset is missing or outside the asset root.')
    return MappingProxyType(assets)


def make_handler(*, asset_root, document_payload, chat_not_found_error,
                 save_partial_error, workflow_error):
    """Compose a handler without importing the application or its runtime."""
    asset_root = Path(asset_root)
    assets = frontend_assets(asset_root)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, data, code=200, mime='application/json; charset=utf-8'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def trusted(self):
            return self.headers.get('Host', '') in {
                f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.trusted():
                return self.reply({'error': '잘못된 호스트'}, 403)
            url = urlparse(self.path)
            app = self.server.app
            try:
                if url.path == '/api/state':
                    queue_offset = int(parse_qs(url.query).get('queueOffset', ['0'])[0])
                    return self.reply(app.state(queue_offset=queue_offset))
                if url.path == '/api/session':
                    return self.reply({'token': app.token})
                if url.path == '/api/chat':
                    job_id = parse_qs(url.query).get('id', [''])[0]
                    return self.reply(app.chat_status(job_id))
                if url.path == '/api/document':
                    params = parse_qs(url.query, keep_blank_values=True)
                    relative = params.get('path', [''])[0]
                    with app.lock:
                        if not app.root:
                            raise ValueError('실제 위키를 연결하세요.')
                        current_root = str(app.root.resolve())
                        if 'expectedRoot' in params and params['expectedRoot'][0] != current_root:
                            raise ValueError('연결된 작업 공간이 변경되었습니다. 문서 목록을 새로고침하세요.')
                        payload = document_payload(app.root, app.mode, relative)
                    return self.reply(payload)
                if url.path not in assets:
                    return self.reply({'error': '찾을 수 없습니다.'}, 404)
                relative, mime = assets[url.path]
                path = (asset_root / relative).resolve()
                if not path.is_relative_to(asset_root.resolve()):
                    return self.reply({'error': '허용되지 않는 정적 파일'}, 403)
                self.reply(path.read_bytes(), mime=mime)
            except chat_not_found_error as exc:
                self.reply({'error': str(exc)}, 404)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.reply({'error': str(exc)}, 400)

        def do_POST(self):
            app = self.server.app
            origin = self.headers.get('Origin')
            expected = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if not self.trusted() or origin not in expected or not secrets.compare_digest(self.headers.get('X-Dashboard-Token', ''), app.token):
                return self.reply({'error': '이 대시보드에서 보낸 요청만 허용됩니다.'}, 403)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2_100_000:
                    raise ValueError('요청 크기가 허용 범위를 벗어났습니다.')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('잘못된 요청 형식입니다.')
                route = urlparse(self.path).path
                if not route.startswith('/api/'):
                    raise ValueError('지원하지 않는 경로입니다.')
                self.reply(app.action(route.removeprefix('/api/'), body))
            except save_partial_error as exc:
                self.reply({**exc.payload, 'error': str(exc), 'queueHandoff': False}, 409)
            except (OSError, ValueError, KeyError, TypeError, workflow_error) as exc:
                self.reply({'error': str(exc)}, 400)

    return Handler
