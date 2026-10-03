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

from app import InputError, analyze, same_origin  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def send_json(self, code, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if code == 405:
            self.send_header("Allow", "POST")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The visitor cancelled or closed the demonstration.

    def do_GET(self):
        self.send_json(405, {"message": "Envie a análise por POST."})

    def do_POST(self):
        origin = self.headers.get("Origin")
        if not same_origin(origin, self.headers.get("Host")):
            return self.send_json(403, {"message": "Envie a análise a partir deste site."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.send_json(415, {"message": "Formato de envio não suportado."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 3_000_000:
                return self.send_json(413, {"message": "O envio deve ter até 3 MB."})
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
