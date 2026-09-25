#!/usr/bin/env bash
# One-command clean install + full test run. No environment variables or caches required.
set -euo pipefail
python3 -m venv .venv && . .venv/bin/activate
pip install --quiet -r requirements-lock.txt
pip install --quiet -e .
python -m pytest -q tests
