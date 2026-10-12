import json
import os
import platform
import queue
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from codex_process import QueryProcess


def find_codex():
    if sys.platform == "win32":
        # Search explicit PATH directories, without Windows' implicit current-directory lookup.
        launchers = []
        for directory in os.get_exec_path():
            if not directory or not Path(directory).is_absolute():
                continue
            for name in ("codex.exe", "codex.cmd", "codex.bat"):
                path = Path(directory) / name
                if path.is_file():
                    launchers.append(path)
        arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
        target = "aarch64" if arch == "arm64" else "x86_64"
        native = f"vendor/{target}-pc-windows-msvc/bin/codex.exe"
        for launcher in launchers:
            if launcher.suffix.lower() == ".exe" and is_windows_executable(launcher):
                return str(launcher)
            for root in (launcher.parent / "node_modules/@openai/codex",
                         launcher.parent.parent / "@openai/codex"):
                try:
                    if json.loads((root / "package.json").read_text(encoding="utf-8")).get("name") != "@openai/codex":
                        continue
                except (OSError, ValueError, AttributeError):
                    continue
                for candidate in (root / f"node_modules/@openai/codex-win32-{arch}" / native,
                                  root.parent / f"codex-win32-{arch}" / native, root / native):
                    if is_windows_executable(candidate):
                        return str(candidate.resolve())
        app_bin = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "OpenAI/Codex/bin"
        candidates = [path for path in app_bin.glob("*/codex.exe") if is_windows_executable(path)]
        if candidates:
            return str(max(candidates, key=lambda path: path.stat().st_mtime))
        # Other package managers may use a different layout; the job owns the wrapper's tree too.
        return next((str(path) for path in launchers if path.suffix.lower() in (".cmd", ".bat")), None)
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
    return codex


def is_windows_executable(path):
    import ctypes
    from ctypes import wintypes
    binary_type = wintypes.DWORD()
    check = ctypes.WinDLL("kernel32", use_last_error=True).GetBinaryTypeW
    check.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    check.restype = wintypes.BOOL
    return bool(check(str(path), ctypes.byref(binary_type))) and binary_type.value in (0, 6)


def settings_path():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent / "usage-dashboard-settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/TokenDashboard/settings.json"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "CodexUsageDashboard/settings.json"


def read_usage(cancel=None, timeout=15):
    cancel = cancel if cancel is not None else threading.Event()
    if cancel.is_set():
        raise RuntimeError("Codex 조회가 취소되었습니다.")
    codex = find_codex()
    if not codex:
        raise RuntimeError("Codex 실행 파일을 찾을 수 없습니다. Codex 앱 또는 CLI 설치를 확인하세요.")

    def send(message):
        process.send(json.dumps(message) + "\n")

    results = {}
    deadline = time.monotonic() + timeout

    def receive(pending):
        while pending:
            line = process.readline(cancel, deadline)
            if not line:
                raise RuntimeError("Codex 사용량 조회 연결이 종료되었습니다.")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
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

    with QueryProcess([codex, "app-server"]) as process:
        send({"method": "initialize", "id": 0, "params": {"clientInfo": {
            "name": "local_usage_dashboard", "title": "Local Usage Dashboard", "version": "1.5.0"
        }}})
        receive({0})
        send({"method": "initialized", "params": {}})
        send({"method": "account/read", "id": 1, "params": {"refreshToken": False}})
        send({"method": "account/rateLimits/read", "id": 2, "params": {}})
        send({"method": "account/usage/read", "id": 3, "params": {}})
        receive({1, 2, 3})
    return results[1], results[2], results[3]


def format_number(value):
    return f"{int(value or 0):,}"


