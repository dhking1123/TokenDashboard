#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(uname -s)" = Darwin
python3 tests/test_release.py
mkdir -p build/battery.iconset
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" assets/battery.png --out "build/battery.iconset/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" assets/battery.png --out "build/battery.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns build/battery.iconset -o build/battery.icns
python3 -m PyInstaller --noconfirm packaging/TokenDashboard-macOS.spec
codesign --verify --deep --strict dist/TokenDashboard.app
python3 -c "import subprocess; subprocess.run(['dist/TokenDashboard.app/Contents/MacOS/TokenDashboard', '--smoke-test'], check=True, timeout=30)"
arch=$(uname -m)
staging=$(mktemp -d build/package.XXXXXX)
package="$staging/TokenDashboard-macOS-${arch}"
mkdir -p "$package"
ditto dist/TokenDashboard.app "$package/TokenDashboard.app"
for file in README.md readme-header.svg requirements.txt src/*.py tests/*.py scripts/*.py scripts/*.ps1 scripts/*.sh packaging/*.spec assets/*.ico assets/*.png licenses/*.txt docs/*.md; do
    mkdir -p "$package/$(dirname "$file")"
    cp "$file" "$package/$file"
done
ditto -c -k --sequesterRsrc --keepParent "$package" "dist/TokenDashboard-macOS-${arch}.zip"
