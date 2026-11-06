#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo 'Install Python 3.11-3.13'; exit 1; }
command -v node >/dev/null || { echo 'Install Node.js LTS'; exit 1; }
command -v npm >/dev/null || { echo 'Install npm'; exit 1; }
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-ethereum.txt
[ -f node_modules/ganache/dist/node/cli.js ] || npm install --no-audit --no-fund
.venv/bin/python scripts/start_evm.py
