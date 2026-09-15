import os
import sys
from pathlib import Path
import PySide6

root = Path(SPECPATH)
qt = Path(PySide6.__file__).parent
os.environ['PATH'] = os.pathsep.join([sys.prefix, str(Path(os.environ['SystemRoot']) / 'System32'), str(qt)])
a = Analysis([str(root / 'usage-dashboard.py')], pathex=[], binaries=[], datas=[], hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
a.binaries = [(name, str(qt / Path(name).name), kind)
              if Path(name).name.lower() in ('vcruntime140.dll', 'vcruntime140_1.dll')
              else (name, source, kind) for name, source, kind in a.binaries]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='CodexUsageDashboard', console=False, icon=[str(root / 'battery.ico')])