def format_reset(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%m월 %d일 %H:%M") if timestamp else "정보 없음"


from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QGraphicsDropShadowEffect, QVBoxLayout
from block_theme import draw_frame, draw_panel, draw_button, draw_icon, draw_resource_icon, draw_xp_bar, draw_slot, make_app_icon
from block_typography import game_font, draw_game_text, glyph_runs
from station_theme import STATION_PALETTES, draw_station_frame, draw_enchanting_table, draw_theme_icon

THEME_ORDER = ("grass", "enchanting", "end")
THEME_NAMES = {"grass": "잔디블록", "enchanting": "인챈트 테이블", "end": "엔드 차원문"}

PALETTES = {
    "light": dict(top="#8D6642", bottom="#6C4A30", text="#FFF7E7", muted="#E0E5D2",
                  line="#626859", accent="#A7E65B", track="#303927",
                  panel="#929789", border="#352619", button="#8A8D81", hover="#A4AC98",
                  grass="#67A83A", grass_dark="#3E7025", dirt_light="#A67A50",
                  dirt_dark="#65452F", bevel_light="#D7DCCA", bevel_dark="#363C31"),
    "dark": dict(top="#725237", bottom="#513A28", text="#F2ECD7", muted="#AAB798",
                 line="#4D5C40", accent="#A4E85B", track="#1A2413",
                 panel="#20271B", border="#241B13", button="#707569", hover="#8B9478",
                 grass="#66A53B", grass_dark="#355F22", dirt_light="#876346",
                 dirt_dark="#493523", bevel_light="#A5AD98", bevel_dark="#252D1D"),
}


def text(p, x, y, width, height, value, color, size=17, bold=False, right=False, center=False):
    p.save()
    p.setFont(game_font(size, korean=True))
    p.setClipRect(QRectF(x, y, width, height), Qt.ClipOperation.IntersectClip)
    alignment = Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignHCenter if center else Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft)
    p.setPen(QColor("#15170F"))
    p.drawText(QRectF(x+1, y+1, width, height), alignment, str(value))
    p.setPen(QColor(color))
    p.drawText(QRectF(x, y, width, height), alignment, str(value))
    p.restore()


def icon(p, kind, box, color):
    draw_icon(p, kind, box, color)


def pixel(p, x, y, value, color, scale=2, center=None, right=None, shadow=True, max_width=None):
    if max_width is not None:
        width, _ = glyph_runs(str(value))
        scale = min(scale, max_width / max(1, width))
    draw_game_text(p, x, y, value, color, scale, center=center, right=right, shadow=shadow)


def usage_color(value, green):
    return "#FF5055" if value is not None and value >= 90 else "#F4D84B" if value is not None and value >= 70 else green


def readout(p, y, value, green, scale, center=None, right=None, outline=None, solid=None, remaining=False, shadow=None):
    if shadow:
        p.save(); p.translate(2, 2)
        readout(p, y, value, green, scale, center=center, right=right, solid=shadow, remaining=remaining)
        p.restore()
    if outline:
        for dx, dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
            p.save(); p.translate(dx, dy)
            readout(p, y, value, green, scale, center=center, right=right, solid=outline, remaining=remaining)
            p.restore()
    color = solid or usage_color(value, green)
    if value is None or (value < 100 and not (remaining and value == 0)):
        shown = None if value is None else (100-value if remaining else value)
        pixel(p, 0, y, "--" if shown is None else f"{min(99, int(shown))}%",
              color, scale, center=center, right=right, shadow=False)
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
    draw_xp_bar(p, x, y, width, height, value, color, track, line, reverse=reverse)


