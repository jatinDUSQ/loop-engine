#!/usr/bin/env bash
#
# run.sh — activate the virtualenv (creating it on first run) and run loop-engine.
#
# Usage:
#   ./run.sh check examples/candidate.good.json
#   ./run.sh check my_candidate.json --genre sleepcast
#   ./run.sh scan examples/raw_script.txt
#   ./run.sh --help
#
# Any arguments you pass are forwarded straight to the loop-engine CLI.

set -euo pipefail

# Always work from the project root (the folder this script lives in),
# so relative paths like examples/... work no matter where you call it from.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/.venv"

# 1. Create the virtualenv + install the package on first run.
if [ ! -d "$VENV_DIR" ]; then
  echo "[run.sh] First run: creating virtualenv in .venv ..."
  python3 -m venv "$VENV_DIR"
  echo "[run.sh] Installing loop-engine ..."
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools >/dev/null
  "$VENV_DIR/bin/pip" install --quiet -e "$PROJECT_DIR"
  echo "[run.sh] Setup complete."
fi

# 2. Activate the environment.
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 3. Run the code on that environment, forwarding all arguments.
#    With no arguments, show the help so it's obvious what to type.
if [ "$#" -eq 0 ]; then
  exec loop-engine --help
else
  exec loop-engine "$@"
fi
