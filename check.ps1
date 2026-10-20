# Sets up .venv if it isn't there, then runs every check: the Python tests, a check that the
# JavaScript test vectors are up to date, and the JavaScript tests. Needs Python 3.12 and Node 20+.
# Usage, from the repo folder in PowerShell:  .\check.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $py -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $py -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $py scripts\make_vectors.py --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
node --test web/sabond.test.mjs
exit $LASTEXITCODE
