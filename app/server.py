"""Session-authenticated loopback configuration server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit
from .dependencies import status, TARGET_URL, VIGEM_URL
from .keyboard import WindowsLayouts
from .model import ConfigurationError, Store, MODES, defaults, validate
from .target import generate
from .windows import Joysticks
from .game_controls import key_action, xbox_choices

WEB = Path(__file__).parent / 'web'


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass


def create_server(root, fixture=None, initial_mode=None):
    store = Store(root)
    token = secrets.token_urlsafe(32)
    if fixture is None:
        layouts = WindowsLayouts()
        inputs = Joysticks()
    else:
        layouts = None
        inputs = None

    def fixture_data():
        return json.loads(Path(fixture).read_text(encoding='utf-8')) if isinstance(fixture, (str, Path)) else fixture

    def dependencies(mode, path):
        if fixture is None:
            return status(root, mode, path)
        data = fixture_data()
        entries = status(root, mode, path, candidates=[], probe=lambda: data['ready'],
                         runtime=lambda: True, microsoft=lambda: True)
        for item in entries:
            if item['id'] == 'target' and path == 'fixture-target':
                item.update(ready=True, path=path)
        return entries

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *args):
            pass

        def route(self):
            parsed = urlsplit(self.path)
            if self.headers.get('Host') != host or not parsed.path.startswith('/' + token + '/') or parsed.query:
                return None
            return parsed.path[len(token) + 2:]

        def reply(self, code, body, mime='application/json; charset=utf-8'):
            self.send_response(code)
            for key, value in {'Content-Type': mime, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store',
                               'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                               'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def json(self, code, data):
            self.reply(code, json.dumps(data, allow_nan=False).encode())

        def do_GET(self):
            route = self.route()
            try:
                if route == 'state':
                    saved = store.load()
                    if initial_mode is not None:
                        saved['preferred_mode'] = initial_mode
                    data = fixture_data() if fixture is not None else {'layouts': layouts.items, 'suggested': layouts.suggested}
                    self.json(200, {'saved': saved, 'defaults': {m: defaults(m) for m in MODES},
                                    'layouts': data['layouts'], 'suggested': data['suggested'],
                                    'active': (store.local / 'session.json').exists(),
                                    'game_controls': {'xbox': xbox_choices()}})
                elif route == 'input':
                    if fixture is not None:
                        self.json(200, fixture_data().get('input', {'available': False, 'message': 'Connect both TCA devices to preview input.'}))
                    else:
                        mode = store.load()['preferred_mode']
                        self.json(200, {'available': True, 'state': inputs.snapshot('target-xbox' if mode == 'target-xbox' and (store.local / 'session.json').exists() else 'xbox')})
                elif route in ('', 'boot.js', 'ui.js', 'logic.js', 'style.css',
                               'device/sidestick.svg', 'device/quadrant.svg', 'device/sidestick-grip.svg', 'device/quadrant-grip.svg'):
                    name = 'index.html' if route == '' else route
                    mime = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css', 'svg': 'image/svg+xml'}[name.rsplit('.', 1)[1]]
                    self.reply(200, (WEB / name).read_bytes(), mime + '; charset=utf-8')
                else:
                    self.json(404, {'message': 'Not found.'})
            except (OSError, ValueError, RuntimeError):
                self.json(503, {'available': False, 'message': 'Local state or input is unavailable. Recheck configuration and connect both controllers.'})

        def do_POST(self):
            route = self.route()
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = 0
            raw = self.rfile.read(min(max(size, 0), 32001))
            if route not in ('save', 'dependencies', 'key-action') or self.headers.get('Origin') != 'http://' + host:
                self.json(403, {'message': 'Request rejected.'})
                return
            if self.headers.get('Content-Type') != 'application/json':
                self.json(415, {'message': 'JSON required.'})
                return
            try:
                if not 0 < size <= 32000:
                    raise ValueError('Invalid request size.')
                data = json.loads(raw)
                if route == 'key-action':
                    if not isinstance(data, dict) or set(data) != {'layout', 'binding'}:
                        raise ValueError('Invalid key-action request.')
                    resolver = (lambda binding, layout: (1004, [])) if fixture is not None else layouts.resolve
                    self.json(200, key_action(data['binding'], data['layout'], resolver))
                    return
                fields = {'mode', 'target_path'} | ({'profile'} if route == 'save' else set())
                if not isinstance(data, dict) or set(data) != fields or data['mode'] not in MODES or not isinstance(data['target_path'], str):
                    raise ValueError('Invalid configuration request.')
                if route == 'dependencies':
                    self.json(200, dependencies(data['mode'], data['target_path']))
                    return
                if (store.local / 'session.json').exists():
                    self.json(409, {'message': 'Stop emulation before saving changes.'})
                    return
                cfg = validate(data['mode'], data['profile'])
                if data['mode'] == 'keyboard':
                    available = fixture_data()['layouts'] if fixture is not None else layouts.items
                    if cfg['layout'] not in {item['id'] for item in available}:
                        raise ConfigurationError('Select a currently installed keyboard layout.', 'layout')
                    resolver = (lambda binding, layout: (1004, [])) if fixture is not None else layouts.resolve
                    for section in ('keys', 'buttons'):
                        for key, binding in cfg[section].items():
                            if binding != '':
                                try:
                                    resolver(binding, cfg['layout'])
                                except ValueError as error:
                                    raise ConfigurationError(str(error), f'{section}:{key}') from error
                    generate('keyboard', cfg, store.local, 'validation', resolver)
                store.save(data['mode'], cfg, data['target_path'])
                label = {'keyboard': 'Keyboard · TARGET', 'xbox': 'Xbox · direct input', 'target-xbox': 'TARGET → Xbox'}[data['mode']]
                self.json(200, {'message': f'Saved. Run emulate.cmd to start {label}.'})
            except ValueError as error:
                self.json(400, {'message': str(error), **({'field': error.field} if isinstance(error, ConfigurationError) else {})})
            except OSError:
                self.json(500, {'message': 'Could not save configuration. Check folder permissions; your previous save is preserved.'})

    server = QuietServer(('127.0.0.1', 0), Handler)
    host = f'127.0.0.1:{server.server_port}'
    server.token = token
    server.url = f'http://{host}/{token}/'
    return server
