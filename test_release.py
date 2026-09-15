"""Run with Python on the build PC to check dashboard behavior."""
import importlib.util
import json
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("dashboard", Path(__file__).parent / "usage-dashboard.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = module.QApplication([])
window = module.Dashboard(False)
temp = tempfile.TemporaryDirectory()
window.settings = Path(temp.name) / "usage-dashboard-settings.json"
window.show_five_hour = False
window.resize_anchored()
window.show_data(({}, {"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": 72}}}, {}))
assert window.week == 72
window.show_data(({}, {"rateLimitsByLimitId": {
    "codex": {"primary": {"windowDurationMins": 10080, "usedPercent": 28}},
    "codex_bengalfox": {"primary": {"windowDurationMins": 300, "usedPercent": 75}}
}}, {}))
assert window.week == 28 and window.five_hour == 75 and window.five_hour_label == "SPARK"
window.show_data(({}, {"rateLimits": {"primary": {"windowDurationMins": 300, "usedPercent": 91}}}, {}))
assert window.five_hour == 91 and window.five_hour_label == "CODEX"
window.results.put((None, "not logged in"))
window.poll()
assert window.week is None and window.five_hour is None and window.credits == "--" and window.tokens == "--"
window.show()
app.processEvents()
anchor = (window.x() + window.width(), window.y())
window.surface.controls['five_hour'].click()
app.processEvents()
assert window.height() == 359 and window.width() == 280
assert json.loads(window.settings.read_text())['show_five_hour'] is True
window.toggle_minimal()
app.processEvents()
assert window.height() == 274 and window.width() == 170
window.surface.controls['five_hour'].click()
app.processEvents()
assert window.height() == 182
assert json.loads(window.settings.read_text())['show_five_hour'] is False
controls = [c for c in window.surface.controls.values() if c.isVisible()]
for i, control in enumerate(controls):
    assert window.surface.rect().contains(control.geometry())
    assert all(not control.geometry().intersects(other.geometry()) for other in controls[i+1:])
window.toggle_minimal()
app.processEvents()
assert window.height() == 283
assert anchor == (window.x() + window.width(), window.y())
window.close()
for value in (0, 77, 95, 100, None):
    images = []
    for outline in (None, '#344C3A'):
        pix = module.QPixmap(120, 60)
        pix.fill(module.QColor('#DEE3D8'))
        painter = module.QPainter(pix)
        module.readout(painter, 10, value, '#245238', 5, center=60, outline=outline)
        painter.end()
        images.append(pix.toImage())
    before, after = images
    changes = 0
    for y in range(60):
        for x in range(120):
            if before.pixelColor(x,y).name() != '#dee3d8':
                assert before.pixelColor(x,y) == after.pixelColor(x,y)
            elif before.pixelColor(x,y) != after.pixelColor(x,y):
                assert after.pixelColor(x,y).name() == '#344c3a'
                changes += 1
    assert changes > 0
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
window.show(); window.minimal = False; window.show_five_hour = True
window.remaining = {'week': False, 'five_hour': False}
window.resize_anchored(); app.processEvents()
QTest.mouseDClick(window.surface, module.Qt.MouseButton.LeftButton, pos=QPoint(80, 92))
assert window.remaining == {'week': True, 'five_hour': False}
QTest.mouseDClick(window.surface, module.Qt.MouseButton.LeftButton, pos=QPoint(80, 168))
assert window.remaining == {'week': True, 'five_hour': True}
window.toggle_minimal(); app.processEvents()
QTest.mouseDClick(window.surface, module.Qt.MouseButton.LeftButton, pos=QPoint(80, 92))
assert window.remaining == {'week': False, 'five_hour': True}
QTest.mouseDClick(window.surface, module.Qt.MouseButton.LeftButton, pos=QPoint(80, 180))
assert window.remaining == {'week': False, 'five_hour': False}
QTest.mouseDClick(window.surface, module.Qt.MouseButton.LeftButton, pos=QPoint(80, 92))
QTest.mouseDClick(window.surface, module.Qt.MouseButton.LeftButton, pos=QPoint(80, 180))
assert window.remaining == {'week': True, 'five_hour': True}
assert json.loads(window.settings.read_text())['remaining_week'] is True
from unittest.mock import patch
with patch.object(module, 'pixel') as lettering:
    pix = module.QPixmap(120,60); painter = module.QPainter(pix)
    module.readout(painter, 10, 78, '#245238', 2, right=110, remaining=True)
    assert lettering.call_args.args[3] == '22%'
    lettering.reset_mock()
    for val in (0, 100):
        module.readout(painter, 10, val, '#245238', 2, right=110, remaining=True)
    assert not lettering.called  # Both endpoints use symbols, never 100%.
    module.readout(painter, 10, None, '#245238', 2, right=110, remaining=True)
    assert lettering.call_args.args[3] == '--'
    painter.end()
for reverse in (False, True):
    pix = module.QPixmap(120,30); pix.fill(module.QColor('#000000'))
    painter = module.QPainter(pix)
    module.meter(painter, 10, 5, 96, 12, 22, '#79F59B', reverse=reverse)
    painter.end(); img = pix.toImage()
    left = img.pixelColor(12, 12).name() == '#79f59b'
    right = img.pixelColor(101, 12).name() == '#79f59b'
    assert (left, right) == ((False, True) if reverse else (True, False))
window.close()
temp.cleanup()
print("PASS")
