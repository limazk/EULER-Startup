#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import pandas, numpy, iapws, openpyxl; assert int(pandas.__version__.split(".")[0]) >= 3' >/dev/null 2>&1; then
  .venv/bin/pip install -r server/requirements.txt
fi
exec .venv/bin/python server/app.py "$@"
