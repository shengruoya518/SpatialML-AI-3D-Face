#!/usr/bin/env python3
"""Loopback-only browser controls for the running Face Calibration app via devmux/adb."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import webbrowser

PACKAGE = 'com.pico.spatial.ml.sample.facelandmarker.registrationlab'
RANGES = {'fx': (250, 6000), 'fy': (250, 6000), 'cx': (0, 3248), 'cy': (0, 2464)}
ACTIONS = {'status', 'set', 'save_values', 'load_values', 'reset_c', 'auto_start', 'auto_check', 'auto_geometry', 'geometry_check', 'auto_roll', 'auto_cancel', 'pose_correction'}


def command_args(request):
    command = request.get('command')
    if command not in ACTIONS:
        raise ValueError('Unknown command')
    args = ['shell', 'am', 'broadcast', '-a', PACKAGE + '.COMMAND', '-p', PACKAGE,
            '--es', 'command', command]
    if command == 'set':
        parameter, value = request.get('parameter'), request.get('value')
        if parameter not in RANGES or type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Choose fx, fy, cx or cy and a finite numeric value')
        low, high = RANGES[parameter]
        if not low <= value <= high:
            raise ValueError(f'{parameter} must be between {low} and {high} pixels')
        args += ['--es', 'parameter', parameter, '--es', 'value', format(value, '.9f')]
    return args


def decode_response(output):
    match = re.search(r'FACE_LAB_V1:([A-Za-z0-9+/=]+)', output)
    if not match:
        raise RuntimeError('No response from the calibration app. Open SpatialML Face Calibration on the headset.')
    result = json.loads(base64.b64decode(match[1], validate=True))
    if result.get('schema') != 1 or set(result.get('values', {})) != set(RANGES):
        raise RuntimeError('Unsupported headset response. Install the desktop-control build.')
    return result


class Bridge:
    def __init__(self, serial, devmux):
        self.serial, self.devmux = serial, devmux
        self.lock = threading.Lock()
        self.env = dict(os.environ, DEVMUX_WAIT='0', DEVMUX_OWNER=f'face-calibration-desktop-{os.getpid()}')
        # The desktop server is its own device client, separate from the installing agent.
        self.env.pop('TRAECLI_THREAD_ID', None)

    def send(self, request):
        args = command_args(request)
        with self.lock:
            result = subprocess.run([self.devmux, 'adb', '-s', self.serial, *args],
                                    capture_output=True, text=True, timeout=12, env=self.env)
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f'Headset unavailable or busy: {detail[-500:]}')
        return decode_response(result.stdout)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, bridge):
        super().__init__(address, Handler)
        self.bridge = bridge
        self.token = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.page = (Path(__file__).parent / 'desktop/index.html').read_text().replace('__TOKEN__', self.token).encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, body, mime='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def allowed_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.allowed_host():
            return self.reply(403, {'error': 'Use the loopback URL printed by the server'})
        if self.path == '/':
            return self.reply(200, self.server.page, 'text/html; charset=utf-8')
        self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if (not self.allowed_host() or self.headers.get('Origin') != self.server.origin or
                self.headers.get('X-Calibrate-Token') != self.server.token):
            return self.reply(403, {'error': 'Request must come from this local calibration page'})
        if self.path != '/api/command':
            return self.reply(404, {'error': 'Not found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Invalid request size')
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError('Expected a command object')
            state = self.server.bridge.send(request)
            self.reply(200, dict(state=state, serial=self.server.bridge.serial))
        except (ValueError, TypeError) as error:
            self.reply(400, {'error': str(error)})
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            self.reply(503, {'error': str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', default='PB311XHGKC220141G')
    parser.add_argument('--port', type=int, default=47835)
    parser.add_argument('--devmux', default=str(Path.home() / '.trae/skills/devmux/scripts/devmux'))
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    server = Server(('127.0.0.1', args.port), Bridge(args.serial, args.devmux))
    print(f'Face Calibration: {server.origin}  |  headset {args.serial}', flush=True)
    if args.open:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
