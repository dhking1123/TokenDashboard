$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    python tests/test_release.py
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    python -m PyInstaller packaging/CodexUsageDashboard.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    @'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

with ZipFile('dist/CodexUsageDashboard-Windows-x64.zip', 'w', ZIP_DEFLATED) as package:
    package.write('dist/CodexUsageDashboard.exe', 'CodexUsageDashboard.exe')
    for name in ('README.md', 'readme-header.svg', 'requirements.txt'):
        package.write(name)
    for pattern in ('src/*.py', 'tests/*.py', 'scripts/*.py', 'scripts/*.ps1', 'scripts/*.sh',
                    'packaging/*.spec', 'assets/*.ico', 'assets/*.png', 'licenses/*.txt', 'docs/*.md'):
        for path in sorted(Path('.').glob(pattern)):
            package.write(path)
'@ | python -
    if ($LASTEXITCODE -ne 0) { throw 'Packaging failed' }
} finally { Pop-Location }
