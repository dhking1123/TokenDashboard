"""Bundled, open-license pixel typography. No system font installation or I/O beyond assets."""

from functools import lru_cache
from pathlib import Path
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import QApplication


@lru_cache(maxsize=1)
def load_game_fonts():
    if QApplication.instance() is None:
        raise RuntimeError("Create QApplication before loading pixel fonts")
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    families = []
    for filename in ("Monocraft.ttf", "Galmuri9.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(root / "assets/fonts" / filename))
        if font_id < 0:
            raise RuntimeError(f"Bundled font could not be loaded: {filename}")
        families.append(QFontDatabase.applicationFontFamilies(font_id)[0])
    return tuple(families)


def game_font(size=10, korean=False):
    latin, hangul = load_game_fonts()
    font = QFont()
    font.setFamilies([hangul, latin] if korean else [latin, hangul])
    font.setPixelSize(size)
    font.setKerning(False)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias | QFont.StyleStrategy.PreferNoShaping)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


@lru_cache(maxsize=256)
def glyph_runs(value):
    """Rasterize Monocraft once at its native 9px size, then scale square pixels."""
    font = game_font(9)
    metrics = QFontMetrics(font)
    advance = metrics.horizontalAdvance(value)
    image = QImage(max(1, advance + 2), metrics.height() + 2, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setFont(font)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(0, metrics.ascent(), value)
    painter.end()
    # Keep a stable seven-pixel cap-height origin for labels, numbers and punctuation.
    top = metrics.ascent() - metrics.capHeight()
    runs = []
    for y in range(image.height()):
        start = None
        for x in range(image.width() + 1):
            filled = x < image.width() and image.pixelColor(x, y).alpha() > 0
            if filled and start is None:
                start = x
            elif not filled and start is not None:
                runs.append((start, y - top, x - start))
                start = None
    return max(0, advance - 1), tuple(runs)


def draw_game_text(p, x, y, value, color, scale=1, center=None, right=None, shadow=True):
    width, runs = glyph_runs(str(value))
    if center is not None:
        x = center - width * scale / 2
    if right is not None:
        x = right - width * scale
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    if shadow:
        shade = QColor("#15170F") if shadow is True else QColor(shadow)
        for rx, ry, length in runs:
            p.fillRect(QRectF(x + rx * scale + 1, y + ry * scale + 1,
                             length * scale, scale), shade)
    brush = QColor(color)
    for rx, ry, length in runs:
        # QRectF retains fractional layout positions at 125/150% display scaling.
        p.fillRect(QRectF(x + rx * scale, y + ry * scale, length * scale, scale), brush)
    p.restore()
