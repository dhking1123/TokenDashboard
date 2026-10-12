"""Original, locally painted enchanting-table and End-portal themes.

No game textures, remote images, timers, or account data are used.  The book
and table are original 64-square artwork shared with the approved preview.
"""

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap, QPolygonF


__all__ = ["STATION_PALETTES", "draw_station_frame", "draw_enchanting_table",
           "draw_theme_icon"]


STATION_PALETTES = {
    "enchanting": dict(
        top="#1F1A2D", bottom="#14111E", text="#F7E9C6", muted="#B9A9C9",
        accent="#67E4D3", track="#0C1520", line="#473651", panel="#171321",
        border="#080912", button="#352A42", hover="#493650",
        bevel_light="#62506D", bevel_dark="#0A0A13",
        frame_light="#382A47", frame_dark="#120F1C", frame_red="#96313E",
        frame_cyan="#51C5C5", frame_cyan_light="#A3F8E8", star="#B5DED9",
    ),
    "end": dict(
        top="#0B1518", bottom="#080E15", text="#E6F1CB", muted="#A8BCB3",
        accent="#ACE68B", track="#071310", line="#354B43", panel="#0A1419",
        border="#17261F", button="#33483B", hover="#425B44",
        bevel_light="#78905D", bevel_dark="#0A1511",
        frame_light="#728452", frame_dark="#344B3A", frame_red="#87965B",
        frame_cyan="#65A38D", frame_cyan_light="#A0D6A1", star="#A7C6D1",
        eye_green="#6DB99B", eye_dark="#152C28", eye_light="#C6E2A8",
    ),
}


def _fill(p, x, y, width, height, color):
    if width > 0 and height > 0:
        p.fillRect(QRectF(x, y, width, height), QColor(color))


def _polygon(p, points, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))


def _outline(width, height, inset=0):
    x, y, w, h = inset, inset, width - 2 * inset, height - 2 * inset
    step = 2 if inset else 4
    path = QPainterPath()
    path.moveTo(x + step, y)
    for px, py in ((x + w - step, y), (x + w - step, y + step),
                   (x + w, y + step), (x + w, y + h - step),
                   (x + w - step, y + h - step), (x + w - step, y + h),
                   (x + step, y + h), (x + step, y + h - step),
                   (x, y + h - step), (x, y + step), (x + step, y + step)):
        path.lineTo(px, py)
    path.closeSubpath()
    return path


