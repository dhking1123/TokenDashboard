$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python test_release.py
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    python -m PyInstaller CodexUsageDashboard.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    $packageFiles = @('README.txt', 'THIRD_PARTY.txt', 'GPL-3.0.txt', 'LGPL-3.0.txt', 'PYTHON-LICENSE.txt', 'usage-dashboard.py', 'CodexUsageDashboard.spec', 'battery.ico', 'requirements.txt', 'build.ps1', 'test_release.py')
    foreach ($file in $packageFiles) { Copy-Item -LiteralPath $file -Destination 'dist' -Force }
    Compress-Archive -LiteralPath (@('dist/CodexUsageDashboard.exe') + ($packageFiles | ForEach-Object { "dist/$_" })) -DestinationPath 'dist/CodexUsageDashboard-Windows-x64.zip' -Force
} finally { Pop-Location }
