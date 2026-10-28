"""Native Qt theme/settings regression; sample data only, no account queries.

Run ``python tests/test_themes.py`` or include with runpy in test_release.py.
The widgets remain off-screen and every settings file lives in a temporary folder.
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("dashboard_theme_tests", ROOT / "src/usage-dashboard.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

from PySide6.QtTest import QTest

THEMES = ("grass", "enchanting", "end")
LAYOUTS = ((False, False), (False, True), (True, True), (True, False))
SAMPLE = (
    {"account": {"planType": "plus"}},
    {"rateLimits": {
        "primary": {"windowDurationMins": 10080, "usedPercent": 28, "resetsAt": 1700000000},
        "secondary": {"windowDurationMins": 300, "usedPercent": 78, "resetsAt": 1700000000},
        "credits": {"unlimited": True},
    }},
    {"summary": {"lifetimeTokens": 1200000}},
)


def create_window(app):
    window = module.Dashboard(False)
    window.setAttribute(module.Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.surface.setGraphicsEffect(None)
    window.show()
    app.processEvents()
    assert window.worker is None
    assert not window.poller.isActive() and not window.timer.isActive()
    return window


def assert_controls_fit(window, context):
    controls = [control for control in window.surface.controls.values() if control.isVisible()]
    theme = window.surface.controls["theme"]
    assert theme in controls and theme.isEnabled() and theme.accessibleName(), context
    for index, control in enumerate(controls):
        assert window.surface.rect().contains(control.geometry()), (context, control.accessibleName())
        for other in controls[index + 1:]:
            assert not control.geometry().intersects(other.geometry()), (
                context, control.accessibleName(), other.accessibleName())


def check_layouts(app, settings):
    rendered = []
    for theme in THEMES:
        settings.write_text(json.dumps({"style": "minecraft-edition", "theme": theme,
                                        "grass_variant": "dark"}), encoding="utf-8")
        window = create_window(app)
        try:
            assert window.theme == theme
            assert isinstance(window.palette, dict) and {"text", "accent", "muted"} <= window.palette.keys()
            window.show_data(SAMPLE)
            window.move(800, 400)
            app.processEvents()
            anchor = (window.x() + window.width(), window.y())
            for minimal, five in LAYOUTS + ((False, False),):
                if window.minimal != minimal:
                    window.toggle_minimal()
                if window.show_five_hour != five:
                    window.surface.controls["five_hour"].click()
                app.processEvents()
                expected = (170, 274 if five else 182) if minimal else (280, 359 if five else 283)
                assert (window.width(), window.height()) == expected, (theme, minimal, five)
                assert (window.x() + window.width(), window.y()) == anchor, (theme, minimal, five)
                assert_controls_fit(window, (theme, minimal, five))
                assert window.week == 28 and window.five_hour == 78
                assert window.worker is None and not window.timer.isActive()
            image = module.QPixmap(window.size())
            image.fill(module.Qt.GlobalColor.transparent)
            window.render(image)
            rendered.append(image.toImage())
        finally:
            window.close()
    assert all(rendered[i] != rendered[j] for i in range(len(rendered))
               for j in range(i + 1, len(rendered))), "Theme selection must change the rendered widget"


def check_cycle_and_restart(app, settings):
    settings.write_text("{}", encoding="utf-8")
    window = create_window(app)
    try:
        assert window.theme == "grass" and window.grass_variant == "dark"
        window.show_data(SAMPLE)
        window.remaining = {"week": True, "five_hour": False}
        for minimal in (False, True):
            if window.minimal != minimal:
                window.toggle_minimal()
            app.processEvents()
            for expected in ("enchanting", "end", "grass"):
                control = window.surface.controls["theme"]
                assert_controls_fit(window, ("cycle", minimal, expected))
                QTest.mouseClick(control, module.Qt.MouseButton.LeftButton)
                app.processEvents()
                assert window.theme == expected, (minimal, expected, window.theme)
                assert window.data == SAMPLE and window.week == 28 and window.five_hour == 78
                saved = json.loads(settings.read_text(encoding="utf-8"))
                assert saved["style"] == "minecraft-edition" and saved["theme"] == expected
                assert saved["grass_variant"] == "dark" and saved["remaining_week"] is True
                restored = create_window(app)
                try:
                    assert restored.theme == expected and restored.grass_variant == "dark"
                    assert restored.remaining == {"week": True, "five_hour": False}
                finally:
                    restored.close()
    finally:
        window.close()


def check_migration(app, settings):
    for style in ("terminal-green", "block-craft"):
        for variant in ("dark", "light"):
            settings.write_text(json.dumps({
                "style": style, "theme": variant, "show_five_hour": True,
                "remaining_week": True, "remaining_five_hour": True,
            }), encoding="utf-8")
            window = create_window(app)
            try:
                assert window.theme == "grass" and window.grass_variant == variant, (style, variant)
                assert window.show_five_hour and window.height() == 359
                assert window.remaining == {"week": True, "five_hour": True}
                window.save_settings()
            finally:
                window.close()
            restored = create_window(app)
            try:
                assert restored.theme == "grass" and restored.grass_variant == variant
                assert restored.show_five_hour and restored.remaining["five_hour"]
            finally:
                restored.close()

    invalid = ([], None, "invalid", {},
               {"style": "minecraft-edition", "theme": []},
               {"style": "minecraft-edition", "theme": "missing"},
               {"style": "terminal-green", "theme": []},
               {"style": "block-craft", "theme": "missing"},
               {"style": "unknown", "theme": "end"},
               {"style": "minecraft-edition", "theme": "grass", "grass_variant": []})
    for saved in invalid:
        settings.write_text(json.dumps(saved), encoding="utf-8")
        window = create_window(app)
        try:
            assert window.theme == "grass" and window.grass_variant == "dark", saved
        finally:
            window.close()
    settings.write_text("{invalid json", encoding="utf-8")
    window = create_window(app)
    try:
        assert window.theme == "grass" and window.grass_variant == "dark"
    finally:
        window.close()


def run():
    app = module.QApplication.instance() or module.QApplication([])
    with tempfile.TemporaryDirectory(prefix="dashboard-themes-") as directory:
        settings = Path(directory) / "settings.json"
        with patch.object(module, "settings_path", return_value=settings), \
             patch.object(module, "read_usage", side_effect=AssertionError("Theme tests must not query an account")) as query:
            check_layouts(app, settings)
            check_cycle_and_restart(app, settings)
            check_migration(app, settings)
            settings.write_text('{}', encoding='utf-8')
            window = create_window(app)
            window.move(120, 130)
            app.processEvents()
            window.close()
            assert json.loads(settings.read_text(encoding='utf-8'))['position'] == [120, 130]
            restored = create_window(app)
            assert (restored.x(), restored.y()) == (120, 130)
            restored.close()
            settings.write_text(json.dumps({'position': [99999, 99999]}), encoding='utf-8')
            restored = create_window(app)
            assert (restored.x(), restored.y()) != (99999, 99999)
            restored.close()
            settings.write_text(json.dumps({'show_five_hour': True}), encoding='utf-8')
            window = create_window(app)
            window.move(120, 130)
            window.toggle_minimal()
            app.processEvents()
            position = (window.x(), window.y())
            window.close()
            restored = create_window(app)
            assert restored.minimal and (restored.width(), restored.height()) == (170, 274)
            assert (restored.x(), restored.y()) == position
            restored.toggle_minimal()
            restored.close()
            restored = create_window(app)
            assert not restored.minimal and (restored.width(), restored.height()) == (280, 359)
            restored.close()
            query.assert_not_called()
    print("PASS: three native themes, compact controls, dimensions/anchors, exact cycle/restart, legacy settings migration")


if __name__ == "__main__":
    run()
