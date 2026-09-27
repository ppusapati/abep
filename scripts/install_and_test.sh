#!/usr/bin/env bash
# One-command clean install + full test run + golden check (docs/ci/PACKAGING.md). No environment variables or caches
# required. Run from the repository root. Optional arguments are passed to pytest instead of the default `tests`
# (e.g. `scripts/install_and_test.sh tests/test_packaging.py`). PYTHON selects the interpreter (default python3, >= 3.11).
set -euo pipefail
PYTHON="${PYTHON:-python3}"
"$PYTHON" - <<'EOF'
import sys
if sys.version_info < (3, 11):
    sys.exit(f"abep-sim needs Python >= 3.11 (tomllib, requirements-lock.txt); {sys.executable} is {sys.version.split()[0]}. "
             "Set PYTHON=python3.11.")
EOF
"$PYTHON" -m venv .venv
. .venv/bin/activate
pip install --quiet -r requirements-lock.txt
# --no-deps: requirements-lock.txt is the dependency source of truth (same as CI).
pip install --quiet --no-deps -e .
if [ "$#" -eq 0 ]; then set -- tests; fi
python -m pytest -q "$@"
# abep_sim.golden prints "OK" or the list of deviations and exits 0 either way, so gate on its output (CLAUDE.md rule 2).
out="$(python -m abep_sim.golden check)"
printf '%s\n' "$out"
[ "$(printf '%s\n' "$out" | tail -n 1)" = "OK" ] || { echo "golden benchmarks moved (CLAUDE.md rule 2)" >&2; exit 1; }
