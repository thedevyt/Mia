#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
python3 -m venv .venv
fi
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt


export PYTHONPATH=$(pwd):$PYTHONPATH
python -m ai_adapter.gui