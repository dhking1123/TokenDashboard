from pathlib import Path
import platform

root = Path(SPECPATH)
a = Analysis([str(root / 'usage-dashboard.py')], pathex=[], binaries=[], datas=[],
             hiddenimports=[], hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='TokenDashboard',
          console=False, target_arch=platform.machine(), codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name='TokenDashboard')
app = BUNDLE(coll, name='TokenDashboard.app', icon=str(root / 'build/battery.icns'),
             bundle_identifier='io.github.dhking1123.tokendashboard',
             info_plist={'CFBundleShortVersionString': '5.1.0',
                         'CFBundleVersion': '5.1.0',
                         'NSHighResolutionCapable': True,
                         'LSMinimumSystemVersion': '13.0'})
