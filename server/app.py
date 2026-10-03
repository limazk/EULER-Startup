"""Landing + preview API. Uses the original EULER engine, without persisting input.

Run: .venv/bin/python server/app.py --port 8766
Only the public assets are served. Full investigations never leave the server.
"""
from __future__ import annotations

import argparse
import csv
import io
from dataclasses import asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent / "vendor"))

import pandas as pd
from euler.io import importar_pacote
from euler.io.esquemas import TABELAS
from euler.investigacao import investigar
from euler.vapor import p_atm_por_altitude_bar
from security import (
    RATE_LIMITER,
    SECURITY_HEADERS,
    client_key,
    content_length,
    media_type,
    same_origin,
)


class InputError(ValueError):
    pass


def validate(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("tables"), dict):
        raise InputError("Informe os registros da caldeira.")
    tables = payload["tables"]
    if set(tables) - set(TABELAS):
        raise InputError("Há um grupo de registros desconhecido.")
    total = 0
    for name, rows in tables.items():
        if not isinstance(rows, list):
            raise InputError("Cada grupo precisa conter uma lista de registros.")
        total += len(rows)
        if total > 5000:
            raise InputError("Use até 5.000 registros nesta prévia. Para bases maiores, proponha um piloto.")
        columns = {c.nome for c in TABELAS[name].colunas}
        for row in rows:
            if not isinstance(row, dict) or set(row) - columns:
                raise InputError(f"Confira as colunas de {TABELAS[name].titulo}.")
            for value in row.values():
                if value is not None and (isinstance(value, (dict, list)) or len(str(value)) > 2000):
                    raise InputError("Um campo contém um valor inválido ou muito longo.")
                if isinstance(value, float) and not math.isfinite(value):
                    raise InputError("Use apenas números finitos.")
    if not tables.get("diario"):
        raise InputError("Adicione leituras ao diário para comparar os períodos.")
    boilers = {str(r.get("caldeira_id", "")).strip() for r in tables["diario"]}
    if len(boilers) != 1 or "" in boilers:
        raise InputError("Use registros de uma única caldeira e identifique todas as leituras.")
    altitude = payload.get("altitude")
    if altitude is not None:
        if isinstance(altitude, bool) or not isinstance(altitude, (int, float)) or not math.isfinite(altitude) or not -500 <= altitude <= 5000:
            raise InputError("Informe uma altitude entre −500 e 5.000 m, ou deixe em branco.")
    periods = []
    for name in ("reference", "comparison"):
        values = payload.get(name)
        if not isinstance(values, list) or len(values) != 2:
            raise InputError("Escolha o início e o fim dos dois períodos.")
        try:
            dates = tuple(pd.Timestamp(v) for v in values)
            if any(pd.isna(v) or v.tzinfo is None for v in dates) or dates[0] >= dates[1]:
                raise ValueError()
        except (ValueError, TypeError):
            raise InputError("Use datas válidas, com início anterior ao fim e fuso horário informado.") from None
        periods.append(dates)
    if not (periods[0][1] <= periods[1][0] or periods[1][1] <= periods[0][0]):
        raise InputError("Os períodos não podem se sobrepor. O fim de um pode ser o início do outro.")
    return tables, altitude, periods


