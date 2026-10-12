"""Original, deterministic pixel art for the dashboard's block theme.

The artwork is painted locally with Qt rectangles.  It does not load game
assets, fonts, image files, or resources, and has no animation or I/O.
"""

from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap


def _fill(painter, x, y, width, height, color):
    if width > 0 and height > 0:
        painter.fillRect(QRectF(x, y, width, height), QColor(color))


def _step_path(x, y, width, height, step=3):
    """A square corner with one pixel-art step, rather than a rounded corner."""
    step = min(step, width / 4, height / 4)
    path = QPainterPath()
    path.moveTo(x + step, y)
    for px, py in (
        (x + width - step, y), (x + width - step, y + step),
        (x + width, y + step), (x + width, y + height - step),
        (x + width - step, y + height - step),
        (x + width - step, y + height), (x + step, y + height),
        (x + step, y + height - step), (x, y + height - step),
        (x, y + step), (x + step, y + step),
    ):
        path.lineTo(px, py)
    path.closeSubpath()
    return path


@lru_cache(maxsize=24)
def _dirt_pixels(width, height, minimal):
    """Cache geometry only; palette changes reuse exactly the same texture."""
    cell = 3 if minimal else 4
    cap = 11 if minimal else 14
    pixels = []
    for y in range(cap, height - 2, cell):
        for x in range(2, width - 2, cell):
            value = (x * 29 + y * 17 + (x // cell) * (y // cell) * 7) % 19
            if value in (0, 1, 3, 6, 11):
                size = cell if value in (0, 6) else max(1, cell - 1)
                pixels.append((x, y, min(size, width - 2 - x),
                               min(size, height - 2 - y), value % 2))
    return tuple(pixels)


@lru_cache(maxsize=24)
def _grass_pixels(width, minimal):
    cell = 3 if minimal else 4
    cap = 11 if minimal else 14
    pixels = []
    for index, x in enumerate(range(2, width - 2, cell)):
        length = (1 + (index * 7 + index // 3) % 3) * 2
        pixels.append((x, cap - 2, min(cell, width - 2 - x), length))
    return tuple(pixels)


def draw_frame(p, width, height, colors, minimal=False):
    """Paint the stepped grass-and-dirt casing inside the supplied bounds."""
    width, height = int(width), int(height)
    if width < 8 or height < 8:
        return
    c = colors
    cap = 11 if minimal else 14
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.fillPath(_step_path(0, 0, width, height, 4), QColor(c["border"]))
    p.setClipPath(_step_path(2, 2, width - 4, height - 4, 2),
                  Qt.ClipOperation.IntersectClip)
    _fill(p, 2, 2, width - 4, height - 4, c["bottom"])
    shades = (c["dirt_light"], c["dirt_dark"])
    for x, y, w, h, shade in _dirt_pixels(width, height, minimal):
        _fill(p, x, y, w, h, shades[shade])
    _fill(p, 2, 2, width - 4, cap - 2, c["grass"])
    _fill(p, 2, 2, width - 4, 2, c["bevel_light"])
    _fill(p, 2, cap - 4, width - 4, 3, c["grass_dark"])
    for index, (x, y, w, h) in enumerate(_grass_pixels(width, minimal)):
        _fill(p, x, y, w, h, c["grass_dark"] if index % 3 else c["grass"])
    # A few bright square grass flecks keep the cap legible at small sizes.
    for x in range(7, width - 4, 19 if minimal else 23):
        _fill(p, x, 5, 3, 2, c["accent"])
    _fill(p, 2, cap + 6, 2, max(0, height - cap - 10), c["dirt_light"])
    _fill(p, width - 4, cap + 3, 2, max(0, height - cap - 5), c["dirt_dark"])
    _fill(p, 2, height - 4, width - 4, 2, c["bevel_dark"])
    p.restore()


def draw_panel(p, rect, colors):
    """Opaque, inset inventory panel with a one-pixel dark inner lip."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    if w < 4 or h < 4:
        return
    c = colors
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    _fill(p, x, y, w, h, c["bevel_dark"])
    _fill(p, x + 1, y + 1, w - 1, h - 1, c["bevel_light"])
    _fill(p, x + 2, y + 2, w - 3, h - 3, c["panel"])
    _fill(p, x + 2, y + 2, w - 3, 1, c["line"])
    _fill(p, x + 2, y + 2, 1, h - 3, c["line"])
    p.restore()


def draw_button(p, rect, colors, pressed=False):
    """An original stone button, with its bevel reversed when pressed."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    if w < 4 or h < 4:
        return
    c = colors
    light, dark = c["bevel_light"], c["bevel_dark"]
    if pressed:
        light, dark = dark, light
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    _fill(p, x, y, w, h, c["border"])
    _fill(p, x + 1, y + 1, w - 2, h - 2,
          c["hover"] if pressed else c["button"])
    _fill(p, x + 1, y + 1, w - 2, 2, light)
    _fill(p, x + 1, y + 1, 2, h - 2, light)
    _fill(p, x + 2, y + h - 3, w - 3, 2, dark)
    _fill(p, x + w - 3, y + 2, 2, h - 3, dark)
    p.restore()


@lru_cache(maxsize=24)
def _xp_notches(width, height):
    """Small edge marks, without gaps through the continuous XP fill."""
    spacing = 12 if height >= 10 else 8
    return tuple(range(spacing, max(spacing, width - 3), spacing))


def draw_xp_bar(p, x, y, width, height, value, color, track, line, reverse=False):
    """Paint an XP-style trough; remaining amounts fill from the right.

    ``value`` is already the displayed used/remaining percentage.  None and
    zero paint an empty trough, while 100 fills its entire inner width.
    Only the fill anchor changes for ``reverse``; its amount is unchanged.
    """
    if width < 5 or height < 5:
        return
    fraction = 0.0 if value is None else max(0.0, min(1.0, float(value) / 100))
    fill = QColor(color)
    backdrop = QColor(track)
    edge = QColor(line)
    inner_x, inner_y = x + 2, y + 2
    inner_w, inner_h = width - 4, height - 4
    highlight_h = 2 if inner_h >= 8 else 1
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setClipRect(QRectF(x, y, width, height), Qt.ClipOperation.IntersectClip)
    p.fillPath(_step_path(x, y, width, height, 1), backdrop.darker(190))
    _fill(p, x + 1, y + 1, width - 2, height - 2, edge)
    _fill(p, inner_x, inner_y, inner_w, inner_h, backdrop)
    _fill(p, inner_x, inner_y, inner_w, 1, backdrop.darker(135))
    _fill(p, x + 1, y + height - 2, width - 2, 1, edge.lighter(115))
    if fraction:
        amount = inner_w * fraction
        start = inner_x + inner_w - amount if reverse else inner_x
        p.save()
        p.setClipRect(QRectF(start, inner_y, amount, inner_h),
                      Qt.ClipOperation.IntersectClip)
        _fill(p, inner_x, inner_y, inner_w, inner_h, fill)
        _fill(p, inner_x, inner_y, inner_w, highlight_h, fill.lighter(155))
        _fill(p, inner_x, inner_y + inner_h - 1, inner_w, 1, fill.darker(155))
        # Alternating short facets add square highlights without splitting
        # the bar into separately filled technical-gauge segments.
        for notch in _xp_notches(int(width), int(height)):
            _fill(p, inner_x + notch - 2, inner_y + highlight_h,
                  2, 1, fill.lighter(125))
        p.restore()
    for notch in _xp_notches(int(width), int(height)):
        _fill(p, inner_x + notch, inner_y, 1, 1, edge.darker(115))
        _fill(p, inner_x + notch, inner_y + inner_h - 1, 1, 1, edge.darker(115))
    p.restore()


def draw_slot(p, rect, colors):
    """Square recessed inventory slot, ready to hold a small painted icon."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    if w < 5 or h < 5:
        return
    c = colors
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setClipRect(rect, Qt.ClipOperation.IntersectClip)
    _fill(p, x, y, w, h, c["bevel_dark"])
    _fill(p, x + 1, y + 1, w - 1, h - 1, c["bevel_light"])
    _fill(p, x + 2, y + 2, w - 3, h - 3, c["track"])
    _fill(p, x + 2, y + 2, w - 3, 1, c["line"])
    _fill(p, x + 2, y + 2, 1, h - 3, c["line"])
    p.restore()


# Every glyph uses an original twelve-square grid.  The run cache avoids
# rebuilding a rectangle for each individual pixel on every paint event.
_ICONS = {
    "close": (
        "000000000000", "011000000110", "011100001110", "001110011100",
        "000111111000", "000011110000", "000011110000", "000111111000",
        "001110011100", "011100001110", "011000000110", "000000000000"),
    "minimize": (
        "000000000000", "000000000000", "000000000000", "000000000000",
        "000000000000", "011111111110", "011111111110", "000000000000",
        "000000000000", "000000000000", "000000000000", "000000000000"),
    "refresh": (
        "000000000000", "000111110100", "001111111100", "011000011100",
        "011000111100", "011000000000", "000000000110", "001111000110",
        "001110000110", "001111111100", "001011111000", "000000000000"),
    "toggle": (
        "000000000000", "011000000110", "001100001100", "000110011000",
        "011110011110", "011110011110", "000000000000", "011110011110",
        "011110011110", "000110011000", "001100001100", "011000000110"),
    "expand": (
        "011110011110", "011110011110", "011000000110", "011100001110",
        "010110011010", "000000000000", "000000000000", "010110011010",
        "011100001110", "011000000110", "011110011110", "011110011110"),
    "theme": (
        "000011110000", "000011110000", "010000000010", "001001100100",
        "000111111000", "110111111011", "110111111011", "000111111000",
        "001001100100", "010000000010", "000011110000", "000011110000"),
    "battery": (
        "000000000000", "000000000000", "011111111000", "011111111000",
        "010110001110", "010111001110", "010011101110", "010001101110",
        "011111111000", "011111111000", "000000000000", "000000000000"),
    "credits": (
        "000000000000", "000011110000", "001111111100", "011001100110",
        "011011110110", "011001100110", "001111111100", "000011110000",
        "001000000100", "001111111100", "000111111000", "000000000000"),
    "tokens": (
        "000001100000", "000011110000", "000111111000", "001110011100",
        "011100001110", "011001100110", "001101101100", "000110011000",
        "000011110000", "000001100000", "000000000000", "000000000000"),
}


@lru_cache(maxsize=len(_ICONS))
def _icon_runs(kind):
    runs = []
    for y, row in enumerate(_ICONS[kind]):
        start = None
        for x, bit in enumerate(row + "0"):
            if bit == "1" and start is None:
                start = x
            elif bit == "0" and start is not None:
                runs.append((start, y, x - start))
                start = None
    return tuple(runs)


def draw_icon(p, kind, box, color):
    """Paint a crisp icon and report whether its kind is supported."""
    if kind not in _ICONS:
        return False
    unit = max(1, int(min(box.width(), box.height()) // 12))
    x = int(box.x() + (box.width() - 12 * unit) / 2)
    y = int(box.y() + (box.height() - 12 * unit) / 2)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    for rx, ry, length in _icon_runs(kind):
        _fill(p, x + rx * unit, y + ry * unit, length * unit, unit, color)
    p.restore()
    return True


_RESOURCE_ART = {
    "credits": (
        "............", "...DDDDDD...", "..DLBBBBLD..", ".DLMMMMLLSD.",
        ".DLLLLLMMMD.", "..DLMMMMSD..", "..DSMMMMSD..", "...DLMMMD...",
        "....DMSD....", ".....DD.....", "............", "............",
    ),
    "tokens": (
        "............", "...DDDDDD...", "..DLBBBBSD..", "..DLMMMMSD..",
        "..DLMLMMSD..", "..DBMLMMSD..", "..DLMLMMSD..", "..DLMMMMSD..",
        "..DSMMMMSD..", "...DSSSSD...", "....DDDD....", "............",
    ),
}
_RESOURCE_COLORS = {
    "credits": dict(D="#236B77", L="#A6FFF1", B="#E4FFF8", M="#69E7DF", S="#2FADA9"),
    "tokens": dict(D="#275B39", L="#A5FF9E", B="#E1FFD2", M="#63E56C", S="#2B9F58"),
}


@lru_cache(maxsize=2)
def _resource_runs(kind):
    runs = []
    for y, row in enumerate(_RESOURCE_ART[kind]):
        start, previous = 0, row[0]
        for x, color in enumerate(row[1:] + ".", start=1):
            if color != previous:
                if previous != ".":
                    runs.append((start, y, x - start, previous))
                start, previous = x, color
    return tuple(runs)


def draw_resource_icon(p, kind, box):
    """Original twelve-pixel diamond/emerald facets for the resource slots.

    Credits use a wide cyan cut gem; tokens use a tall green cut gem.  Colors
    are intrinsic to the resources and stay consistent across app themes.
    """
    if kind not in _RESOURCE_ART or box.width() <= 0 or box.height() <= 0:
        return False
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    p.setClipRect(box, Qt.ClipOperation.IntersectClip)
    p.translate(box.x(), box.y())
    p.scale(box.width() / 12, box.height() / 12)
    colors = _RESOURCE_COLORS[kind]
    for x, y, width, color in _resource_runs(kind):
        _fill(p, x, y, width, 1, colors[color])
    p.restore()
    return True


def _paint_app_icon(p):
    """A grass block and emerald, drawn on an original 32-square canvas."""
    palette = {
        "border": "#202718", "bottom": "#765036", "grass": "#699D38",
        "grass_dark": "#3D692C", "accent": "#A0D554",
        "dirt_light": "#996B48", "dirt_dark": "#543C2D",
        "bevel_light": "#B1D66C", "bevel_dark": "#35291E",
    }
    draw_frame(p, 32, 32, palette, minimal=True)
    # Stepped silhouette and facets suggest a cut stone without any game art.
    _fill(p, 12, 10, 8, 2, "#142E20")
    _fill(p, 10, 12, 12, 12, "#142E20")
    _fill(p, 12, 24, 8, 2, "#142E20")
    _fill(p, 12, 12, 8, 2, "#B6FFD3")
    _fill(p, 11, 14, 10, 8, "#35D285")
    _fill(p, 13, 22, 6, 2, "#1B8F62")
    _fill(p, 13, 14, 3, 7, "#83F5B3")
    _fill(p, 18, 15, 3, 7, "#23AB75")
    _fill(p, 16, 21, 3, 3, "#1B8F62")
    _fill(p, 13, 14, 2, 2, "#E3FFEB")


def make_app_icon():
    """Create native icon sizes without runtime resources or smooth scaling."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.scale(size / 32, size / 32)
        _paint_app_icon(p)
        p.end()
        icon.addPixmap(pixmap)
    return icon
