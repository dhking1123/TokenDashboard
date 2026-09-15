"""Compare rendered pixels and warm frame times against a Git revision (no account access)."""
import argparse
import importlib.util
import itertools
import json
import os
import statistics
import subprocess
import time
import types
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", default="71be458", help="Original Git revision")
args = parser.parse_args()
original = subprocess.check_output(
    ["git", "show", f"{args.baseline}:usage-dashboard.py"], cwd=root).decode("utf-8")
old = types.ModuleType("baseline")
old.__file__ = str(root / "usage-dashboard.py")
exec(compile(original, old.__file__, "exec"), old.__dict__)
spec = importlib.util.spec_from_file_location("optimized", root / "src/usage-dashboard.py")
new = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new)
app = new.QApplication([])
with patch.object(Path, "read_text", return_value="{}"):
    windows = [module.Dashboard(False) for module in (old, new)]
for window in windows:
    window.surface.setGraphicsEffect(None)  # Measure widget drawing without platform shadows.
    window.show()
app.processEvents()
for window in windows:
    window.surface.clearFocus()

comparisons = 0
for theme, minimal, five, left, value, dpr in itertools.product(
        ("dark", "light"), (False, True), (False, True), (False, True),
        (None, 0, 28, 78, 95, 100), (1, 1.25, 1.5, 2)):
    images = []
    for module, window in zip((old, new), windows):
        window.theme, window.minimal, window.show_five_hour = theme, minimal, five
        window.remaining = {"week": left, "five_hour": left}
        window.surface.controls["five_hour"].setChecked(five)
        window.resize_anchored()
        window.show_data(({}, {"rateLimits": {
            "primary": {"windowDurationMins": 10080, "usedPercent": value},
            "secondary": {"windowDurationMins": 300, "usedPercent": value},
        }}, {}))
        app.processEvents()
        pixmap = module.QPixmap(round(window.width()*dpr), round(window.height()*dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(module.Qt.GlobalColor.transparent)
        window.render(pixmap)
        images.append(pixmap.toImage())
    assert images[0] == images[1], (theme, minimal, five, left, value, dpr)
    comparisons += 1

timings = {}
for theme in ("dark", "light"):
    for window, label in zip(windows, ("baseline", "optimized")):
        window.theme, window.minimal, window.show_five_hour = theme, False, True
        window.resize_anchored()
        window.week, window.five_hour = 78, 91
        app.processEvents()
        pixmap = new.QPixmap(window.size())
        for _ in range(10):
            window.render(pixmap)
        samples = []
        for _ in range(5):
            start = time.perf_counter()
            for _ in range(100):
                window.render(pixmap)
            samples.append((time.perf_counter()-start)*10)
        timings[f"{theme}_{label}_ms"] = round(statistics.median(samples), 3)
for window in windows:
    window.close()
result = {"baseline": args.baseline, "identical_scenes": comparisons, "timings": timings}
print(json.dumps(result, indent=2))
(root / "build").mkdir(exist_ok=True)
(root / "build/render-benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
