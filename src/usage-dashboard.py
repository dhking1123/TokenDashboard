import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path


def find_codex():
    codex = shutil.which("codex")
    if codex:
        return codex
    if sys.platform == "darwin":
        # Finder apps do not inherit the shell's Homebrew/npm PATH.
        candidates = [Path("/Applications/Codex.app/Contents/Resources/codex"),
                      Path.home() / "Applications/Codex.app/Contents/Resources/codex",
                      Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex"),
                      Path.home() / ".local/bin/codex"]
        return next((str(path) for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)
    if not codex:
        candidates = list((Path.home() / "AppData/Local/OpenAI/Codex/bin").glob("*/codex.exe"))
        codex = str(max(candidates, key=lambda path: path.stat().st_mtime)) if candidates else None
    return codex


def settings_path():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent / "usage-dashboard-settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/TokenDashboard/settings.json"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "CodexUsageDashboard/settings.json"


def read_usage():
    codex = find_codex()
    if not codex:
        raise RuntimeError("Codex 실행 파일을 찾을 수 없습니다. Codex 앱 또는 CLI 설치를 확인하세요.")

    process = subprocess.Popen(
        [codex, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    messages = queue.Queue()

    def read_lines():
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict):
                    messages.put(message)
        except (OSError, UnicodeError):
            pass
        finally:
            messages.put(None)

    reader = threading.Thread(target=read_lines, daemon=True)
    reader.start()

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    results = {}
    deadline = time.monotonic() + 15

    def receive(pending):
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise queue.Empty
            message = messages.get(timeout=remaining)
            if message is None:
                raise RuntimeError("Codex 사용량 조회 연결이 종료되었습니다.")
            request_id = message.get("id")
            if type(request_id) is int and request_id in pending:
                if "error" in message:
                    error = message["error"]
                    if not isinstance(error, dict):
                        raise RuntimeError("Codex 조회 오류 응답 형식이 올바르지 않습니다.")
                    # Older CLIs may not expose token totals; quota data is still usable.
                    unsupported = error.get("code") == -32601 or (
                        error.get("code") == -32600 and
                        "unknown variant `account/usage/read`" in str(error.get("message", "")))
                    if request_id == 3 and unsupported:
                        results[request_id] = {}
                        pending.remove(request_id)
                        continue
                    raise RuntimeError(error.get("message") or "조회 실패")
                result = message.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("Codex 조회 응답 형식이 올바르지 않습니다.")
                results[request_id] = result
                pending.remove(request_id)

    try:
        send({"method": "initialize", "id": 0, "params": {"clientInfo": {
            "name": "local_usage_dashboard", "title": "Local Usage Dashboard", "version": "1.0.0"
        }}})
        receive({0})
        send({"method": "initialized", "params": {}})
        send({"method": "account/read", "id": 1, "params": {"refreshToken": False}})
        send({"method": "account/rateLimits/read", "id": 2, "params": {}})
        send({"method": "account/usage/read", "id": 3, "params": {}})
        receive({1, 2, 3})
    except queue.Empty:
        raise RuntimeError("Codex 사용량 조회 시간이 초과되었습니다.") from None
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        reader.join(timeout=2)
        process.stdout.close()
    return results[1], results[2], results[3]


def format_number(value):
    return f"{int(value or 0):,}"


def format_reset(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%m월 %d일 %H:%M") if timestamp else "정보 없음"


from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QLinearGradient, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QGraphicsDropShadowEffect, QVBoxLayout

PALETTES = {
    "light": dict(top="#F0EEE4", bottom="#D4D5CA", text="#245238", muted="#526B56",
                  line="#9EAD9E", accent="#245238", track="#CAD2C7",
                  panel="#DEE3D8", border="#FAFAF1", button="#E1E3D8", hover="#C3D6C0"),
    "dark": dict(top="#252925", bottom="#1A1E1B", text="#79F59B", muted="#789A80",
                 line="#344C3A", accent="#79F59B", track="#101D13",
                 panel="#080F0B", border="#59605A", button="#202921", hover="#304737"),
}


def text(p, x, y, width, height, value, color, size=17, bold=False, right=False, center=False):
    font = QFont("Segoe UI")
    font.setFamilies(["Helvetica Neue", "Apple SD Gothic Neo"] if sys.platform == "darwin" else ["Segoe UI", "Malgun Gothic"])
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(QRectF(x, y, width, height),
               Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignHCenter if center else Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft), str(value))


def icon(p, kind, box, color):
    p.save()
    p.translate(box.x(), box.y())
    p.scale(box.width() / 24, box.height() / 24)
    p.setPen(QPen(QColor(color), 1.55, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "close":
        p.drawLine(QPointF(5, 5), QPointF(19, 19)); p.drawLine(QPointF(19, 5), QPointF(5, 19))
    elif kind == "minimize":
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
    elif kind == "refresh":
        p.drawArc(QRectF(4, 4, 16, 16), 35 * 16, 140 * 16)
        p.drawArc(QRectF(4, 4, 16, 16), 215 * 16, 140 * 16)
        p.drawPolyline([QPointF(3, 5), QPointF(3, 11), QPointF(9, 11)])
        p.drawPolyline([QPointF(21, 19), QPointF(21, 13), QPointF(15, 13)])
    elif kind in ("expand", "toggle"):
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            near = QPointF(12+sx*3, 12+sy*3)
            far = QPointF(12+sx*9, 12+sy*9)
            p.drawLine(near, far)
            tip = far if kind == "expand" else near
            direction = -1 if kind == "expand" else 1
            p.drawLine(tip, QPointF(tip.x()+direction*sx*4, tip.y()))
            p.drawLine(tip, QPointF(tip.x(), tip.y()+direction*sy*4))
    elif kind == "theme":
        p.drawEllipse(QRectF(7, 7, 10, 10))
        for x, y, ex, ey in ((12,1,12,4),(12,20,12,23),(1,12,4,12),(20,12,23,12),
                             (4,4,6,6),(18,18,20,20),(4,20,6,18),(18,6,20,4)):
            p.drawLine(QPointF(x,y), QPointF(ex,ey))
    elif kind == "credits":
        p.drawEllipse(QRectF(5, 3, 14, 6))
        p.drawLine(QPointF(5, 6), QPointF(5, 19))
        p.drawLine(QPointF(19, 6), QPointF(19, 19))
        p.drawArc(QRectF(5, 10, 14, 6), 180 * 16, 180 * 16)
        p.drawArc(QRectF(5, 16, 14, 6), 180 * 16, 180 * 16)
    elif kind == "tokens":
        p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.DotLine))
        p.drawEllipse(QRectF(3, 3, 18, 18))
        p.setPen(QPen(QColor(color), 1.4))
        p.drawRoundedRect(QRectF(8, 8, 8, 8), 2, 2)
    elif kind == "battery":
        p.drawRect(QRectF(1, 5, 19, 14))
        p.fillRect(QRectF(20, 9, 3, 6), QColor(color))
        text(p, 2, 5, 17, 14, "$$", color, 12, True, center=True)
    p.restore()


# Bitmap lettering keeps the terminal face crisp at every display scale.
GLYPHS = dict(zip(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%./:-$ ",
    [
        "01110/10001/10001/11111/10001/10001/10001","11110/10001/10001/11110/10001/10001/11110",
        "01111/10000/10000/10000/10000/10000/01111","11110/10001/10001/10001/10001/10001/11110",
        "11111/10000/10000/11110/10000/10000/11111","11111/10000/10000/11110/10000/10000/10000",
        "01111/10000/10000/10111/10001/10001/01111","10001/10001/10001/11111/10001/10001/10001",
        "11111/00100/00100/00100/00100/00100/11111","00111/00010/00010/00010/10010/10010/01100",
        "10001/10010/10100/11000/10100/10010/10001","10000/10000/10000/10000/10000/10000/11111",
        "10001/11011/10101/10101/10001/10001/10001","10001/11001/10101/10011/10001/10001/10001",
        "01110/10001/10001/10001/10001/10001/01110","11110/10001/10001/11110/10000/10000/10000",
        "01110/10001/10001/10001/10101/10010/01101","11110/10001/10001/11110/10100/10010/10001",
        "01111/10000/10000/01110/00001/00001/11110","11111/00100/00100/00100/00100/00100/00100",
        "10001/10001/10001/10001/10001/10001/01110","10001/10001/10001/10001/10001/01010/00100",
        "10001/10001/10001/10101/10101/10101/01010","10001/10001/01010/00100/01010/10001/10001",
        "10001/10001/01010/00100/00100/00100/00100","11111/00001/00010/00100/01000/10000/11111",
        "01110/10001/10011/10101/11001/10001/01110","00100/01100/00100/00100/00100/00100/01110",
        "01110/10001/00001/00010/00100/01000/11111","11110/00001/00001/01110/00001/00001/11110",
        "00010/00110/01010/10010/11111/00010/00010","11111/10000/10000/11110/00001/00001/11110",
        "01110/10000/10000/11110/10001/10001/01110","11111/00001/00010/00100/01000/01000/01000",
        "01110/10001/10001/01110/10001/10001/01110","01110/10001/10001/01111/00001/00001/01110",
        "11001/11010/00010/00100/01000/01011/10011","00000/00000/00000/00000/00000/00100/00100",
        "00001/00010/00010/00100/01000/01000/10000","00000/00100/00100/00000/00100/00100/00000",
        "00000/00000/00000/11111/00000/00000/00000","00100/01111/10100/01110/00101/11110/00100",
        "00000/00000/00000/00000/00000/00000/00000",
    ]))


GLYPHS[","] = "00000/00000/00000/00000/00100/00100/01000"
GLYPHS["s"] = "00000/00000/01111/10000/01110/00001/11110"


@lru_cache(maxsize=256)
def pixel_rects(x, y, value, scale):
    return tuple(QRectF(x+(i*6+col)*scale, y+row*scale, scale, scale)
                 for i, char in enumerate(value)
                 for row, bits in enumerate(GLYPHS.get(char, GLYPHS.get(char.upper(), GLYPHS[" "])).split("/"))
                 for col, bit in enumerate(bits) if bit == "1")


def pixel(p, x, y, value, color, scale=2, center=None, right=None):
    value = str(value)
    width = (len(value)*6-1)*scale
    if center is not None:
        x = center-width/2
    if right is not None:
        x = right-width
    p.save(); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    brush = QColor(color)
    for rect in pixel_rects(x, y, value, scale):
        p.fillRect(rect, brush)
    p.restore()


@lru_cache(maxsize=8)
def grain_rects(width, height):
    return tuple((QRectF(x, y, 1, 1), QColor(180, 200, 180, 10 if (x+y)%3 else 18))
                 for y in range(5, height, 4) for x in range(5, width, 7))


def bevel(p, rect, fill, inset=False):
    p.fillRect(rect, QColor(fill))
    light, dark = ("#FCFCF5", "#969E92") if QColor(fill).lightness() > 128 else ("#4D524E", "#080A09")
    if inset:
        light, dark = dark, light
    p.setPen(QPen(QColor(light), 2))
    p.drawLine(rect.topLeft(), rect.topRight()); p.drawLine(rect.topLeft(), rect.bottomLeft())
    p.setPen(QPen(QColor(dark), 2))
    p.drawLine(rect.bottomLeft(), rect.bottomRight()); p.drawLine(rect.topRight(), rect.bottomRight())


def usage_color(value, green):
    return "#FF5055" if value is not None and value >= 90 else "#F4D84B" if value is not None and value >= 70 else green


def readout(p, y, value, green, scale, center=None, right=None, outline=None, solid=None, remaining=False):
    if outline:
        for dx, dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
            p.save(); p.translate(dx, dy)
            readout(p, y, value, green, scale, center=center, right=right, solid=outline, remaining=remaining)
            p.restore()
    color = solid or usage_color(value, green)
    if value is None or (value < 100 and not (remaining and value == 0)):
        shown = None if value is None else (100-value if remaining else value)
        pixel(p, 0, y, "--" if shown is None else f"{min(99, int(shown))}%",
              color, scale, center=center, right=right)
        return
    # Match the lock height to the seven-row numeric readout.
    rows = ("001111100", "011000110", "010000010", "010000010",
            "111111111", "111101111", "111000111", "111101111", "111111111")
    if remaining and value == 0:
        rows = ("000000001", "000000011", "000000110", "000001100",
                "100011000", "110110000", "011100000", "001000000", "000000000")
    step = 7*scale/9
    x = center-3.5*scale if center is not None else right-7*scale
    for row, bits in enumerate(rows):
        for col, bit in enumerate(bits):
            if bit == "1":
                p.fillRect(QRectF(x+col*step, y+row*step, step, step), QColor(color))


def meter(p, x, y, width, height, value, color, track="#101D13", line="#27432C", reverse=False):
    if reverse:
        p.save(); p.translate(2*x+width-3, 0); p.scale(-1, 1)
        meter(p, x, y, width, height, value, color, track, line)
        p.restore()
        return
    count = min(24, max(1, int(width//8)))
    for i in range(count):
        cell = width/count
        rect = QRectF(x+i*cell, y, cell-3, height)
        p.fillRect(rect, QColor(track))
        p.setPen(QPen(QColor(line), 1)); p.drawRect(rect)
        fraction = 0 if value is None else max(0, min(1, value/100*count-i))
        if fraction:
            p.fillRect(QRectF(rect.x()+1, rect.y()+1, (rect.width()-2)*fraction, height-2), QColor(color))
            p.fillRect(QRectF(rect.x()+2, rect.y()+2, max(0,(rect.width()-4)*fraction), 2), QColor(color).lighter(125))


def battery_icon():
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size); pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(size/64, size/64)
        p.setBrush(QColor("#151B17")); p.setPen(QPen(QColor("#73EF92"), 3))
        p.drawRoundedRect(QRectF(3, 13, 51, 38), 5, 5)
        p.fillRect(QRectF(55, 25, 7, 14), QColor("#73EF92"))
        pixel(p, 0, 22, "$$", "#86FFA3", 3, center=28)
        p.end(); result.addPixmap(pixmap)
    return result


class Control(QPushButton):
    def __init__(self, owner, kind, label, callback):
        super().__init__(owner)
        self.owner, self.kind = owner, kind
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(callback)
        if kind == "five_hour":
            self.setCheckable(True)
            self.setChecked(owner.app.show_five_hour)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = PALETTES[self.owner.app.theme]
        active = self.underMouse() or self.hasFocus()
        if self.kind == "five_hour":
            if not self.owner.app.minimal:
                pixel(p, 2, 8, "5H", c["text"], 1.3)
            x = self.width()-29
            bevel(p, QRectF(x, 5, 27, 13), c["hover"] if active else c["track"], True)
            p.fillRect(QRectF(x+(15 if self.isChecked() else 3), 7, 9, 9),
                       QColor(c["accent"] if self.isChecked() else c["muted"]))
            if self.hasFocus():
                p.setPen(QPen(QColor(c["accent"]), 1, Qt.PenStyle.DotLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(self.rect()).adjusted(1, 1, -2, -2))
            return
        bevel(p, QRectF(self.rect()).adjusted(2, 2, -2, -2),
              c["hover"] if active else c["button"], self.isDown())
        if active:
            p.setPen(QPen(QColor(c["accent"]), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(self.rect()).adjusted(2, 2, -3, -3))
        size = min(22, self.width()-6, self.height()-6)
        icon(p, self.kind, QRectF((self.width()-size)/2, (self.height()-size)/2, size, size), c["text"])


class Surface(QWidget):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.controls = {}
        for kind, label, callback in (
            ("minimize", "최소화", app.showMinimized), ("close", "닫기", app.close),
            ("theme", "화이트 / 다크 모드 전환", app.toggle_theme),
            ("refresh", "사용량 새로고침", app.refresh),
            ("toggle", "미니멀 모드", app.toggle_minimal),
            ("expand", "일반 모드로 확장", app.toggle_minimal),
            ("five_hour", "5시간 사용량 표시 / 숨기기", app.toggle_five_hour),
        ):
            self.controls[kind] = Control(self, kind, label, callback)

    def resizeEvent(self, event):
        w = self.width()
        positions = {"minimize": (w-74, 16, 24, 24), "close": (w-44, 16, 24, 24)}
        if self.app.minimal:
            positions = dict(expand=(w-82, 9, 20, 20), minimize=(w-58, 9, 20, 20),
                             close=(w-34, 9, 20, 20), five_hour=(14, 8, 30, 24))
        else:
            extra = 76 if self.app.show_five_hour else 0
            positions.update(theme=(w-55, 195+extra, 28, 28), refresh=(w-91, 195+extra, 28, 28),
                             toggle=(w-104, 16, 24, 24), five_hour=(58, 16, 54, 24))
        for kind, control in self.controls.items():
            control.setVisible(kind in positions)
            if kind in positions:
                control.setGeometry(*positions[kind])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < (38 if self.app.minimal else 44):
            self.app.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            regions = (("week", 40), ("five_hour", 134)) if self.app.minimal else (("week", 58), ("five_hour", 134))
            for key, y in regions:
                if key == "five_hour" and not self.app.show_five_hour:
                    continue
                if QRectF(18, y, self.width()-36, 90 if self.app.minimal else 47).contains(event.position()):
                    self.app.remaining[key] = not self.app.remaining[key]
                    self.app.save_settings()
                    self.app.repaint_all()
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        c = PALETTES[self.app.theme]
        green = c["accent"]
        outline = "#344C3A" if self.app.theme == "light" else None
        casing = c["top"]
        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0, QColor(casing)); gradient.setColorAt(.5, QColor(c["bottom"]))
        gradient.setColorAt(1, QColor(casing))
        path = QPainterPath()
        path.moveTo(12, 2); path.lineTo(w-12, 2); path.lineTo(w-2, 12)
        path.lineTo(w-2, h-12); path.lineTo(w-12, h-2); path.lineTo(12, h-2)
        path.lineTo(2, h-12); path.lineTo(2, 12); path.closeSubpath()
        p.setBrush(gradient); p.setPen(QPen(QColor(c["border"]), 2)); p.drawPath(path)
        p.save(); p.setClipPath(path)
        # Deterministic fine metal grain; never covers the display lettering.
        for rect, color in grain_rects(w, h):
            p.fillRect(rect, color)
        p.restore()
        if self.app.minimal:
            bevel(p, QRectF(12, 39, w-24, 92+(92 if self.app.show_five_hour else 0)), c["panel"], True)
            pixel(p, 0, 51, "WEEK/CODEX", green, 1.3, center=w/2)
            left = self.app.remaining["week"]
            pixel(p, 0, 63, "LEFT" if left else "USED", c["muted"], 1, center=w/2)
            readout(p, 73, self.app.week, green, 5, center=w/2, outline=outline, remaining=left)
            amount = None if self.app.week is None else (100-self.app.week if left else self.app.week)
            meter(p, (w-92)/2, 116, 92, 8, amount, usage_color(self.app.week, green), c["track"], c["line"], reverse=left)
            if self.app.show_five_hour:
                p.setPen(QPen(QColor(c["line"]), 1))
                p.drawLine(QPointF(20, 132), QPointF(w-20, 132))
                pixel(p, 0, 143, "5H/"+self.app.five_hour_label, green, 1.3, center=w/2)
                left = self.app.remaining["five_hour"]
                pixel(p, 0, 155, "LEFT" if left else "USED", c["muted"], 1, center=w/2)
                readout(p, 165, self.app.five_hour, green, 5, center=w/2, outline=outline, remaining=left)
                amount = None if self.app.five_hour is None else (100-self.app.five_hour if left else self.app.five_hour)
                meter(p, (w-92)/2, 208, 92, 8, amount, usage_color(self.app.five_hour, green), c["track"], c["line"], reverse=left)
            return
        for x, y in ((10, 9), (w-10, 9), (10, h-10), (w-10, h-10)):
            p.setBrush(QColor(c["button"])); p.setPen(QPen(QColor(c["line"]), 1))
            p.drawEllipse(QPointF(x, y), 3, 3)
            p.drawLine(QPointF(x-1, y+1), QPointF(x+1, y-1))
        icon(p, "battery", QRectF(20, 16, 27, 24), green)
        extra = 76 if self.app.show_five_hour else 0
        bevel(p, QRectF(12, 51, w-24, 132+extra), c["panel"], True)
        pixel(p, 22, 65, "WEEK / CODEX", green, 1.5)
        left = self.app.remaining["week"]
        readout(p, 64, self.app.week, green, 2, right=w-24, outline=outline, remaining=left)
        amount = None if self.app.week is None else (100-self.app.week if left else self.app.week)
        meter(p, 22, 87, w-45, 15, amount, usage_color(self.app.week, green), c["track"], c["line"], reverse=left)
        pixel(p, 22, 110, "LEFT" if left else "USED", c["muted"], 1)
        text(p, 22, 105, w-46, 16, self.app.week_reset, c["muted"], 10, right=True)
        p.setPen(QPen(QColor(c["line"]), 1))
        p.drawLine(QPointF(13, 126), QPointF(w-13, 126))
        if self.app.show_five_hour:
            pixel(p, 22, 141, "5H / "+self.app.five_hour_label, green, 1.5)
            left = self.app.remaining["five_hour"]
            readout(p, 140, self.app.five_hour, green, 2, right=w-24, outline=outline, remaining=left)
            amount = None if self.app.five_hour is None else (100-self.app.five_hour if left else self.app.five_hour)
            meter(p, 22, 163, w-45, 15, amount, usage_color(self.app.five_hour, green), c["track"], c["line"], reverse=left)
            pixel(p, 22, 186, "LEFT" if left else "USED", c["muted"], 1)
            text(p, 22, 181, w-46, 16, self.app.five_hour_reset, c["muted"], 10, right=True)
            p.setPen(QPen(QColor(c["line"]), 1))
            p.drawLine(QPointF(13, 202), QPointF(w-13, 202))
        p.translate(0, extra)
        p.drawLine(QPointF(w/2, 126), QPointF(w/2, 182))
        pixel(p, 0, 138, "CREDITS", green, 1.3, center=w/4+6)
        pixel(p, 0, 159, self.app.credits, green, 1.8, center=w/4+6)
        pixel(p, 0, 138, "TOKENS", green, 1.3, center=3*w/4-6)
        pixel(p, 0, 159, self.app.tokens, green, 1.8, center=3*w/4-6)
        bevel(p, QRectF(16, 189, w-32, 40), c["button"])
        pixel(p, 26, 205, "SYNC..." if self.app.busy else "AUTO 30s", green, 1.3)


class Dashboard(QWidget):
    def __init__(self, autostart=True):
        super().__init__()
        self.theme, self.minimal, self.busy = "dark", False, False
        self.data = None
        self.plan, self.credits, self.tokens = "--", "--", "--"
        self.week = None
        self.five_hour = None
        self.five_hour_label = "CODEX"
        self.five_hour_reset = "정보 없음"
        self.show_five_hour = False
        self.remaining = {"week": False, "five_hour": False}
        self.week_reset = "정보 없음"
        self.settings = settings_path()
        try:
            saved = json.loads(self.settings.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("Settings must be a JSON object")
            self.theme = saved.get("theme", "dark") if saved.get("style") == "terminal-green" else "dark"
            self.show_five_hour = saved.get("show_five_hour") is True
            for key in self.remaining:
                self.remaining[key] = saved.get("remaining_"+key) is True
        except (OSError, ValueError):
            pass
        if not isinstance(self.theme, str) or self.theme not in PALETTES:
            self.theme = "dark"
        self.setWindowTitle("Codex Usage Dashboard")
        self.setWindowIcon(battery_icon())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 16, 20, 24)
        self.surface = Surface(self); layout.addWidget(self.surface)
        self.surface.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.surface.setFocus()
        shadow = QGraphicsDropShadowEffect(self.surface)
        shadow.setBlurRadius(28); shadow.setOffset(0, 7); shadow.setColor(QColor(0, 0, 0, 65))
        self.surface.setGraphicsEffect(shadow)
        self.setFixedSize(280, 283+(76 if self.show_five_hour else 0))
        self.results = queue.Queue()
        self.poller = QTimer(self); self.poller.timeout.connect(self.poll)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.refresh)
        if autostart:
            self.refresh()

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.save_settings()
        self.repaint_all()

    def save_settings(self):
        try:
            self.settings.parent.mkdir(parents=True, exist_ok=True)
            self.settings.write_text(json.dumps({"theme": self.theme, "style": "terminal-green", "show_five_hour": self.show_five_hour,
                                                **{"remaining_"+key: value for key, value in self.remaining.items()}}), encoding="utf-8")
        except OSError:
            pass

    def toggle_five_hour(self):
        self.show_five_hour = not self.show_five_hour
        self.surface.controls["five_hour"].setChecked(self.show_five_hour)
        self.resize_anchored()
        self.save_settings()

    def toggle_minimal(self):
        self.minimal = not self.minimal
        self.resize_anchored()

    def resize_anchored(self):
        right, top = self.x() + self.width(), self.y()
        if self.minimal:
            self.setFixedSize(170, 182+(92 if self.show_five_hour else 0))
        else:
            self.setFixedSize(280, 283+(76 if self.show_five_hour else 0))
        self.move(right - self.width(), top)
        self.repaint_all()

    def repaint_all(self):
        self.surface.update()
        for control in self.surface.controls.values():
            control.update()

    @staticmethod
    def window(item, duration):
        return next((w for w in (item.get("primary"), item.get("secondary"))
                     if w and w.get("windowDurationMins") == duration), None)

    @staticmethod
    def used(window):
        if not window or window.get("usedPercent") is None:
            return None
        return max(0, min(100, float(window["usedPercent"])))

    def show_data(self, data):
        self.data = data
        account, response, usage = data
        raw = (account.get("account") or {}).get("planType") or "unknown"
        self.plan = {"prolite": "Pro Lite", "plus": "Plus", "pro": "Pro"}.get(raw, raw.title())
        limits = response.get("rateLimitsByLimitId") or {}
        main = limits.get("codex") or response.get("rateLimits") or {}
        week = self.window(main, 10080)
        self.week = self.used(week)
        self.week_reset = format_reset((week or {}).get("resetsAt")) + " 초기화"
        five_hour = self.window(main, 300)
        self.five_hour_label = "CODEX"
        if five_hour is None:
            # Spark is a separate quota: never label it as the main Codex quota.
            spark = limits.get("codex_bengalfox") or limits.get("codex_spark") or {}
            five_hour = self.window(spark, 300)
            if five_hour is not None:
                self.five_hour_label = "SPARK"
        self.five_hour = self.used(five_hour)
        self.five_hour_reset = (format_reset(five_hour.get("resetsAt"))+" 초기화") if five_hour else "5시간 사용량 정보 없음"
        credit = main.get("credits") or {}
        balance = credit.get("balance")
        self.credits = "UNL" if credit.get("unlimited") else (f"{float(balance):,.0f}" if balance is not None else "--")
        total = (usage.get("summary") or {}).get("lifetimeTokens")
        self.tokens = "--" if total is None else (f"{total/1000000:.1f}M" if total >= 1000000 else f"{total:,}")
        self.surface.setToolTip(f"{datetime.now():%H:%M:%S} 업데이트 · 각 게이지 더블클릭: USED 사용량 / LEFT 잔여량 전환 (일반·미니멀 공통)")
        self.repaint_all()

    def refresh(self):
        if self.busy:
            return
        self.busy = True; self.timer.stop()
        self.surface.controls["refresh"].setEnabled(False)
        self.repaint_all()
        self.poller.start(100)
        threading.Thread(target=self.fetch, daemon=True).start()

    def fetch(self):
        try:
            self.results.put((read_usage(), None))
        except Exception as error:
            self.results.put((None, str(error)))

    def poll(self):
        try:
            data, error = self.results.get_nowait()
        except queue.Empty:
            return
        self.poller.stop()
        self.busy = False
        self.surface.controls["refresh"].setEnabled(True)
        if data is not None:
            try:
                self.show_data(data)
            except (AttributeError, TypeError, ValueError, OverflowError, OSError) as exc:
                data, error = None, str(exc)
        if data is None:
            self.data = None
            self.week, self.credits, self.tokens = None, "--", "--"
            self.five_hour = None
            self.five_hour_reset = "조회 불가 · 로그인/설치 확인"
            self.week_reset = "조회 불가 · 로그인/설치 확인"
            self.surface.setToolTip(f"조회 실패: {error} · 30초 후 재시도")
        self.repaint_all()
        self.timer.start(30000)


def main():
    if "--check" in sys.argv:
        data = read_usage()
        print("OK: account, limits, usage")
        return
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dawool.CodexUsage.Terminal")
    app = QApplication(sys.argv)
    app.setWindowIcon(battery_icon())
    smoke = "--smoke-test" in sys.argv
    window = Dashboard(autostart=not smoke)
    if smoke:
        window.show_data(({}, {"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": 78}}}, {}))
    window.show()
    if smoke:
        QTimer.singleShot(1500, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
