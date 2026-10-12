"""Render the real widget with sample data, without querying an account."""

import argparse
import importlib.util
import os
import struct
import sys
import tempfile
from pathlib import Path

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication
from block_theme import make_app_icon
from block_typography import game_font


def write_icons():
    icon = make_app_icon()
    icon.pixmap(256, 256).scaled(1024, 1024, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.FastTransformation).save(str(ROOT / "assets/battery.png"))
    # ICO entries contain lossless PNGs at native icon sizes.
    entries, payloads = [], []
    sizes = (16, 24, 32, 48, 64, 128, 256)
    offset = 6 + 16 * len(sizes)
    for size in sizes:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        assert icon.pixmap(size, size).save(buffer, "PNG")
        payload = bytes(data)
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0,
                                   1, 32, len(payload), offset))
        payloads.append(payload)
        offset += len(payload)
    (ROOT / "assets/battery.ico").write_bytes(
        struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries + payloads))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/theme-preview")
    parser.add_argument("--scale", type=float, default=2)
    parser.add_argument("--write-icons", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.scale <= 3:
        parser.error("--scale must be between 1 and 3")
    app = QApplication([])
    if args.write_icons:
        write_icons()
    spec = importlib.util.spec_from_file_location("dashboard", ROOT / "src/usage-dashboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args.output.mkdir(parents=True, exist_ok=True)
    themes = ("grass", "enchanting", "end")
    labels = {"grass": "GRASS", "enchanting": "ENCHANTING TABLE", "end": "END PORTAL"}
    sheet = QPixmap(1200, 1260)
    sheet.fill(QColor("#15151E"))
    painter = QPainter(sheet)
    painter.setFont(game_font(10))
    with tempfile.TemporaryDirectory() as settings_dir:
        module.settings_path = lambda: Path(settings_dir) / "settings.json"
        window = module.Dashboard(False)
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        # Capture the widget itself without its soft decorative shadow.
        window.surface.setGraphicsEffect(None)
        window.grass_variant = "dark"
        for row, theme in enumerate(themes):
            for col, (minimal, five_hour) in enumerate(((False, False), (False, True), (True, False), (True, True))):
                window.theme, window.minimal, window.show_five_hour = theme, minimal, five_hour
                window.week, window.five_hour = 28, 78
                window.credits, window.tokens = "UNL", "1.2M"
                window.week_reset, window.five_hour_reset = "10월 14일 09:00 초기화", "10월 12일 12:30 초기화"
                window.surface.controls["five_hour"].setChecked(five_hour)
                window.resize_anchored()
                window.show()
                app.processEvents()
                image = QPixmap(round(window.width() * args.scale), round(window.height() * args.scale))
                image.setDevicePixelRatio(args.scale)
                image.fill(Qt.GlobalColor.transparent)
                window.render(image)
                name = f'{theme}-{"minimal" if minimal else "normal"}{"-5h" if five_hour else ""}'
                assert image.save(str(args.output / f"{name}.png"))
                x, y = col * 300, row * 420
                painter.setPen(QColor("#E0DCEB"))
                painter.drawText(x + 20, y + 26, name.upper())
                thumbnail = image.scaled(window.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.FastTransformation)
                thumbnail.setDevicePixelRatio(1)
                painter.drawPixmap(x + (300 - window.width()) // 2, y + 40, thumbnail)
        window.close()
    painter.end()
    assert sheet.save(str(args.output / "contact-sheet.png"))
    hero = QPixmap(1200, 650)
    hero.fill(QColor("#15151E"))
    painter = QPainter(hero)
    painter.setPen(QColor("#F1EAF9"))
    painter.setFont(game_font(18))
    painter.drawText(40, 42, "MINECRAFT THEMES / SAMPLE DATA")
    # Show the three normal widgets at the same 1.35x size, without stretching
    # their proportions or inflating the actual application windows.
    for col, theme in enumerate(themes):
        x = 11 + col * 400
        painter.drawImage(QRectF(x, 128, 378, 382.05),
                          QImage(str(args.output / f"{theme}-normal.png")))
        painter.setFont(game_font(13))
        painter.setPen(QColor("#E0DCEB"))
        painter.drawText(QRectF(col * 400, 86, 400, 28),
                         Qt.AlignmentFlag.AlignCenter, labels[theme])
    painter.setFont(game_font(12))
    painter.setPen(QColor("#BDB2CC"))
    painter.drawText(40, 587, "NORMAL: 280 x 283  /  MINIMAL: 170 x 182")
    painter.drawText(40, 614, "OPTIONAL 5H: +76 px NORMAL / +92 px MINIMAL")
    painter.end()
    assert hero.save(str(args.output / "preview.png"))
    print(f"Sample-data previews: {args.output}")


if __name__ == "__main__":
    main()
