#!/bin/sh
# The same checks as check.ps1, for macOS and Linux. Needs Python 3.12 and Node 20+.
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3.12 -m venv .venv
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/python scripts/make_vectors.py --check
node --test web/sabond.test.mjs
