"""Vercel serverless function for POST /api/analyze.

The front-end calls ./api/analyze on the same origin. Locally, server/app.py
serves that route; on Vercel, this file serves it. Both use the same
validation and engine (server/app.py and server/vendor/euler/).
"""
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app import InputError, analyze  # noqa: E402
from security import (  # noqa: E402
    RATE_LIMITER,
    SECURITY_HEADERS,
    client_key,
    content_length,
    media_type,
    same_origin,
)


class handler(BaseHTTPRequestHandler):
    server_version = "EULER"
    sys_version = ""

    def send_json(self, code, value, extra_headers=None):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        for name, header_value in SECURITY_HEADERS.items():
            self.send_header(name, header_value)
        if code == 405:
            self.send_header("Allow", "POST")
        for name, header_value in (extra_headers or {}).items():
            self.send_header(name, header_value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The visitor cancelled or closed the demonstration.

    def _method_not_allowed(self):
        self.send_json(405, {"message": "Envie a análise por POST."})

    do_GET = _method_not_allowed
    do_HEAD = _method_not_allowed
    do_OPTIONS = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed

    def do_POST(self):
        if not same_origin(self.headers):
            return self.send_json(403, {"message": "Envie a análise a partir deste site."})
        if media_type(self.headers) != "application/json":
            return self.send_json(415, {"message": "Formato de envio não suportado."})

        key = client_key(self.headers, getattr(self, "client_address", ("unknown",))[0])
        allowed, retry_after = RATE_LIMITER.check(key)
        if not allowed:
            return self.send_json(
                429,
                {"message": "Muitas análises em pouco tempo. Tente novamente em instantes."},
                {"Retry-After": str(retry_after)},
            )
        try:
            try:
                length = content_length(self.headers)
            except OverflowError:
                return self.send_json(413, {"message": "O envio deve ter até 3 MB."})
            except ValueError:
                return self.send_json(400, {"message": "Requisição HTTP inválida."})
            payload = json.loads(self.rfile.read(length))
            self.send_json(200, analyze(payload))
        except (InputError, ValueError, TypeError, KeyError) as error:
            self.send_json(
                422,
                {"message": str(error) if isinstance(error, InputError)
                 else "Não foi possível interpretar os dados. Confira valores, unidades e datas."},
            )
        except Exception as error:
            # The engine's domain errors carry a legible reason; do not return tracebacks.
            reason = getattr(error, "motivo", None)
            self.send_json(
                422 if reason else 500,
                {"message": reason or "Não foi possível concluir esta análise. Seus dados continuam no formulário; revise-os e tente novamente."},
            )