def battery_icon():
    return make_app_icon()


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
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        c = self.owner.app.palette
        if self.owner.app.theme == "grass" and self.kind in ("refresh", "theme") and not self.owner.app.minimal:
            c = {**c, "button": c["panel"], "hover": c["track"],
                 "bevel_light": c["line"], "bevel_dark": c["border"]}
        active = self.underMouse() or self.hasFocus()
        if self.kind == "five_hour":
            if not self.owner.app.minimal:
                pixel(p, 2, 8, "5H", "#F2ECD7", 1.3)
            x = self.width()-29
            draw_panel(p, QRectF(x, 5, 27, 13), c)
            p.fillRect(QRectF(x+(15 if self.isChecked() else 3), 7, 9, 9),
                       QColor(c["accent"] if self.isChecked() else c["muted"]))
            if self.hasFocus():
                p.setPen(QPen(QColor(c["accent"]), 1, Qt.PenStyle.DotLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(self.rect()).adjusted(1, 1, -2, -2))
            return
        if not self.isEnabled():
            p.setOpacity(.45)
        draw_button(p, QRectF(self.rect()).adjusted(2, 2, -2, -2),
                    {**c, "button": c["hover"]} if active else c, pressed=self.isDown())
        if active:
            p.setPen(QPen(QColor(c["accent"]), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(self.rect()).adjusted(2, 2, -3, -3))
        size = min(22, self.width()-6, self.height()-6)
        box = QRectF((self.width()-size)/2, (self.height()-size)/2, size, size)
        if self.kind == "theme":
            draw_theme_icon(p, box, self.owner.app.theme)
        else:
            icon(p, self.kind, box, c["text"])


class Surface(QWidget):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.controls = {}
        for kind, label, callback in (
            ("minimize", "최소화", app.showMinimized), ("close", "닫기", app.close),
            ("theme", "테마 전환: 잔디블록 → 인챈트 테이블 → 엔드 차원문", app.toggle_theme),
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
            positions = dict(theme=(w-94, 9, 18, 20), expand=(w-72, 9, 18, 20),
                             minimize=(w-50, 9, 18, 20), close=(w-28, 9, 18, 20),
                             five_hour=(5, 8, 30, 24))
        else:
            extra = 76 if self.app.show_five_hour else 0
            positions.update(theme=(w-43, 206+extra, 24, 24), refresh=(w-71, 206+extra, 24, 24),
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
            regions = (("week", 40), ("five_hour", 134)) if self.app.minimal else (("week", 72), ("five_hour", 148))
            if not self.app.minimal and self.app.theme != "grass":
                regions = (("week", 51), ("five_hour", 166))
            for key, y in regions:
                if key == "five_hour" and not self.app.show_five_hour:
                    continue
                height = 90 if self.app.minimal else (113 if key == "week" else 76) if self.app.theme != "grass" else 47
                if QRectF(18, y, self.width()-36, height).contains(event.position()):
                    self.app.remaining[key] = not self.app.remaining[key]
                    self.app.save_settings()
                    self.app.repaint_all()
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        c = self.app.palette
        green = c["accent"]
        outline = None
        if self.app.theme == "grass":
            draw_frame(p, w, h, c, minimal=self.app.minimal)
        else:
            draw_station_frame(p, w, h, c, self.app.theme, minimal=self.app.minimal)
        if self.app.minimal:
            if self.app.theme != "end":
                draw_panel(p, QRectF(12, 39, w-24, 92+(92 if self.app.show_five_hour else 0)), c)
            pixel(p, 0, 51, "WEEK/CODEX", c["text"], 1.3, center=w/2)
            left = self.app.remaining["week"]
            pixel(p, 0, 63, "LEFT" if left else "USED", c["muted"], 1, center=w/2)
            readout(p, 73, self.app.week, green, 5, center=w/2, outline=outline, remaining=left, shadow="#15170F")
            amount = None if self.app.week is None else (100-self.app.week if left else self.app.week)
            meter(p, (w-92)/2, 116, 92, 8, amount, usage_color(self.app.week, green), c["track"], c["line"], reverse=left)
            if self.app.show_five_hour:
                p.setPen(QPen(QColor(c["line"]), 1))
                p.drawLine(QPointF(20, 132), QPointF(w-20, 132))
                pixel(p, 0, 143, "5H/"+self.app.five_hour_label, c["text"], 1.3, center=w/2)
                left = self.app.remaining["five_hour"]
                pixel(p, 0, 155, "LEFT" if left else "USED", c["muted"], 1, center=w/2)
                readout(p, 165, self.app.five_hour, green, 5, center=w/2, outline=outline, remaining=left, shadow="#15170F")
                amount = None if self.app.five_hour is None else (100-self.app.five_hour if left else self.app.five_hour)
                meter(p, (w-92)/2, 208, 92, 8, amount, usage_color(self.app.five_hour, green), c["track"], c["line"], reverse=left)
            return
        if self.app.theme != "grass":
            self.paint_station(p, w, h, c)
            return
        p.drawPixmap(20, 16, 24, 24, self.app.windowIcon().pixmap(24, 24))
        extra = 76 if self.app.show_five_hour else 0
        draw_panel(p, QRectF(12, 51, w-24, 113+extra), c)
        p.save()
        p.translate(0, 14)
        pixel(p, 22, 65, "WEEK / CODEX", c["text"], 1.5)
        left = self.app.remaining["week"]
        readout(p, 64, self.app.week, green, 2, right=w-24, outline=outline, remaining=left, shadow="#15170F")
        amount = None if self.app.week is None else (100-self.app.week if left else self.app.week)
        meter(p, 22, 87, w-45, 15, amount, usage_color(self.app.week, green), c["track"], c["line"], reverse=left)
        pixel(p, 22, 110, "LEFT" if left else "USED", c["muted"], 1)
        text(p, 58, 105, w-82, 16, self.app.week_reset, c["muted"], 10, right=True)
        p.setPen(QPen(QColor(c["line"]), 1))
        p.drawLine(QPointF(13, 126), QPointF(w-13, 126))
        if self.app.show_five_hour:
            pixel(p, 22, 141, "5H / "+self.app.five_hour_label, c["text"], 1.5)
            left = self.app.remaining["five_hour"]
            readout(p, 140, self.app.five_hour, green, 2, right=w-24, outline=outline, remaining=left, shadow="#15170F")
            amount = None if self.app.five_hour is None else (100-self.app.five_hour if left else self.app.five_hour)
            meter(p, 22, 163, w-45, 15, amount, usage_color(self.app.five_hour, green), c["track"], c["line"], reverse=left)
            pixel(p, 22, 186, "LEFT" if left else "USED", c["muted"], 1)
            text(p, 58, 181, w-82, 16, self.app.five_hour_reset, c["muted"], 10, right=True)
            p.setPen(QPen(QColor(c["line"]), 1))
            p.drawLine(QPointF(13, 202), QPointF(w-13, 202))
        p.restore()
        self.paint_resources(p, w, c, extra)
        self.paint_footer(p, h, c)
        pixel(p, 0, h-11, "BLOCK EDITION", "#F2ECD7", 1, center=w/2)

    def paint_resources(self, p, w, c, extra):
        """Align resource slots and keep diamond/emerald colors across themes."""
        p.save()
        p.translate(0, extra)
        slot_width = (w-56)/2
        for x, label, value, kind, color in (
            (20, "CREDITS", self.app.credits, "credits", "#69E7DF"),
            (w/2+8, "TOKENS", self.app.tokens, "tokens", "#63E56C"),
        ):
            draw_slot(p, QRectF(x, 170, slot_width, 33), c)
            draw_resource_icon(p, kind, QRectF(x+5, 174, 12, 12))
            pixel(p, x+20, 176, label, c["text"], 1)
            pixel(p, 0, 189, value, color, 1.3, center=x+slot_width/2, max_width=slot_width-10)
        p.restore()

    def paint_footer(self, p, h, c):
        """Use the same compact status row and typography for all three themes."""
        if self.app.theme == "grass":
            y, width = h-37, self.width()-36
            p.fillRect(QRectF(18, y, width, 24), QColor(c["bevel_dark"]))
            p.fillRect(QRectF(19, y+1, width-2, 22), QColor(c["panel"]))
            p.fillRect(QRectF(19, y+1, width-2, 1), QColor(c["line"]))
            p.fillRect(QRectF(self.width()-74, y+6, 1, 12), QColor(c["line"]))
        pixel(p, 22, h-28, "SYNC..." if self.app.busy else "AUTO 30s", c["text"], 1.1)

    def paint_station(self, p, w, h, c):
        """Keep the selected block's artwork inside the existing small window."""
        theme = self.app.theme
        extra = 76 if self.app.show_five_hour else 0
        draw_theme_icon(p, QRectF(20, 16, 24, 24), theme)
        if theme == "enchanting":
            draw_panel(p, QRectF(12, 51, w-24, 113), c)
            draw_enchanting_table(p, QRectF(20, 55, 84, 84))
            center, scale = (w+84)/2, 4.5
        else:
            center, scale = w/2, 5
        pixel(p, 0, 59, "WEEK / CODEX", c["text"], 1.3, center=center)
        left = self.app.remaining["week"]
        readout(p, 80, self.app.week, c["accent"], scale, center=center,
                remaining=left, shadow=c["border"])
        pixel(p, 0, 121, "LEFT" if left else "USED", c["muted"], 1, center=center)
        amount = None if self.app.week is None else (100-self.app.week if left else self.app.week)
        meter(p, 22, 139, w-44, 7, amount, usage_color(self.app.week, c["accent"]), c["track"], c["line"], reverse=left)
        text(p, 22, 149, w-44, 15, self.app.week_reset, c["muted"], 10, right=True)
        if self.app.show_five_hour:
            p.setPen(QPen(QColor(c["line"]), 1))
            p.drawLine(QPointF(20, 168), QPointF(w-20, 168))
            pixel(p, 22, 177, "5H / "+self.app.five_hour_label, c["text"], 1.3)
            left = self.app.remaining["five_hour"]
            readout(p, 176, self.app.five_hour, c["accent"], 2.5, right=w-24,
                    remaining=left, shadow=c["border"])
            amount = None if self.app.five_hour is None else (100-self.app.five_hour if left else self.app.five_hour)
            meter(p, 22, 197, w-44, 8, amount, usage_color(self.app.five_hour, c["accent"]), c["track"], c["line"], reverse=left)
            pixel(p, 22, 219, "LEFT" if left else "USED", c["muted"], 1)
            text(p, 58, 212, w-82, 15, self.app.five_hour_reset, c["muted"], 10, right=True)
        self.paint_resources(p, w, c, extra)
        self.paint_footer(p, h, c)
        pixel(p, 0, h-11, "ENCHANTING TABLE" if theme == "enchanting" else "END PORTAL", c["muted"], 1, center=w/2)


class Dashboard(QWidget):
    def __init__(self, autostart=True):
        super().__init__()
        application = QApplication.instance()
        application.setFont(game_font(10))
        application.setStyleSheet("QToolTip { color: #FFF7E7; background-color: #1B1421; border: 2px solid #573273; padding: 5px; }")
        self.theme, self.grass_variant = "grass", "dark"
        self.minimal, self.busy = False, False
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
            if saved.get("style") == "minecraft-edition":
                if saved.get("theme") in THEME_ORDER:
                    self.theme = saved["theme"]
                if saved.get("grass_variant") in ("dark", "light"):
                    self.grass_variant = saved["grass_variant"]
            elif saved.get("style") in ("terminal-green", "block-craft") and saved.get("theme") in ("dark", "light"):
                self.grass_variant = saved["theme"]
            self.show_five_hour = saved.get("show_five_hour") is True
            for key in self.remaining:
                self.remaining[key] = saved.get("remaining_"+key) is True
        except (OSError, ValueError):
            pass
        self.setWindowTitle("Token Dashboard - Minecraft Edition")
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
        self.cancel = threading.Event()
        self.worker = None
        self.poller = QTimer(self); self.poller.timeout.connect(self.poll)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.refresh)
        if autostart:
            self.refresh()

    def toggle_theme(self):
        self.theme = THEME_ORDER[(THEME_ORDER.index(self.theme)+1) % len(THEME_ORDER)]
        self.save_settings()
        self.surface.resizeEvent(None)
        self.repaint_all()

    @property
    def palette(self):
        return PALETTES[self.grass_variant] if self.theme == "grass" else STATION_PALETTES[self.theme]

    def save_settings(self):
        try:
            self.settings.parent.mkdir(parents=True, exist_ok=True)
            self.settings.write_text(json.dumps({"theme": self.theme, "style": "minecraft-edition", "grass_variant": self.grass_variant, "show_five_hour": self.show_five_hour,
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
        next_theme = THEME_ORDER[(THEME_ORDER.index(self.theme)+1) % len(THEME_ORDER)]
        label = f"테마 전환: {THEME_NAMES[self.theme]} → {THEME_NAMES[next_theme]}"
        self.surface.controls["theme"].setToolTip(label)
        self.surface.controls["theme"].setAccessibleName(label)
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
        if self.busy or self.cancel.is_set():
            return
        self.busy = True; self.timer.stop()
        self.surface.controls["refresh"].setEnabled(False)
        self.repaint_all()
        self.poller.start(100)
        self.worker = threading.Thread(target=self.fetch, name="codex-query", daemon=True)
        self.worker.start()

    def fetch(self):
        try:
            self.results.put((read_usage(self.cancel), None))
        except Exception as error:
            self.results.put((None, str(error)))

    def poll(self):
        if self.cancel.is_set():
            return
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

    def shutdown(self):
        self.cancel.set()
        self.timer.stop()
        self.poller.stop()
        if self.worker is not None:
            self.worker.join(timeout=3)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


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
    app.aboutToQuit.connect(window.shutdown)
    if smoke:
        window.show_data(({}, {"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": 78}}}, {}))
    window.show()
    if smoke:
        QTimer.singleShot(1500, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
