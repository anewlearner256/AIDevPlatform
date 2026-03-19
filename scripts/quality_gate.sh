#!/usr/bin/env bash
set -euo pipefail

python -m compileall -q api core services models config tasks utils

if command -v pytest >/dev/null 2>&1; then
  PYTHONPATH=. pytest -q tests/unit -o addopts=''
else
  echo "pytest not installed, skip"
fi