def analyze(payload):
    tables, altitude, periods = validate(payload)
    sources = {}
    for name, rows in tables.items():
        if not rows:
            continue
        buffer = io.StringIO()
        # The form accepts decimal comma or decimal point, never thousands separators.
        # Serialize as comma-separated CSV with decimal point. Using ';' would make
        # the importer interpret values such as 0.345 as Brazilian thousands (345).
        writer = csv.DictWriter(buffer, fieldnames=[c.nome for c in TABELAS[name].colunas])
        writer.writeheader()
        numeric = {c.nome for c in TABELAS[name].colunas if c.tipo == "numero"}
        for row in rows:
            normalized = dict(row)
            for key in numeric & row.keys():
                raw = str(row[key] or "").strip() if row[key] != 0 else "0"
                if raw:
                    try:
                        value = float(raw.replace(",", "."))
                        if not math.isfinite(value):
                            raise ValueError()
                    except ValueError:
                        raise InputError(f"Confira o campo {TABELAS[name].coluna(key).rotulo}: use número sem separador de milhar.") from None
                    normalized[key] = raw.replace(",", ".")
            writer.writerow(normalized)
        sources[name] = buffer.getvalue().encode("utf-8")
    package = importar_pacote(sources, p_atm_bar=None if altitude is None else p_atm_por_altitude_bar(altitude))
    warnings = [asdict(a) for a in package.avisos]
    if any(a.gravidade == "erro" for a in package.avisos):
        return {"validation": True, "message": "Revise os registros indicados antes de analisar.", "warnings": warnings}
    investigation = investigar(package, *periods)
    consumption = investigation["o_que_mudou"]["consumo_especifico"]
    conclusions = investigation["conclusao"]
    compatible = [h["titulo"] for h in investigation["hipoteses"] if h["status"] == "sustentada"]
    limits = list(investigation["o_que_falta"])
    # Assumptions and exclusions are necessary to interpret the public preview;
    # they are never withheld as part of the commercial boundary.
    for period in investigation["periodos"].values():
        for value in period.values():
            if isinstance(value, dict):
                limits.extend(value.get("nao_incluido_na_incerteza", []))
        if "assum" in str(period.get("composicao_origem", "")):
            limits.append("Composição do combustível assumida pelo motor: " + period["composicao_origem"])
    if altitude is None:
        limits.append("Pressão atmosférica de referência assumida: altitude da instalação não informada.")
    # Commercial boundary: no hidden full JSON in HTML/JS, no financial decomposition
    # or detailed evidence in this public response. Interpretation limits remain visible.
    return {
        "boiler": investigation["caldeira_id"],
        "source": investigation["origem_dados"],
        "status": "insufficient" if consumption["referencia"] is None or consumption["comparacao"] is None else "limited" if conclusions["abstencao"] else "supported",
        "consumption": consumption,
        "finding": investigation["o_que_mudou"]["frase"],
        "reason": conclusions["motivo"],
        "hypotheses": compatible[:2],
        "hypothesisCount": len(compatible),
        "next": investigation["proxima_verificacao"],
        "limits": list(dict.fromkeys(limits)),
        "criteria": investigation["criterios"]["nota"],
        "warnings": warnings,
    }


class Handler(SimpleHTTPRequestHandler):
    server_version = "EULER"
    sys_version = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def json_response(self, code, value, extra_headers=None):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if code == 405:
            self.send_header("Allow", "POST")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/analyze":
            return self.json_response(405, {"message": "Envie a análise por POST."})
        if path == "/api/status":
            return self.json_response(200, {"ready": True})
        resolved = Path(self.translate_path(self.path)).resolve()
        allowed = resolved in {ROOT / "index.html", ROOT / "og-image.png", ROOT} or resolved.is_relative_to(ROOT / "assets")
        if not allowed or (resolved != ROOT and not resolved.is_file()):
            return self.send_error(404)
        super().do_GET()

    def do_HEAD(self):
        # Same allowlist as GET; avoid exposing source or virtual-environment paths.
        path = Path(self.translate_path(self.path)).resolve()
        if path not in {ROOT, ROOT / "index.html", ROOT / "og-image.png"} and not path.is_relative_to(ROOT / "assets"):
            return self.send_error(404)
        if path.is_dir() and path != ROOT:
            return self.send_error(404)
        super().do_HEAD()

    def _api_method_not_allowed(self):
        if urlsplit(self.path).path == "/api/analyze":
            return self.json_response(405, {"message": "Envie a análise por POST."})
        return self.send_error(404)

    do_OPTIONS = _api_method_not_allowed
    do_PUT = _api_method_not_allowed
    do_PATCH = _api_method_not_allowed
    do_DELETE = _api_method_not_allowed

    def do_POST(self):
        if urlsplit(self.path).path != "/api/analyze":
            return self.send_error(404)
        if not same_origin(self.headers):
            return self.json_response(403, {"message": "Envie a análise a partir deste site."})
        if media_type(self.headers) != "application/json":
            return self.json_response(415, {"message": "Formato de envio não suportado."})

        key = client_key(self.headers, getattr(self, "client_address", ("unknown",))[0])
        allowed, retry_after = RATE_LIMITER.check(key)
        if not allowed:
            return self.json_response(
                429,
                {"message": "Muitas análises em pouco tempo. Tente novamente em instantes."},
                {"Retry-After": str(retry_after)},
            )
        try:
            try:
                length = content_length(self.headers)
            except OverflowError:
                return self.json_response(413, {"message": "O envio deve ter até 3 MB."})
            except ValueError:
                return self.json_response(400, {"message": "Requisição HTTP inválida."})
            payload = json.loads(self.rfile.read(length))
            self.json_response(200, analyze(payload))
        except (InputError, ValueError, TypeError, KeyError) as error:
            self.json_response(422, {"message": str(error) if isinstance(error, InputError) else "Não foi possível interpretar os dados. Confira valores, unidades e datas."})
        except Exception as error:
            # The engine's domain errors carry a legible reason; do not return tracebacks.
            reason = getattr(error, "motivo", None)
            self.json_response(422 if reason else 500, {"message": reason or "Não foi possível concluir esta análise. Seus dados continuam no formulário; revise-os e tente novamente."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"EULER disponível em http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
