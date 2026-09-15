#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
test "$(uname -s)" = Darwin
python3 test_release.py
mkdir -p build/battery.iconset
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" battery.png --out "build/battery.iconset/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" battery.png --out "build/battery.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns build/battery.iconset -o build/battery.icns
python3 -m PyInstaller --noconfirm TokenDashboard-macOS.spec
codesign --verify --deep --strict dist/TokenDashboard.app
python3 -c "import subprocess; subprocess.run(['dist/TokenDashboard.app/Contents/MacOS/TokenDashboard', '--smoke-test'], check=True, timeout=30)"
arch=$(uname -m)
package="dist/TokenDashboard-macOS-${arch}"
mkdir -p "$package"
ditto dist/TokenDashboard.app "$package/TokenDashboard.app"
cp README-macOS.md THIRD_PARTY.txt GPL-3.0.txt LGPL-3.0.txt PYTHON-LICENSE.txt "$package/"
mkdir -p "$package/source"
cp usage-dashboard.py test_release.py TokenDashboard-macOS.spec build-macos.sh requirements.txt battery.png "$package/source/"
ditto -c -k --sequesterRsrc --keepParent "$package" "dist/TokenDashboard-macOS-${arch}.zip"