@lru_cache(maxsize=24)
def _stone_pixels(width, height, minimal):
    cell = 8 if minimal else 11
    return tuple((x, y, 2 + (x + y) % 4, 2 + (x * 3 + y) % 3,
                  (x // cell + y // cell) % 2)
                 for y in range(7, height - 4, cell)
                 for x in range(5, width - 4, cell)
                 if (x * 13 + y * 7) % 5 == 0)


@lru_cache(maxsize=24)
def _stars(width, height, minimal):
    """Static star positions, deliberately independent of time or randomness."""
    step = 17 if minimal else 23
    stars = []
    for row, y in enumerate(range(15, height - 10, step)):
        for column, x in enumerate(range(11, width - 9, step)):
            if (column * 3 + row * 5) % 4 == 0:
                stars.append((x + (row * 7) % 9, y + (column * 3) % 7,
                              2 if (column + row) % 3 == 0 else 1))
    return tuple(stars)


def _eye(p, x, y, width, height, c):
    """Stepped green eye, sized to stay entirely within a perimeter corner."""
    p.save()
    p.translate(x, y)
    p.scale(width / 12, height / 8)
    _fill(p, 2, 0, 8, 8, c["eye_dark"])
    _fill(p, 0, 2, 12, 4, c["eye_dark"])
    _fill(p, 2, 1, 8, 6, c["eye_green"])
    _fill(p, 1, 3, 10, 2, c["eye_green"])
    _fill(p, 3, 2, 6, 1, c["eye_light"])
    _fill(p, 5, 1, 2, 6, c["eye_dark"])
    _fill(p, 5, 2, 1, 1, c["eye_light"])
    p.restore()


def draw_station_frame(p, w, h, palette, theme, minimal=False):
    """Paint within a local surface's bounds, preserving painter state.

    Normal corner ornament ends before coordinate 14; compact ornament ends
    before coordinate 8.  Existing controls starting at 16/9 stay unobscured.
    This accepts the inner Surface size, rather than the outer window size.
    """
    w, h = int(w), int(h)
    if w < 16 or h < 16:
        return
    c = palette
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setClipRect(QRectF(0, 0, w, h), Qt.ClipOperation.IntersectClip)
    p.fillPath(_outline(w, h), QColor(c["border"]))
    p.setClipPath(_outline(w, h, 2), Qt.ClipOperation.IntersectClip)
    _fill(p, 2, 2, w - 4, h - 4, c["top"])
    if theme == "end":
        rim = 4 if minimal else 6
        _fill(p, 2, 2, w - 4, rim, c["frame_light"])
        _fill(p, 2, h - rim - 2, w - 4, rim, c["frame_dark"])
        _fill(p, 2, 2, rim, h - 4, c["frame_dark"])
        _fill(p, w - rim - 2, 2, rim, h - 4, c["frame_light"])
        _fill(p, rim + 2, rim + 2, w - 2 * rim - 4, h - 2 * rim - 4,
              c["bottom"])
        for x, y, size in _stars(w, h, minimal):
            _fill(p, x, y, size, size, c["star"] if size == 2 else c["line"])
        eye_w, eye_h = (6, 4) if minimal else (12, 8)
        for x, y in ((2, 2), (w - eye_w - 2, 2),
                     (2, h - eye_h - 2), (w - eye_w - 2, h - eye_h - 2)):
            _eye(p, x, y, eye_w, eye_h, c)
        _eye(p, (w - eye_w) // 2, 2, eye_w, eye_h, c)
        for x in range(16, w - 15, 15 if minimal else 24):
            _fill(p, x, 3, 3, 2, c["frame_cyan"])
            _fill(p, x + 3, h - 5, 3, 2, c["frame_red"])
    else:
        shades = (c["frame_light"], c["frame_dark"])
        for x, y, pw, ph, shade in _stone_pixels(w, h, minimal):
            _fill(p, x, y, pw, ph, shades[shade])
        _fill(p, 2, 2, w - 4, 3, c["frame_red"])
        _fill(p, 2, h - 5, w - 4, 3, c["frame_red"])
        _fill(p, 2, 5, 2, h - 10, c["frame_light"])
        _fill(p, w - 4, 5, 2, h - 10, c["frame_dark"])
        size, corner_y = (3, 5) if minimal else (6, 8)
        for x, y in ((4, corner_y), (w - size - 4, corner_y),
                     (4, h - size - 5), (w - size - 4, h - size - 5)):
            _fill(p, x, y, size, size, c["frame_cyan"])
            _fill(p, x, y, max(1, size // 2), max(1, size // 2),
                  c["frame_cyan_light"])
    p.restore()


@lru_cache(maxsize=1)
def _table_pixmap():
    """Create the original preview illustration once, after QApplication."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    pieces = (
        ([(6,36),(31,26),(58,36),(33,47)], "#B33242"),
        ([(10,36),(31,29),(54,36),(33,44)], "#3B283E"),
        ([(6,36),(33,47),(33,62),(6,51)], "#191727"),
        ([(33,47),(58,36),(58,51),(33,62)], "#282139"),
        ([(6,36),(33,47),(33,50),(6,39)], "#862532"),
        ([(33,47),(58,36),(58,39),(33,50)], "#D74750"),
        ([(8,40),(14,42),(14,50),(8,48)], "#5AE6D2"),
        ([(25,47),(31,50),(31,58),(25,55)], "#37B9BE"),
        ([(35,50),(41,47),(41,55),(35,58)], "#6BEFE1"),
        ([(50,42),(56,40),(56,48),(50,51)], "#4BC6C5"),
        ([(8,40),(11,41),(11,45),(8,44)], "#B2FFF0"),
        ([(35,50),(38,49),(38,52),(35,53)], "#B2FFF0"),
        ([(10,12),(26,14),(32,19),(37,14),(53,11),(54,22),
          (37,27),(32,31),(26,27),(10,22)], "#A82536"),
        ([(12,9),(26,12),(32,17),(32,28),(25,24),(12,20)], "#F4E2B0"),
        ([(32,17),(38,12),(51,9),(52,20),(38,24),(32,28)], "#D5BE8D"),
        ([(31,17),(33,17),(33,28),(31,28)], "#9B764D"),
        ([(14,12),(25,15),(28,17),(28,18),(24,17),(14,14)], "#BA9C6F"),
        ([(14,16),(24,19),(28,21),(28,22),(23,21),(14,18)], "#BA9C6F"),
        ([(36,17),(40,15),(49,12),(49,14),(40,17),(36,19)], "#927252"),
        ([(36,21),(41,18),(50,16),(50,18),(41,20),(36,23)], "#927252"),
    )
    for points, color in pieces:
        _polygon(p, points, color)
    for x, y, w, h, color in (
        (17,47,4,3,"#3E2D4E"), (20,54,3,2,"#3E2D4E"),
        (42,48,5,3,"#4A3459"), (4,10,2,6,"#D5BD84"),
        (6,10,3,2,"#D5BD84"), (4,14,3,2,"#D5BD84"),
        (56,4,2,7,"#B9DFD6"), (54,6,6,2,"#B9DFD6"),
        (55,11,2,2,"#B9DFD6"),
    ):
        _fill(p, x, y, w, h, color)
    p.end()
    return pixmap


def draw_enchanting_table(p, box):
    """Draw the cached square table illustration, with nearest-pixel scaling."""
    side = min(box.width(), box.height())
    if side <= 0:
        return
    target = QRectF(box.x() + (box.width() - side) / 2,
                    box.y() + (box.height() - side) / 2, side, side)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    p.setClipRect(box, Qt.ClipOperation.IntersectClip)
    p.drawPixmap(target, _table_pixmap(), QRectF(0, 0, 64, 64))
    p.restore()


def draw_theme_icon(p, box, theme):
    """Paint an original grass, book, or eye icon for the existing cycle button."""
    if box.width() <= 0 or box.height() <= 0:
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setClipRect(box, Qt.ClipOperation.IntersectClip)
    p.translate(box.x(), box.y())
    p.scale(box.width() / 16, box.height() / 16)
    if theme == "end":
        _eye(p, 1, 3, 14, 10, STATION_PALETTES["end"])
    elif theme == "enchanting":
        _polygon(p, [(1,3),(6,4),(8,6),(10,4),(15,3),(15,11),
                     (10,12),(8,14),(6,12),(1,11)], "#B63044")
        _polygon(p, [(2,2),(6,3),(8,5),(8,12),(6,10),(2,9)], "#F3E1B1")
        _polygon(p, [(8,5),(10,3),(14,2),(14,9),(10,10),(8,12)], "#D6BE8E")
        _fill(p, 7, 5, 2, 8, "#9A764F")
        _fill(p, 3, 5, 3, 1, "#BA9C6F")
        _fill(p, 10, 5, 3, 1, "#927252")
    else:
        _fill(p, 2, 6, 12, 8, "#765036")
        _fill(p, 2, 4, 12, 4, "#699D38")
        _fill(p, 2, 4, 12, 1, "#B1D66C")
        _fill(p, 2, 7, 3, 3, "#3D692C")
        _fill(p, 8, 7, 3, 2, "#3D692C")
        _fill(p, 4, 11, 2, 2, "#996B48")
        _fill(p, 10, 10, 2, 2, "#543C2D")
    p.restore()
