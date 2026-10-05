"""Exercise both HTTP adapters with the same synthetic requests."""
import http.client
import io
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_preview_api import example

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from app import Handler

spec = importlib.util.spec_from_file_location('vercel_analyze', ROOT / 'api/analyze.py')
vercel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vercel)


class MemorySocket:
    """Transport HTTP bytes without opening a network port."""
    def __init__(self, data):
        self.input = io.BytesIO(data)
        self.output = io.BytesIO()

    def makefile(self, *args):
        return self.input

    def sendall(self, data):
        self.output.write(data)


class HTTPTests(unittest.TestCase):
    def test_local_and_vercel_contract(self):
        for adapter in (Handler, vercel.handler):
            with self.subTest(adapter=adapter.__module__):
                with patch.object(adapter, 'log_message'):
                    def request(method='POST', path='/api/analyze', body='{}', headers=None):
                        body = (body or '').encode()
                        fields = {'Host': 'localhost', 'Content-Length': str(len(body)),
                                  'Content-Type': 'application/json', **(headers or {})}
                        head = f'{method} {path} HTTP/1.0\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in fields.items())
                        transport = MemorySocket(head.encode() + b'\r\n' + body)
                        adapter(transport, ('127.0.0.1', 12345), None)
                        response = http.client.HTTPResponse(MemorySocket(transport.output.getvalue()), method=method)
                        response.begin()
                        return response.status, dict(response.getheaders()), response.read()

                    status, headers, body = request(body=json.dumps(example()))
                    self.assertEqual(status, 200)
                    self.assertEqual(json.loads(body)['status'], 'supported')
                    self.assertEqual(headers['Cache-Control'], 'no-store')
                    self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                    for raw in ('{', '{}', 'null', '[]'):
                        status, _, body = request(body=raw)
                        self.assertEqual(status, 422)
                        self.assertIn('message', json.loads(body))
                    self.assertEqual(request(headers={'Content-Type': 'text/plain'})[0], 415)
                    self.assertEqual(request(body='')[0], 413)
                    self.assertEqual(request(headers={'Content-Type': 'application/json', 'Content-Length': '3000001'})[0], 413)
                    for origin in ('https://foreign.example', 'http://[', 'null'):
                        self.assertEqual(request(headers={'Content-Type': 'application/json', 'Origin': origin})[0], 403)
                    self.assertEqual(request(headers={'Origin': 'http://localhost'})[0], 422)
                    status, headers, _ = request(method='GET', body=None)
                    self.assertEqual(status, 405)
                    self.assertEqual(headers['Allow'], 'POST')
                    if adapter is Handler:
                        self.assertEqual(request('GET', '/', None)[0], 200)
                        self.assertEqual(request('GET', '/legal.html', None)[0], 200)
                        self.assertEqual(request('HEAD', '/legal.html', None)[0], 200)
                        self.assertEqual(request('GET', '/assets/euler-schema.json', None)[0], 200)
                        for path in ('/server/app.py', '/.git/config', '/pyproject.toml', '/assets/../server/app.py'):
                            for method in ('GET', 'HEAD'):
                                self.assertEqual(request(method, path, None)[0], 404)


if __name__ == '__main__':
    unittest.main()
