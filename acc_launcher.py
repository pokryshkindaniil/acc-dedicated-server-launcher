import ctypes
import csv
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPointF
    from PyQt6.QtGui import (
        QColor, QTextCharFormat, QTextCursor, QFont, QShortcut, QKeySequence,
        QIcon, QPainter, QPolygonF,
    )
    from PyQt6.QtWidgets import (
        QProxyStyle, QStyle, QStyleOption,
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QFormLayout, QGridLayout, QTabWidget, QGroupBox, QLabel, QPushButton,
        QLineEdit, QSpinBox, QComboBox, QCheckBox, QTextEdit,
        QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,
        QInputDialog, QFrame, QHeaderView, QAbstractItemView,
        QSizePolicy, QScrollArea, QSplitter,
    )
except ImportError:
    print("PyQt6 is required. Install it with:  pip install PyQt6")
    sys.exit(1)


APP_NAME = "ACC Dedicated Server Launcher"
APP_VERSION = "1.0.0"
APP_CONFIG_FILE = "acc_launcher_config.json"
PRESETS_FILE = "acc_launcher_presets.json"


TRACK_GROUPS = {
    "Base game": [
        "barcelona", "brands_hatch", "hungaroring", "misano", "monza",
        "nurburgring", "paul_ricard", "silverstone", "spa", "zandvoort", "zolder",
    ],
    "Intercontinental GT Pack": ["kyalami", "laguna_seca", "mount_panorama", "suzuka"],
    "2020 GT World Challenge Pack": ["imola"],
    "British GT Pack": ["donington", "oulton_park", "snetterton"],
    "American Track Pack": ["cota", "indianapolis", "watkins_glen"],
    "2023 GT World Challenge Pack": ["valencia"],
    "GT2 Pack": ["red_bull_ring"],
    "Nurburgring 24h Pack": ["nurburgring_24h"],
}

TRACK_TO_GROUP = {
    track: group for group, tracks in TRACK_GROUPS.items() for track in tracks
}
ALL_TRACKS = [track for tracks in TRACK_GROUPS.values() for track in tracks]

CAR_GROUPS = ["GT3", "GT4", "GT2", "GTC", "TCX", "FreeForAll"]

WEATHER_PRESETS = {
    "Dry":        {"ambientTemp": 23, "cloudLevel": 0.0, "rain": 0.0, "weatherRandomness": 0},
    "Cloudy":     {"ambientTemp": 22, "cloudLevel": 0.6, "rain": 0.0, "weatherRandomness": 1},
    "Light rain": {"ambientTemp": 19, "cloudLevel": 0.8, "rain": 0.25, "weatherRandomness": 1},
    "Random":     {"ambientTemp": 22, "cloudLevel": 0.4, "rain": 0.1,  "weatherRandomness": 5},
}

CAR_MODELS = {
    "Any / keep default": -1,
    "Porsche 992 GT3 R 2023": 32,
    "Porsche 991 II GT3 R 2019": 23,
    "BMW M4 GT3": 30,
    "Ferrari 296 GT3": 31,
    "McLaren 720S GT3 Evo": 33,
    "Mercedes-AMG GT3 Evo": 24,
    "Audi R8 LMS Evo II": 29,
    "Aston Martin V8 Vantage GT3": 20,
    "Lamborghini Huracan GT3 Evo2": 34,
}

LOG_TAGS = {
    "error":      ["==ERR", "ERROR", "Couldn't", "wrong value", "failed", "Failed"],
    "warning":    ["warning", "Warning", "exceeds", "Late lastUdp"],
    "success":    ["Lobby accepted", "RegisterToLobby succeeded", "New connection request", "Starting server", "Listening to"],
    "connection": ["New connection", "client(s) online", "Driver(s) detected", "Updated lobby with", "Disconnected"],
}

PALETTES = {
    "dark": {
        "text":       "#edf2f7",
        "muted":      "#9ba7b6",
        "accent":     "#5b7cff",
        "success":    "#58d68d",
        "warning":    "#f4b35e",
        "error":      "#ff6b6b",
        "connection": "#6cb6ff",
        "bg":         "#101215",
        "surface":    "#171a20",
        "surface2":   "#1d222a",
        "border":     "#2d3440",
    },
    "light": {
        "text":       "#18212b",
        "muted":      "#617182",
        "accent":     "#4060f6",
        "success":    "#1f8f52",
        "warning":    "#b7791f",
        "error":      "#d64545",
        "connection": "#1b6ed1",
        "bg":         "#eef2f7",
        "surface":    "#ffffff",
        "surface2":   "#f6f8fb",
        "border":     "#ccd5e3",
    },
}


def _qss_dark():
    return """
QMainWindow, QDialog { background-color: #101215; }
QWidget { background-color: #101215; color: #edf2f7;
          font-family: "Segoe UI"; font-size: 10pt; }

/* ── Header ── */
QFrame#header { background-color: #171a20;
                border-bottom: 1px solid #2d3440; padding: 0; }
QLabel#app_title { font-size: 18pt; font-weight: 700; color: #edf2f7;
                   background: transparent; }
QLabel#app_subtitle { color: #9ba7b6; font-size: 9pt; background: transparent; }

/* ── Group boxes ── */
QGroupBox { background-color: #171a20; border: 1px solid #2d3440;
            border-radius: 8px; margin-top: 14px;
            padding: 14px 12px 12px 12px;
            font-weight: 600; font-size: 10pt; color: #edf2f7; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                   left: 12px; padding: 0 5px; color: #9ba7b6; }

/* ── Inputs ── */
QLineEdit, QSpinBox, QComboBox {
    background-color: #0f1318; border: 1px solid #2d3440;
    border-radius: 5px; padding: 7px 10px; color: #edf2f7;
    min-height: 18px; selection-background-color: #3658d4; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #5b7cff; }
QLineEdit:hover, QSpinBox:hover, QComboBox:hover { border-color: #4a5568; }
QLineEdit[echoMode="2"] { letter-spacing: 3px; }

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #1d222a; border: none; width: 22px;
    border-radius: 0; }
QSpinBox::up-button { border-bottom: 1px solid #2d3440;
                       border-top-right-radius: 5px; }
QSpinBox::down-button { border-bottom-right-radius: 5px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #2d3440; }

QComboBox::drop-down {
    width: 28px;
    border-left: 1px solid #2d3440;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    background-color: #1d222a;
}
QComboBox::drop-down:hover { background-color: #252c36; }
QComboBox QAbstractItemView {
    background-color: #0f1318; border: 1px solid #2d3440;
    border-radius: 5px; color: #edf2f7;
    selection-background-color: #3658d4; selection-color: #fff;
    outline: none; }
QComboBox QAbstractItemView::item { padding: 7px 10px; min-height: 24px; }
QComboBox QAbstractItemView::item:hover { background-color: #1d222a; }

/* ── Buttons ── */
QPushButton { background-color: #1d222a; border: 1px solid #2d3440;
              border-radius: 5px; padding: 8px 18px; color: #edf2f7;
              font-weight: 500; min-height: 20px; }
QPushButton:hover   { background-color: #252c36; border-color: #4a5568; }
QPushButton:pressed { background-color: #151b24; }
QPushButton:disabled { color: #4a5568; border-color: #1d222a;
                        background-color: #171a20; }
QPushButton#primary { background-color: #5b7cff; border-color: #5b7cff;
                       color: #fff; font-weight: 600; }
QPushButton#primary:hover   { background-color: #7290ff; border-color: #7290ff; }
QPushButton#primary:pressed { background-color: #4060f6; }
QPushButton#danger  { background-color: #2d1a1a; border-color: #5c2020; color: #ff8080; }
QPushButton#danger:hover { background-color: #3d2020; border-color: #7a2a2a; }

/* ── Tabs ── */
QTabWidget::pane { border: 1px solid #2d3440; border-top: none;
                   background-color: #101215; border-bottom-left-radius: 6px;
                   border-bottom-right-radius: 6px; }
QTabBar { background-color: #101215; }
QTabWidget { background-color: #101215; }
QTabBar::tab { background-color: #1d222a; color: #9ba7b6;
               padding: 11px 24px; font-weight: 600; font-size: 10pt;
               border: 1px solid #2d3440; border-bottom: none;
               margin-right: 2px; border-top-left-radius: 7px;
               border-top-right-radius: 7px; }
QTabBar::tab:selected { background-color: #5b7cff; color: #fff;
                         border-color: #5b7cff; margin-bottom: -1px; }
QTabBar::tab:hover:!selected { background-color: #252c36; color: #edf2f7; }

/* ── Checkboxes ── */
QCheckBox { color: #edf2f7; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #2d3440;
                        border-radius: 4px; background-color: #0f1318; }
QCheckBox::indicator:hover   { border-color: #5b7cff; }
QCheckBox::indicator:checked { background-color: #5b7cff; border-color: #5b7cff; }

/* ── Text areas ── */
QTextEdit, QPlainTextEdit {
    background-color: #0d1117; border: 1px solid #2d3440; border-radius: 5px;
    color: #edf2f7; selection-background-color: #3658d4;
    font-family: "Consolas"; font-size: 10pt; padding: 4px; }
QTextEdit:focus, QPlainTextEdit:focus { border-color: #5b7cff; }

/* ── Tree ── */
QTreeWidget { background-color: #0f1318; border: 1px solid #2d3440;
              border-radius: 5px; color: #edf2f7;
              alternate-background-color: #141820; outline: none; }
QTreeWidget::item { padding: 6px 4px; border: none; }
QTreeWidget::item:selected { background-color: #3658d4; color: #fff; }
QTreeWidget::item:hover:!selected { background-color: #1d222a; }
QHeaderView::section { background-color: #1d222a; color: #9ba7b6;
                        border: none; border-right: 1px solid #2d3440;
                        border-bottom: 1px solid #2d3440;
                        padding: 7px 8px; font-weight: 600; }
QHeaderView::section:hover { background-color: #252c36; color: #edf2f7; }

/* ── Scrollbars ── */
QScrollBar:vertical   { background: #0f1318; width: 8px; border: none; }
QScrollBar:horizontal { background: #0f1318; height: 8px; border: none; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #2d3440; border-radius: 4px; min-height: 24px; min-width: 24px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #4a5568; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ── Separator ── */
QFrame#vsep { background-color: #2d3440; max-width: 1px; min-width: 1px; margin: 4px 8px; }
QFrame#hsep { background-color: #2d3440; max-height: 1px; min-height: 1px; }

/* ── Badges ── */
QLabel#badge { background-color: #1d222a; border: 1px solid #2d3440;
               border-radius: 5px; padding: 5px 12px; color: #edf2f7;
               font-size: 9pt; }

/* ── Muted labels ── */
QLabel#muted { color: #9ba7b6; font-size: 9pt; background: transparent; }

/* ── Tooltip ── */
QToolTip { background-color: #1d222a; color: #edf2f7;
           border: 1px solid #2d3440; border-radius: 4px;
           padding: 6px 10px; font-size: 9pt; }
"""


def _qss_light():
    return """
QMainWindow, QDialog { background-color: #eef2f7; }
QWidget { background-color: #eef2f7; color: #18212b;
          font-family: "Segoe UI"; font-size: 10pt; }

QFrame#header { background-color: #ffffff; border-bottom: 1px solid #ccd5e3; }
QLabel#app_title  { font-size: 18pt; font-weight: 700; color: #18212b; background: transparent; }
QLabel#app_subtitle { color: #617182; font-size: 9pt; background: transparent; }

QGroupBox { background-color: #ffffff; border: 1px solid #ccd5e3;
            border-radius: 8px; margin-top: 14px;
            padding: 14px 12px 12px 12px; font-weight: 600;
            font-size: 10pt; color: #18212b; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                   left: 12px; padding: 0 5px; color: #617182; }

QLineEdit, QSpinBox, QComboBox {
    background-color: #ffffff; border: 1px solid #ccd5e3;
    border-radius: 5px; padding: 7px 10px; color: #18212b;
    min-height: 18px; selection-background-color: #4d6dff; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #4060f6; }
QLineEdit:hover, QSpinBox:hover, QComboBox:hover  { border-color: #a0aec0; }

QSpinBox::up-button, QSpinBox::down-button { background-color: #f6f8fb;
    border: none; width: 22px; }
QSpinBox::up-button  { border-top-right-radius: 5px;
                        border-bottom: 1px solid #ccd5e3; }
QSpinBox::down-button { border-bottom-right-radius: 5px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #e8edf5; }

QComboBox::drop-down {
    width: 28px;
    border-left: 1px solid #ccd5e3;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    background-color: #f0f4f8;
}
QComboBox::drop-down:hover { background-color: #e8edf5; }
QComboBox QAbstractItemView { background-color: #ffffff; border: 1px solid #ccd5e3;
    border-radius: 5px; color: #18212b; selection-background-color: #4d6dff;
    selection-color: #fff; outline: none; }
QComboBox QAbstractItemView::item { padding: 7px 10px; min-height: 24px; }
QComboBox QAbstractItemView::item:hover { background-color: #f6f8fb; }

QPushButton { background-color: #f6f8fb; border: 1px solid #ccd5e3;
              border-radius: 5px; padding: 8px 18px; color: #18212b;
              font-weight: 500; min-height: 20px; }
QPushButton:hover   { background-color: #e8edf5; border-color: #a0aec0; }
QPushButton:pressed { background-color: #dde4ef; }
QPushButton:disabled { color: #a0aec0; border-color: #e2e8f0; background-color: #f6f8fb; }
QPushButton#primary { background-color: #4060f6; border-color: #4060f6;
                       color: #fff; font-weight: 600; }
QPushButton#primary:hover   { background-color: #5876ff; border-color: #5876ff; }
QPushButton#primary:pressed { background-color: #3355e0; }
QPushButton#danger  { background-color: #fff0f0; border-color: #f5c6c6; color: #d64545; }
QPushButton#danger:hover { background-color: #ffe0e0; }

QTabWidget::pane { border: 1px solid #ccd5e3; border-top: none;
                   background-color: #eef2f7; border-bottom-left-radius: 6px;
                   border-bottom-right-radius: 6px; }
QTabBar { background-color: #eef2f7; }
QTabWidget { background-color: #eef2f7; }
QTabBar::tab { background-color: #e8edf5; color: #617182; padding: 11px 24px;
               font-weight: 600; font-size: 10pt; border: 1px solid #ccd5e3;
               border-bottom: none; margin-right: 2px;
               border-top-left-radius: 7px; border-top-right-radius: 7px; }
QTabBar::tab:selected { background-color: #4060f6; color: #fff; border-color: #4060f6;
                         margin-bottom: -1px; }
QTabBar::tab:hover:!selected { background-color: #dde4ef; color: #18212b; }

QCheckBox { color: #18212b; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #ccd5e3;
                        border-radius: 4px; background-color: #ffffff; }
QCheckBox::indicator:hover   { border-color: #4060f6; }
QCheckBox::indicator:checked { background-color: #4060f6; border-color: #4060f6; }

QTextEdit, QPlainTextEdit { background-color: #ffffff; border: 1px solid #ccd5e3;
    border-radius: 5px; color: #18212b; selection-background-color: #4d6dff;
    font-family: "Consolas"; font-size: 10pt; padding: 4px; }
QTextEdit:focus, QPlainTextEdit:focus { border-color: #4060f6; }

QTreeWidget { background-color: #ffffff; border: 1px solid #ccd5e3;
              border-radius: 5px; color: #18212b;
              alternate-background-color: #f6f8fb; outline: none; }
QTreeWidget::item { padding: 6px 4px; border: none; }
QTreeWidget::item:selected { background-color: #4d6dff; color: #fff; }
QTreeWidget::item:hover:!selected { background-color: #f6f8fb; }
QHeaderView::section { background-color: #f6f8fb; color: #617182;
                        border: none; border-right: 1px solid #ccd5e3;
                        border-bottom: 1px solid #ccd5e3; padding: 7px 8px;
                        font-weight: 600; }
QHeaderView::section:hover { background-color: #e8edf5; color: #18212b; }

QScrollBar:vertical   { background: #f6f8fb; width: 8px; border: none; }
QScrollBar:horizontal { background: #f6f8fb; height: 8px; border: none; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #ccd5e3; border-radius: 4px; min-height: 24px; min-width: 24px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #a0aec0; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QFrame#vsep { background-color: #ccd5e3; max-width: 1px; min-width: 1px; margin: 4px 8px; }
QFrame#hsep { background-color: #ccd5e3; max-height: 1px; min-height: 1px; }

QLabel#badge { background-color: #f6f8fb; border: 1px solid #ccd5e3;
               border-radius: 5px; padding: 5px 12px; color: #18212b; font-size: 9pt; }
QLabel#muted  { color: #617182; font-size: 9pt; background: transparent; }

QToolTip { background-color: #ffffff; color: #18212b; border: 1px solid #ccd5e3;
           border-radius: 4px; padding: 6px 10px; font-size: 9pt; }
"""


@dataclass
class Paths:
    server: Path
    exe: Path
    cfg: Path
    settings: Path
    event: Path
    configuration: Path
    assist_rules: Path
    event_rules: Path
    entrylist: Path
    log_dir: Path
    results_dir: Path
    backups_dir: Path


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def is_windows_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_command(command, cwd=None, timeout=10):
    try:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, shell=False,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def parse_csv_lines(text: str):
    rows = []
    try:
        import csv as _csv
        reader = _csv.reader(text.splitlines())
        rows = [row for row in reader if row]
    except Exception:
        return []
    return rows


def get_local_ipv4_addresses():
    addresses = []
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = item[4][0]
            if ip not in addresses and not ip.startswith("127."):
                addresses.append(ip)
    except Exception:
        pass
    return addresses


class ServerReader(QThread):
    line_received = pyqtSignal(str)
    process_stopped = pyqtSignal(int)

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process

    def run(self):
        for line in self.process.stdout:
            self.line_received.emit(line.rstrip())
        code = self.process.wait()
        self.process_stopped.emit(code)


class AccStyle(QProxyStyle):
    """Fusion-based style that draws arrows in the theme's muted color."""

    ARROW_ELEMENTS = frozenset([
        QStyle.PrimitiveElement.PE_IndicatorArrowDown,
        QStyle.PrimitiveElement.PE_IndicatorArrowUp,
        QStyle.PrimitiveElement.PE_IndicatorArrowRight,
        QStyle.PrimitiveElement.PE_IndicatorArrowLeft,
    ])

    def __init__(self):
        super().__init__("Fusion")
        self._color = QColor("#9ba7b6")

    def set_color(self, hex_color: str):
        self._color = QColor(hex_color)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element not in self.ARROW_ELEMENTS:
            super().drawPrimitive(element, option, painter, widget)
            return

        r = option.rect
        cx, cy = r.center().x(), r.center().y()
        s = max(3, min(r.width(), r.height()) * 38 // 100)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)

        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            pts = [QPointF(cx - s, cy - s * 0.5),
                   QPointF(cx + s, cy - s * 0.5),
                   QPointF(cx,     cy + s * 0.6)]
        elif element == QStyle.PrimitiveElement.PE_IndicatorArrowUp:
            pts = [QPointF(cx - s, cy + s * 0.5),
                   QPointF(cx + s, cy + s * 0.5),
                   QPointF(cx,     cy - s * 0.6)]
        elif element == QStyle.PrimitiveElement.PE_IndicatorArrowRight:
            pts = [QPointF(cx - s * 0.5, cy - s),
                   QPointF(cx - s * 0.5, cy + s),
                   QPointF(cx + s * 0.6, cy)]
        else:
            pts = [QPointF(cx + s * 0.5, cy - s),
                   QPointF(cx + s * 0.5, cy + s),
                   QPointF(cx - s * 0.6, cy)]

        painter.drawPolygon(QPolygonF(pts))
        painter.restore()


def _vsep():
    f = QFrame()
    f.setObjectName("vsep")
    f.setFrameShape(QFrame.Shape.VLine)
    return f


def _hsep():
    f = QFrame()
    f.setObjectName("hsep")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


class ACCServerLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ACC Server Control  v{APP_VERSION}")
        self.resize(1260, 880)
        self.setMinimumSize(1060, 740)

        self.process: subprocess.Popen | None = None
        self.server_reader: ServerReader | None = None

        self.app_config = read_json(Path(APP_CONFIG_FILE), {})
        self.presets = read_json(Path(PRESETS_FILE), {})
        self.theme_mode = self.app_config.get("theme_mode", "dark")
        if self.theme_mode not in PALETTES:
            self.theme_mode = "dark"
        self.palette = PALETTES[self.theme_mode]

        self.entry_items = []
        self.selected_entry_index = None

        self._build_ui()
        self._apply_theme(self.theme_mode)
        self._refresh_track_values()
        self._refresh_preset_list()
        self._update_session_controls()

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_configs)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.start_server)
        QShortcut(QKeySequence("F6"), self).activated.connect(self.stop_server)
        QShortcut(QKeySequence("F7"), self).activated.connect(self.restart_server)

        server_dir = self.app_config.get("server_dir", "")
        if server_dir:
            self.server_dir_edit.setText(server_dir)
            self.load_existing_configs(silent=True)

    # ─────────────────────────── UI CONSTRUCTION ────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._make_header())
        main.addWidget(self._make_path_bar())
        main.addWidget(self._make_status_bar())

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        main.addWidget(self.tab_widget, 1)

        self._make_tabs()
        main.addWidget(self._make_footer())

    def _make_header(self):
        frame = QFrame()
        frame.setObjectName("header")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(20, 16, 20, 16)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("ACC Server Control")
        title.setObjectName("app_title")
        sub = QLabel(f"v{APP_VERSION}  ·  Dedicated server launcher with presets, validation and live logs.")
        sub.setObjectName("app_subtitle")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        lay.addLayout(title_col, 1)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(8)
        theme_row.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.theme_mode)
        self.theme_combo.setFixedWidth(90)
        self.theme_combo.currentTextChanged.connect(self._apply_theme)
        theme_row.addWidget(self.theme_combo)
        lay.addLayout(theme_row)
        return frame

    def _make_path_bar(self):
        box = QGroupBox("ACC server folder")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(12, 20, 12, 12)
        self.server_dir_edit = QLineEdit()
        self.server_dir_edit.setPlaceholderText("Folder containing accServer.exe …")
        lay.addWidget(self.server_dir_edit, 1)
        btn_choose = QPushButton("Choose folder")
        btn_choose.clicked.connect(self.choose_server_folder)
        lay.addWidget(btn_choose)
        btn_open = QPushButton("Open in Explorer")
        btn_open.clicked.connect(self.open_server_folder)
        lay.addWidget(btn_open)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(12, 8, 12, 0)
        wl.addWidget(box)
        return wrap

    def _make_status_bar(self):
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        self.server_status_lbl  = self._badge("Server stopped")
        self.player_status_lbl  = self._badge("Players: 0")
        self.lobby_status_lbl   = self._badge("Lobby: unknown")
        self.port_status_lbl    = self._badge("Ports not checked")
        self.track_pack_lbl     = self._badge("Track pack: Base game")

        for lbl in [self.server_status_lbl, self.player_status_lbl,
                    self.lobby_status_lbl, self.port_status_lbl, self.track_pack_lbl]:
            lay.addWidget(lbl)
        lay.addStretch()
        self._set_server_badge(False)
        return wrap

    def _badge(self, text=""):
        lbl = QLabel(text)
        lbl.setObjectName("badge")
        return lbl

    def _make_tabs(self):
        tw = self.tab_widget
        self.tab_quick    = QWidget()
        self.tab_tracks   = QWidget()
        self.tab_presets  = QWidget()
        self.tab_entry    = QWidget()
        self.tab_rules    = QWidget()
        self.tab_network  = QWidget()
        self.tab_logs     = QWidget()

        tw.addTab(self.tab_quick,   "Quick Setup")
        tw.addTab(self.tab_tracks,  "Tracks / DLC")
        tw.addTab(self.tab_presets, "Presets")
        tw.addTab(self.tab_entry,   "Entry List")
        tw.addTab(self.tab_rules,   "Assists / Rules")
        tw.addTab(self.tab_network, "Network Checks")
        tw.addTab(self.tab_logs,    "Logs")

        self._build_quick_tab()
        self._build_tracks_tab()
        self._build_presets_tab()
        self._build_entry_tab()
        self._build_rules_tab()
        self._build_network_tab()
        self._build_logs_tab()

    def _make_footer(self):
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(12, 10, 12, 14)
        lay.setSpacing(6)

        btn_load = QPushButton("Load configs")
        btn_load.setToolTip("Reload config files from the server folder into the form.")
        btn_load.clicked.connect(self.load_existing_configs)
        lay.addWidget(btn_load)

        btn_val = QPushButton("Validate")
        btn_val.setToolTip("Check for errors or warnings before saving.")
        btn_val.clicked.connect(self.validate_and_show)
        lay.addWidget(btn_val)

        btn_save = QPushButton("Save configs")
        btn_save.setToolTip("Write all config files to disk.  Shortcut: Ctrl+S")
        btn_save.clicked.connect(self.save_configs)
        lay.addWidget(btn_save)

        lay.addWidget(_vsep())

        self.btn_start = QPushButton("▶   Start server")
        self.btn_start.setObjectName("primary")
        self.btn_start.setToolTip("Save configs and start accServer.exe.  Shortcut: F5")
        self.btn_start.clicked.connect(self.start_server)
        lay.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■   Stop server")
        self.btn_stop.setToolTip("Stop the running server process.  Shortcut: F6")
        self.btn_stop.clicked.connect(self.stop_server)
        lay.addWidget(self.btn_stop)

        self.btn_restart = QPushButton("↻   Restart")
        self.btn_restart.setToolTip("Stop and start the server.  Shortcut: F7")
        self.btn_restart.clicked.connect(self.restart_server)
        lay.addWidget(self.btn_restart)

        lay.addStretch()

        btn_share = QPushButton("Share info")
        btn_share.setToolTip("Copy server connection info to clipboard.")
        btn_share.clicked.connect(self.copy_share_info)
        lay.addWidget(btn_share)
        return wrap

    # ─────────────────────────── TABS ───────────────────────────────────────

    def _build_quick_tab(self):
        outer = QHBoxLayout(self.tab_quick)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        left = QVBoxLayout()
        right = QVBoxLayout()
        outer.addLayout(left, 1)
        outer.addLayout(right, 1)

        # Server group
        srv = QGroupBox("Server")
        form = QFormLayout(srv)
        form.setContentsMargins(12, 20, 12, 12)
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)

        self.server_name_edit = QLineEdit("ABOBA RACING")
        form.addRow("Server name", self.server_name_edit)

        self.server_password_edit = QLineEdit("aboba")
        self.server_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password", self.server_password_edit)

        self.admin_password_edit = QLineEdit("CHANGE_THIS_PASSWORD")
        self.admin_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Admin password", self.admin_password_edit)

        self.max_slots_spin = QSpinBox()
        self.max_slots_spin.setRange(1, 30)
        self.max_slots_spin.setValue(5)
        self.max_slots_spin.setToolTip("Max drivers (1–30). Above 10 requires Track Medals ≥ 3 + SA ≥ 70.")
        form.addRow("Max slots", self.max_slots_spin)

        self.car_group_combo = QComboBox()
        self.car_group_combo.addItems(CAR_GROUPS)
        form.addRow("Car group", self.car_group_combo)

        self.track_medals_spin = QSpinBox()
        self.track_medals_spin.setRange(0, 3)
        self.track_medals_spin.setToolTip("Track medals required (0 = no requirement, max 3).")
        form.addRow("Track medals", self.track_medals_spin)

        self.safety_rating_spin = QSpinBox()
        self.safety_rating_spin.setRange(-1, 99)
        self.safety_rating_spin.setValue(-1)
        self.safety_rating_spin.setToolTip("Minimum Safety Rating (SA) to join. -1 = no requirement.")
        form.addRow("Safety rating", self.safety_rating_spin)

        self.racecraft_rating_spin = QSpinBox()
        self.racecraft_rating_spin.setRange(-1, 99)
        self.racecraft_rating_spin.setValue(-1)
        self.racecraft_rating_spin.setToolTip("Minimum Racecraft Rating (RC) to join. -1 = no requirement.")
        form.addRow("Racecraft rating", self.racecraft_rating_spin)

        left.addWidget(srv)

        # Validation group
        val_box = QGroupBox("Validation")
        vl = QVBoxLayout(val_box)
        vl.setContentsMargins(12, 20, 12, 12)
        self.validation_status_lbl = QLabel("Not checked")
        self.validation_status_lbl.setObjectName("muted")
        vl.addWidget(self.validation_status_lbl)
        self.validation_text = QTextEdit()
        self.validation_text.setReadOnly(True)
        self.validation_text.setMaximumHeight(120)
        vl.addWidget(self.validation_text)
        left.addWidget(val_box)

        # Event group
        evt = QGroupBox("Event")
        eform = QFormLayout(evt)
        eform.setContentsMargins(12, 20, 12, 12)
        eform.setVerticalSpacing(8)
        eform.setHorizontalSpacing(12)

        self.track_combo = QComboBox()
        self.track_combo.addItems(ALL_TRACKS)
        self.track_combo.setCurrentText("monza")
        self.track_combo.currentTextChanged.connect(self._refresh_track_pack_label)
        eform.addRow("Track", self.track_combo)

        self.weather_combo = QComboBox()
        self.weather_combo.addItems(list(WEATHER_PRESETS.keys()))
        eform.addRow("Weather", self.weather_combo)

        self.hour_of_day_spin = QSpinBox()
        self.hour_of_day_spin.setRange(0, 23)
        self.hour_of_day_spin.setValue(12)
        self.hour_of_day_spin.setToolTip("In-game start hour (0–23). Affects lighting and track temperature.")
        eform.addRow("Hour of day", self.hour_of_day_spin)

        self.time_multiplier_spin = QSpinBox()
        self.time_multiplier_spin.setRange(1, 24)
        self.time_multiplier_spin.setValue(1)
        self.time_multiplier_spin.setToolTip("How fast in-game time passes. 1 = real time, 24 = full day per hour.")
        eform.addRow("Time multiplier", self.time_multiplier_spin)

        self.practice_minutes_spin = QSpinBox()
        self.practice_minutes_spin.setRange(5, 180)
        self.practice_minutes_spin.setValue(60)
        eform.addRow("Practice minutes", self.practice_minutes_spin)

        q_row = QHBoxLayout()
        self.enable_qualifying_cb = QCheckBox("Enable qualifying")
        self.enable_qualifying_cb.toggled.connect(self._update_session_controls)
        self.qualifying_minutes_spin = QSpinBox()
        self.qualifying_minutes_spin.setRange(5, 60)
        self.qualifying_minutes_spin.setValue(10)
        q_row.addWidget(self.enable_qualifying_cb)
        q_row.addWidget(self.qualifying_minutes_spin)
        q_row.addWidget(QLabel("min"))
        eform.addRow("", q_row)  # type: ignore[arg-type]

        r_row = QHBoxLayout()
        self.enable_race_cb = QCheckBox("Enable race")
        self.enable_race_cb.toggled.connect(self._update_session_controls)
        self.race_minutes_spin = QSpinBox()
        self.race_minutes_spin.setRange(5, 180)
        self.race_minutes_spin.setValue(20)
        r_row.addWidget(self.enable_race_cb)
        r_row.addWidget(self.race_minutes_spin)
        r_row.addWidget(QLabel("min"))
        eform.addRow("", r_row)  # type: ignore[arg-type]

        self.track_pack_inline = QLabel()
        self.track_pack_inline.setObjectName("muted")
        eform.addRow("", self.track_pack_inline)

        right.addWidget(evt)
        right.addStretch()

    def _build_tracks_tab(self):
        lay = QVBoxLayout(self.tab_tracks)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        filter_box = QGroupBox("Track filtering")
        fl = QVBoxLayout(filter_box)
        self.show_only_owned_cb = QCheckBox("Show only tracks from DLC/base packs I own")
        self.show_only_owned_cb.toggled.connect(self._refresh_track_values)
        fl.addWidget(self.show_only_owned_cb)
        lay.addWidget(filter_box)

        owned_box = QGroupBox("Owned packs")
        ol = QGridLayout(owned_box)
        ol.setContentsMargins(12, 20, 12, 12)
        self.track_group_cbs: dict[str, QCheckBox] = {}
        owned = self.app_config.get("owned_track_groups", {})
        for i, (group, tracks) in enumerate(TRACK_GROUPS.items()):
            cb = QCheckBox(f"{group}:  {', '.join(tracks)}")
            cb.setChecked(owned.get(group, group == "Base game"))
            cb.toggled.connect(self._refresh_track_values)
            ol.addWidget(cb, i // 2, i % 2)
            self.track_group_cbs[group] = cb
        lay.addWidget(owned_box)

        tip = QLabel("Tip: if a friend doesn't own a DLC track, use a base track like monza.")
        tip.setObjectName("muted")
        lay.addWidget(tip)
        lay.addStretch()

    def _build_presets_tab(self):
        lay = QVBoxLayout(self.tab_presets)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        box = QGroupBox("Presets")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 20, 12, 12)
        bl.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(self.preset_combo, 1)
        bl.addLayout(row)

        btns = QHBoxLayout()
        b_load = QPushButton("Load preset")
        b_load.clicked.connect(self.load_preset)
        b_save = QPushButton("Save current as preset")
        b_save.clicked.connect(self.save_preset)
        b_del  = QPushButton("Delete preset")
        b_del.clicked.connect(self.delete_preset)
        b_start = QPushButton("Create starter presets")
        b_start.clicked.connect(self.create_starter_presets)
        for b in [b_load, b_save, b_del, b_start]:
            btns.addWidget(b)
        btns.addStretch()
        bl.addLayout(btns)

        info = QLabel(
            "Presets are stored in acc_launcher_presets.json next to the launcher.\n"
            "They do not overwrite your server configs until you press Save configs or Start server."
        )
        info.setObjectName("muted")
        bl.addWidget(info)
        lay.addWidget(box)
        lay.addStretch()

    def _build_entry_tab(self):
        outer = QHBoxLayout(self.tab_entry)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # Driver list
        list_box = QGroupBox("Drivers")
        ll = QVBoxLayout(list_box)
        ll.setContentsMargins(12, 20, 12, 12)

        self.entry_tree = QTreeWidget()
        self.entry_tree.setAlternatingRowColors(True)
        self.entry_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.entry_tree.setHeaderLabels(["Name", "Steam ID", "Car model", "#"])
        self.entry_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.entry_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.entry_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.entry_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.entry_tree.header().resizeSection(3, 50)
        self.entry_tree.itemSelectionChanged.connect(self._on_entry_selected)
        ll.addWidget(self.entry_tree)

        btn_row = QHBoxLayout()
        b_load_el = QPushButton("Load entrylist")
        b_load_el.clicked.connect(self.load_entrylist)
        b_save_el = QPushButton("Save entrylist")
        b_save_el.clicked.connect(self.save_entrylist)
        b_rem = QPushButton("Remove selected")
        b_rem.clicked.connect(self.remove_selected_entry)
        for b in [b_load_el, b_save_el, b_rem]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        ll.addLayout(btn_row)
        outer.addWidget(list_box, 1)

        # Add / edit form
        form_box = QGroupBox("Add / Edit driver")
        form = QFormLayout(form_box)
        form.setContentsMargins(12, 20, 12, 12)
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(12)

        self.entry_name_edit  = QLineEdit()
        self.entry_steam_edit = QLineEdit()
        self.entry_steam_edit.setPlaceholderText("S76561198…")
        self.entry_steam_edit.setToolTip("Steam ID from server log, looks like S7656119xxxxxxxxx.")
        self.entry_car_combo = QComboBox()
        self.entry_car_combo.addItems(list(CAR_MODELS.keys()))
        self.entry_race_spin    = QSpinBox(); self.entry_race_spin.setRange(1, 999)
        self.entry_ballast_spin = QSpinBox(); self.entry_ballast_spin.setRange(0, 100)
        self.entry_ballast_spin.setToolTip("Extra weight in kg (0 = none).")
        self.entry_restrictor_spin = QSpinBox(); self.entry_restrictor_spin.setRange(0, 100)
        self.entry_restrictor_spin.setToolTip("Air restrictor 0–100. Reduces engine power.")

        form.addRow("Name",        self.entry_name_edit)
        form.addRow("Steam ID",    self.entry_steam_edit)
        form.addRow("Car",         self.entry_car_combo)
        form.addRow("Race number", self.entry_race_spin)
        form.addRow("Ballast kg",  self.entry_ballast_spin)
        form.addRow("Restrictor",  self.entry_restrictor_spin)

        entry_btns = QHBoxLayout()
        b_add = QPushButton("Add driver")
        b_add.clicked.connect(self.add_entry_item)
        b_upd = QPushButton("Update selected")
        b_upd.clicked.connect(self.update_selected_entry)
        entry_btns.addWidget(b_add); entry_btns.addWidget(b_upd)

        vl = form_box.layout()
        vl.addRow("", entry_btns)  # type: ignore[union-attr]

        tip = QLabel(
            "Entrylist is optional — use it as a whitelist for private servers.\n"
            "Steam ID looks like S7656119… in the server log."
        )
        tip.setObjectName("muted")
        vl.addRow("", tip)  # type: ignore[union-attr]
        outer.addWidget(form_box, 1)

    def _build_rules_tab(self):
        outer = QHBoxLayout(self.tab_rules)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # Assists
        assist_box = QGroupBox("Assists")
        al = QVBoxLayout(assist_box)
        al.setContentsMargins(12, 20, 12, 12)
        al.setSpacing(8)
        self.assist_auto_clutch_cb       = QCheckBox("Allow auto clutch");       self.assist_auto_clutch_cb.setChecked(True)
        self.assist_auto_engine_start_cb = QCheckBox("Allow auto engine start");  self.assist_auto_engine_start_cb.setChecked(True)
        self.assist_stability_cb         = QCheckBox("Allow stability control")
        self.assist_auto_pit_limiter_cb  = QCheckBox("Allow auto pit limiter");   self.assist_auto_pit_limiter_cb.setChecked(True)
        self.assist_auto_lights_cb       = QCheckBox("Allow auto lights");        self.assist_auto_lights_cb.setChecked(True)
        self.assist_auto_wipers_cb       = QCheckBox("Allow auto wipers");        self.assist_auto_wipers_cb.setChecked(True)
        for cb in [self.assist_auto_clutch_cb, self.assist_auto_engine_start_cb,
                   self.assist_stability_cb, self.assist_auto_pit_limiter_cb,
                   self.assist_auto_lights_cb, self.assist_auto_wipers_cb]:
            al.addWidget(cb)
        al.addStretch()
        outer.addWidget(assist_box, 1)

        # Rules
        rules_box = QGroupBox("Race rules")
        rform = QFormLayout(rules_box)
        rform.setContentsMargins(12, 20, 12, 12)
        rform.setVerticalSpacing(8)
        rform.setHorizontalSpacing(12)

        self.formation_lap_spin = QSpinBox(); self.formation_lap_spin.setRange(0, 3)
        self.formation_lap_spin.setValue(3)
        self.formation_lap_spin.setToolTip("0=disabled, 1=old pit-exit start, 2=formation in-game, 3=default controlled.")
        rform.addRow("Formation lap type", self.formation_lap_spin)

        self.mandatory_pit_spin = QSpinBox(); self.mandatory_pit_spin.setRange(0, 10)
        self.mandatory_pit_spin.setToolTip("Number of mandatory pit stops required per driver (0 = none).")
        rform.addRow("Mandatory pit stops", self.mandatory_pit_spin)

        self.pit_window_spin = QSpinBox(); self.pit_window_spin.setRange(-1, 7200); self.pit_window_spin.setValue(-1)
        self.pit_window_spin.setToolTip("Pit window duration in seconds. -1 = disabled.")
        rform.addRow("Pit window sec  (-1 = off)", self.pit_window_spin)

        self.stint_time_spin = QSpinBox(); self.stint_time_spin.setRange(-1, 7200); self.stint_time_spin.setValue(-1)
        self.stint_time_spin.setToolTip("Max consecutive driving time in seconds. -1 = disabled.")
        rform.addRow("Driver stint sec  (-1 = off)", self.stint_time_spin)

        self.max_driving_spin = QSpinBox(); self.max_driving_spin.setRange(-1, 20000); self.max_driving_spin.setValue(-1)
        self.max_driving_spin.setToolTip("Max total driving time per driver in seconds. -1 = disabled.")
        rform.addRow("Max total driving sec  (-1 = off)", self.max_driving_spin)

        self.tyre_set_spin = QSpinBox(); self.tyre_set_spin.setRange(1, 99); self.tyre_set_spin.setValue(50)
        self.tyre_set_spin.setToolTip("Number of tyre sets available per driver.")
        rform.addRow("Tyre set count", self.tyre_set_spin)

        tip = QLabel("These options write cfg/assistRules.json and cfg/eventRules.json.")
        tip.setObjectName("muted")
        rform.addRow("", tip)
        outer.addWidget(rules_box, 1)

    def _build_network_tab(self):
        lay = QVBoxLayout(self.tab_network)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        net = QGroupBox("Network settings")
        nf = QFormLayout(net)
        nf.setContentsMargins(12, 20, 12, 12)
        nf.setHorizontalSpacing(12)

        ports_row = QHBoxLayout()
        self.udp_port_spin = QSpinBox(); self.udp_port_spin.setRange(1000, 65535); self.udp_port_spin.setValue(9231)
        self.tcp_port_spin = QSpinBox(); self.tcp_port_spin.setRange(1000, 65535); self.tcp_port_spin.setValue(9232)
        ports_row.addWidget(QLabel("UDP")); ports_row.addWidget(self.udp_port_spin)
        ports_row.addSpacing(20)
        ports_row.addWidget(QLabel("TCP")); ports_row.addWidget(self.tcp_port_spin)
        ports_row.addStretch()
        nf.addRow("Ports", ports_row)

        cb_row = QHBoxLayout()
        self.register_to_lobby_cb = QCheckBox("Register to ACC lobby"); self.register_to_lobby_cb.setChecked(True)
        self.lan_discovery_cb     = QCheckBox("LAN discovery");          self.lan_discovery_cb.setChecked(True)
        cb_row.addWidget(self.register_to_lobby_cb)
        cb_row.addWidget(self.lan_discovery_cb)
        cb_row.addStretch()
        nf.addRow("", cb_row)
        lay.addWidget(net)

        checks = QGroupBox("Tools")
        cl = QHBoxLayout(checks)
        cl.setContentsMargins(12, 20, 12, 12)
        for label, fn in [
            ("Check local ports",          self.check_local_ports),
            ("Create Firewall rules",       self.create_firewall_rules),
            ("Copy IPs for friend",         self.copy_ips),
            ("Create safe start.bat",       self.create_start_bat),
        ]:
            b = QPushButton(label); b.clicked.connect(fn); cl.addWidget(b)
        cl.addStretch()
        lay.addWidget(checks)

        self.network_text = QTextEdit()
        self.network_text.setReadOnly(True)
        lay.addWidget(self.network_text, 1)

    def _build_logs_tab(self):
        lay = QVBoxLayout(self.tab_logs)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        filter_row = QHBoxLayout()
        self.log_errors_only_cb   = QCheckBox("Errors only")
        self.log_connections_cb   = QCheckBox("Show connections"); self.log_connections_cb.setChecked(True)
        self.log_lobby_cb         = QCheckBox("Show lobby");       self.log_lobby_cb.setChecked(True)
        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(self._clear_log)
        for w in [self.log_errors_only_cb, self.log_connections_cb, self.log_lobby_cb]:
            filter_row.addWidget(w)
        filter_row.addStretch()
        filter_row.addWidget(btn_clear)
        lay.addLayout(filter_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        lay.addWidget(self.log_text, 1)

    # ─────────────────────────── THEME ──────────────────────────────────────

    def _apply_theme(self, theme_name: str):
        if theme_name not in PALETTES:
            return
        self.theme_mode = theme_name
        self.palette = PALETTES[theme_name]
        qss = _qss_dark() if theme_name == "dark" else _qss_light()
        app = QApplication.instance()
        app.setStyleSheet(qss)
        style = app.style()
        if isinstance(style, AccStyle):
            style.set_color(self.palette["muted"])
        self._apply_log_colors()
        self._save_app_config()

    def _apply_log_colors(self):
        pass  # Colors are applied per-line via QTextCharFormat

    # ─────────────────────────── STATUS HELPERS ─────────────────────────────

    def _set_server_badge(self, running: bool):
        lbl = self.server_status_lbl
        p = self.palette
        if running:
            lbl.setStyleSheet(
                f"color: {p['success']}; background-color: transparent;"
                f"border: 1px solid {p['success']}44; border-radius: 5px;"
                f"padding: 5px 12px; font-weight: 600; font-size: 9pt;"
            )
        else:
            lbl.setStyleSheet(
                f"color: {p['muted']}; background-color: transparent;"
                f"border: 1px solid {p['border']}; border-radius: 5px;"
                f"padding: 5px 12px; font-size: 9pt;"
            )

    def _update_window_title(self, running: bool = False):
        name = self.server_name_edit.text().strip() or "unnamed"
        if running:
            self.setWindowTitle(f"[RUNNING]  {name}  —  ACC Server Control  v{APP_VERSION}")
        else:
            self.setWindowTitle(f"ACC Server Control  v{APP_VERSION}")

    # ─────────────────────────── SESSION CONTROLS ───────────────────────────

    def _update_session_controls(self):
        self.qualifying_minutes_spin.setEnabled(self.enable_qualifying_cb.isChecked())
        self.race_minutes_spin.setEnabled(self.enable_race_cb.isChecked())

    # ─────────────────────────── TRACK HELPERS ──────────────────────────────

    def _refresh_track_values(self):
        show_owned = self.show_only_owned_cb.isChecked()
        values = []
        for group, tracks in TRACK_GROUPS.items():
            if not show_owned or self.track_group_cbs[group].isChecked():
                values.extend(tracks)
        if not values:
            values = TRACK_GROUPS["Base game"]
        current = self.track_combo.currentText()
        self.track_combo.clear()
        self.track_combo.addItems(values)
        if current in values:
            self.track_combo.setCurrentText(current)
        self._refresh_track_pack_label()
        self._save_app_config()

    def _refresh_track_pack_label(self):
        track = self.track_combo.currentText()
        group = TRACK_TO_GROUP.get(track, "Unknown pack")
        text = f"Track pack: {group}"
        self.track_pack_lbl.setText(text)
        if hasattr(self, "track_pack_inline"):
            self.track_pack_inline.setText(text)

    # ─────────────────────────── PRESETS ────────────────────────────────────

    def _refresh_preset_list(self):
        self.preset_combo.clear()
        self.preset_combo.addItems(sorted(self.presets.keys()))

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Preset name", "Enter preset name:",
                                        text=self.preset_combo.currentText() or "Monza Practice")
        if not ok or not name:
            return
        self.presets[name] = self._snapshot()
        write_json(Path(PRESETS_FILE), self.presets)
        self._refresh_preset_list()
        self.preset_combo.setCurrentText(name)
        self._log("Preset saved: " + name)

    def load_preset(self):
        name = self.preset_combo.currentText()
        if not name or name not in self.presets:
            QMessageBox.warning(self, "Preset", "Choose a preset first.")
            return
        self._apply_snapshot(self.presets[name])
        self._log(f"Preset loaded: {name}")

    def delete_preset(self):
        name = self.preset_combo.currentText()
        if not name or name not in self.presets:
            return
        if QMessageBox.question(self, "Delete preset", f"Delete preset '{name}'?") != QMessageBox.StandardButton.Yes:
            return
        self.presets.pop(name, None)
        write_json(Path(PRESETS_FILE), self.presets)
        self._refresh_preset_list()
        self._log(f"Preset deleted: {name}")

    def create_starter_presets(self):
        starter = {
            "Monza Practice":     self._quick_preset("monza", "Dry", False, False, 60, 0, 0),
            "Spa Practice":       self._quick_preset("spa", "Dry", False, False, 60, 0, 0),
            "Nurburgring Practice": self._quick_preset("nurburgring", "Dry", False, False, 60, 0, 0),
            "Private Race Weekend": self._quick_preset("monza", "Dry", True, True, 30, 10, 20),
            "Wet Practice":       self._quick_preset("silverstone", "Light rain", False, False, 60, 0, 0),
        }
        self.presets.update(starter)
        write_json(Path(PRESETS_FILE), self.presets)
        self._refresh_preset_list()
        self._log("Starter presets created.")

    def _quick_preset(self, track, weather, q, r, p_min, q_min, r_min):
        old = self._snapshot()
        self.track_combo.setCurrentText(track)
        self.weather_combo.setCurrentText(weather)
        self.enable_qualifying_cb.setChecked(q)
        self.enable_race_cb.setChecked(r)
        self.practice_minutes_spin.setValue(p_min)
        if q: self.qualifying_minutes_spin.setValue(q_min)
        if r: self.race_minutes_spin.setValue(r_min)
        snap = self._snapshot()
        self._apply_snapshot(old)
        return snap

    # ─────────────────────────── ENTRY LIST ─────────────────────────────────

    def load_entrylist(self, silent=False):
        paths = self._get_paths()
        data = read_json(paths.entrylist, {"entries": []})
        self.entry_items = data.get("entries", []) if isinstance(data, dict) else []
        self._refresh_entry_tree()
        if not silent:
            self._log("Entrylist loaded.")

    def save_entrylist(self, silent=False):
        if not self.server_dir_edit.text().strip():
            return
        paths = self._get_paths()
        write_json(paths.entrylist, {"entries": self.entry_items, "configVersion": 1})
        if not silent:
            self._log("Entrylist saved.")

    def _refresh_entry_tree(self):
        self.entry_tree.clear()
        for i, entry in enumerate(self.entry_items):
            driver = entry.get("drivers", [{}])[0]
            item = QTreeWidgetItem([
                driver.get("firstName", entry.get("firstName", "")),
                driver.get("playerID", ""),
                str(entry.get("forcedCarModel", -1)),
                str(entry.get("raceNumber", "")),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, i)
            self.entry_tree.addTopLevelItem(item)

    def _on_entry_selected(self):
        items = self.entry_tree.selectedItems()
        if not items:
            return
        self.selected_entry_index = items[0].data(0, Qt.ItemDataRole.UserRole)
        entry = self.entry_items[self.selected_entry_index]
        driver = entry.get("drivers", [{}])[0]
        self.entry_name_edit.setText(driver.get("firstName", entry.get("firstName", "")))
        self.entry_steam_edit.setText(driver.get("playerID", ""))
        model = int(entry.get("forcedCarModel", -1))
        label = next((k for k, v in CAR_MODELS.items() if v == model), "Any / keep default")
        self.entry_car_combo.setCurrentText(label)
        self.entry_race_spin.setValue(int(entry.get("raceNumber", 1)))
        self.entry_ballast_spin.setValue(int(entry.get("ballastKg", 0)))
        self.entry_restrictor_spin.setValue(int(entry.get("restrictor", 0)))

    def _entry_form_to_item(self):
        player_id = self.entry_steam_edit.text().strip()
        if player_id and not player_id.startswith("S"):
            player_id = "S" + player_id
        car_model = CAR_MODELS.get(self.entry_car_combo.currentText(), -1)
        name = self.entry_name_edit.text().strip() or "Driver"
        return {
            "drivers": [{
                "firstName": name, "lastName": "",
                "shortName": name[:3].upper(),
                "driverCategory": 0, "playerID": player_id,
            }],
            "raceNumber": self.entry_race_spin.value(),
            "forcedCarModel": int(car_model),
            "overrideDriverInfo": 1,
            "isServerAdmin": 0,
            "defaultGridPosition": -1,
            "ballastKg": self.entry_ballast_spin.value(),
            "restrictor": self.entry_restrictor_spin.value(),
            "customCar": "",
            "firstName": name,
        }

    def add_entry_item(self):
        if not self.entry_steam_edit.text().strip():
            QMessageBox.warning(self, "Entrylist", "Steam ID is required.")
            return
        self.entry_items.append(self._entry_form_to_item())
        self._refresh_entry_tree()

    def update_selected_entry(self):
        if self.selected_entry_index is None or self.selected_entry_index >= len(self.entry_items):
            QMessageBox.warning(self, "Entrylist", "Choose a driver first.")
            return
        self.entry_items[self.selected_entry_index] = self._entry_form_to_item()
        self._refresh_entry_tree()

    def remove_selected_entry(self):
        items = self.entry_tree.selectedItems()
        if not items:
            return
        idx = items[0].data(0, Qt.ItemDataRole.UserRole)
        self.entry_items.pop(idx)
        self.selected_entry_index = None
        self._refresh_entry_tree()

    # ─────────────────────────── SERVER FOLDER ──────────────────────────────

    def choose_server_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder containing accServer.exe")
        if folder:
            self.server_dir_edit.setText(folder)
            self._save_app_config()
            self.load_existing_configs(silent=True)

    def open_server_folder(self):
        folder = self.server_dir_edit.text().strip()
        if not folder:
            return
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])

    def _get_paths(self) -> Paths:
        raw = self.server_dir_edit.text().strip().strip('"')
        server = Path(raw).expanduser().resolve()
        cfg = server / "cfg"
        return Paths(
            server=server, exe=server / "accServer.exe", cfg=cfg,
            settings=cfg / "settings.json", event=cfg / "event.json",
            configuration=cfg / "configuration.json",
            assist_rules=cfg / "assistRules.json",
            event_rules=cfg / "eventRules.json",
            entrylist=cfg / "entrylist.json",
            log_dir=server / "log", results_dir=server / "results",
            backups_dir=server / "backups",
        )

    def _validate_server_folder(self, show=True) -> bool:
        paths = self._get_paths()
        errors = []
        if not paths.server.exists():
            errors.append("Server folder does not exist.")
        if not paths.exe.exists():
            errors.append("accServer.exe not found. Choose the folder where accServer.exe is located.")
        if not paths.cfg.exists():
            errors.append("cfg folder not found.")
        if errors and show:
            QMessageBox.critical(self, "Server folder error", "\n".join(errors))
        return not errors

    # ─────────────────────────── CONFIG I/O ─────────────────────────────────

    def load_existing_configs(self, silent=False):
        if not self.server_dir_edit.text().strip():
            if not silent:
                QMessageBox.warning(self, "Warning", "Choose server folder first.")
            return
        if not self._validate_server_folder(show=not silent):
            return
        paths = self._get_paths()
        settings = read_json(paths.settings, {})
        event    = read_json(paths.event, {})
        config   = read_json(paths.configuration, {})
        assist   = read_json(paths.assist_rules, {})
        rules    = read_json(paths.event_rules, {})

        self.server_name_edit.setText(settings.get("serverName", self.server_name_edit.text()))
        self.server_password_edit.setText(settings.get("password", ""))
        self.admin_password_edit.setText(settings.get("adminPassword", ""))
        self.max_slots_spin.setValue(int(settings.get("maxCarSlots", 5)))
        idx = self.car_group_combo.findText(settings.get("carGroup", "GT3"))
        if idx >= 0: self.car_group_combo.setCurrentIndex(idx)
        self.track_medals_spin.setValue(int(settings.get("trackMedalsRequirement", 0)))
        self.safety_rating_spin.setValue(int(settings.get("safetyRatingRequirement", -1)))
        self.racecraft_rating_spin.setValue(int(settings.get("racecraftRatingRequirement", -1)))

        track = event.get("track", "monza")
        if self.track_combo.findText(track) >= 0:
            self.track_combo.setCurrentText(track)
        weather = next((k for k, v in WEATHER_PRESETS.items()
                        if v["rain"] == event.get("rain", 0)
                        and v["cloudLevel"] == event.get("cloudLevel", 0)), "Dry")
        self.weather_combo.setCurrentText(weather)

        self.enable_qualifying_cb.setChecked(False)
        self.enable_race_cb.setChecked(False)
        for session in event.get("sessions", []):
            st = session.get("sessionType")
            dur = int(session.get("sessionDurationMinutes", 0))
            if st == "P":
                self.practice_minutes_spin.setValue(dur or 60)
                self.hour_of_day_spin.setValue(int(session.get("hourOfDay", 12)))
                self.time_multiplier_spin.setValue(int(session.get("timeMultiplier", 1)))
            elif st == "Q":
                self.enable_qualifying_cb.setChecked(True)
                self.qualifying_minutes_spin.setValue(dur or 10)
            elif st == "R":
                self.enable_race_cb.setChecked(True)
                self.race_minutes_spin.setValue(dur or 20)

        self.udp_port_spin.setValue(int(config.get("udpPort", 9231)))
        self.tcp_port_spin.setValue(int(config.get("tcpPort", 9232)))
        self.register_to_lobby_cb.setChecked(bool(config.get("registerToLobby", 1)))
        self.lan_discovery_cb.setChecked(bool(config.get("lanDiscovery", 1)))

        self.assist_auto_clutch_cb.setChecked(not assist.get("disableAutoClutch", 0))
        self.assist_auto_engine_start_cb.setChecked(not assist.get("disableAutoEngineStart", 0))
        self.assist_stability_cb.setChecked(assist.get("stabilityControlLevelMax", 0) > 0)
        self.assist_auto_pit_limiter_cb.setChecked(not assist.get("disableAutoPitLimiter", 0))
        self.assist_auto_lights_cb.setChecked(not assist.get("disableAutoLights", 0))
        self.assist_auto_wipers_cb.setChecked(not assist.get("disableAutoWipers", 0))

        self.formation_lap_spin.setValue(int(rules.get("formationLapType", 3)))
        self.mandatory_pit_spin.setValue(int(rules.get("mandatoryPitstopCount", 0)))
        self.pit_window_spin.setValue(int(rules.get("pitWindowLengthSec", -1)))
        self.stint_time_spin.setValue(int(rules.get("driverStintTimeSec", -1)))
        self.max_driving_spin.setValue(int(rules.get("maxTotalDrivingTime", -1)))
        self.tyre_set_spin.setValue(int(rules.get("tyreSetCount", 50)))

        self.load_entrylist(silent=True)
        self._save_app_config()
        self._log("Configs loaded.")

    def _build_settings_json(self):
        return {
            "serverName": self.server_name_edit.text().strip() or "ACC Server",
            "adminPassword": self.admin_password_edit.text().strip() or "CHANGE_THIS_PASSWORD",
            "carGroup": self.car_group_combo.currentText(),
            "trackMedalsRequirement": self.track_medals_spin.value(),
            "safetyRatingRequirement": self.safety_rating_spin.value(),
            "racecraftRatingRequirement": self.racecraft_rating_spin.value(),
            "password": self.server_password_edit.text(),
            "maxCarSlots": self.max_slots_spin.value(),
            "spectatorPassword": "",
            "configVersion": 1,
        }

    def _build_event_json(self):
        weather = WEATHER_PRESETS.get(self.weather_combo.currentText(), WEATHER_PRESETS["Dry"])
        hour = self.hour_of_day_spin.value()
        mult = self.time_multiplier_spin.value()
        sessions = [{
            "hourOfDay": hour, "dayOfWeekend": 1, "timeMultiplier": mult,
            "sessionType": "P",
            "sessionDurationMinutes": self.practice_minutes_spin.value(),
        }]
        if self.enable_qualifying_cb.isChecked():
            sessions.append({
                "hourOfDay": min(hour + 1, 23), "dayOfWeekend": 1, "timeMultiplier": mult,
                "sessionType": "Q",
                "sessionDurationMinutes": self.qualifying_minutes_spin.value(),
            })
        if self.enable_race_cb.isChecked():
            sessions.append({
                "hourOfDay": min(hour + 2, 23), "dayOfWeekend": 1, "timeMultiplier": mult,
                "sessionType": "R",
                "sessionDurationMinutes": self.race_minutes_spin.value(),
            })
        return {
            "track": self.track_combo.currentText(),
            "preRaceWaitingTimeSeconds": 60,
            "sessionOverTimeSeconds": 120,
            **weather,
            "sessions": sessions,
            "configVersion": 1,
        }

    def _build_configuration_json(self):
        return {
            "udpPort": self.udp_port_spin.value(),
            "tcpPort": self.tcp_port_spin.value(),
            "maxConnections": 85,
            "registerToLobby": 1 if self.register_to_lobby_cb.isChecked() else 0,
            "lanDiscovery": 1 if self.lan_discovery_cb.isChecked() else 0,
            "configVersion": 1,
        }

    def _build_assist_rules_json(self):
        return {
            "disableAutoClutch":      0 if self.assist_auto_clutch_cb.isChecked() else 1,
            "disableAutoEngineStart": 0 if self.assist_auto_engine_start_cb.isChecked() else 1,
            "stabilityControlLevelMax": 100 if self.assist_stability_cb.isChecked() else 0,
            "disableAutoPitLimiter":  0 if self.assist_auto_pit_limiter_cb.isChecked() else 1,
            "disableAutoLights":      0 if self.assist_auto_lights_cb.isChecked() else 1,
            "disableAutoWipers":      0 if self.assist_auto_wipers_cb.isChecked() else 1,
        }

    def _build_event_rules_json(self):
        return {
            "qualifyStandingType": 1,
            "pitWindowLengthSec":  self.pit_window_spin.value(),
            "driverStintTimeSec":  self.stint_time_spin.value(),
            "mandatoryPitstopCount": self.mandatory_pit_spin.value(),
            "maxTotalDrivingTime": self.max_driving_spin.value(),
            "maxDriversCount": 1,
            "isRefuellingAllowedInRace": True,
            "isRefuellingTimeFixed": False,
            "isMandatoryPitstopRefuellingRequired": False,
            "isMandatoryPitstopTyreChangeRequired": False,
            "isMandatoryPitstopSwapDriverRequired": False,
            "tyreSetCount": self.tyre_set_spin.value(),
            "formationLapType": self.formation_lap_spin.value(),
        }

    # ─────────────────────────── SNAPSHOT ───────────────────────────────────

    def _snapshot(self):
        return {
            "settings":    self._build_settings_json(),
            "event":       self._build_event_json(),
            "configuration": self._build_configuration_json(),
            "assistRules": self._build_assist_rules_json(),
            "eventRules":  self._build_event_rules_json(),
            "entrylist":   self.entry_items,
            "weather":     self.weather_combo.currentText(),
        }

    def _apply_snapshot(self, snap):
        s = snap.get("settings", {})
        e = snap.get("event", {})
        c = snap.get("configuration", {})
        a = snap.get("assistRules", {})
        r = snap.get("eventRules", {})

        self.server_name_edit.setText(s.get("serverName", ""))
        self.admin_password_edit.setText(s.get("adminPassword", ""))
        self.server_password_edit.setText(s.get("password", ""))
        self.max_slots_spin.setValue(int(s.get("maxCarSlots", 5)))
        idx = self.car_group_combo.findText(s.get("carGroup", "GT3"))
        if idx >= 0: self.car_group_combo.setCurrentIndex(idx)
        self.track_medals_spin.setValue(int(s.get("trackMedalsRequirement", 0)))
        self.safety_rating_spin.setValue(int(s.get("safetyRatingRequirement", -1)))
        self.racecraft_rating_spin.setValue(int(s.get("racecraftRatingRequirement", -1)))

        track = e.get("track", "monza")
        if self.track_combo.findText(track) >= 0:
            self.track_combo.setCurrentText(track)
        self.weather_combo.setCurrentText(snap.get("weather", "Dry"))
        self.udp_port_spin.setValue(int(c.get("udpPort", 9231)))
        self.tcp_port_spin.setValue(int(c.get("tcpPort", 9232)))
        self.register_to_lobby_cb.setChecked(bool(c.get("registerToLobby", 1)))
        self.lan_discovery_cb.setChecked(bool(c.get("lanDiscovery", 1)))

        self.enable_qualifying_cb.setChecked(False)
        self.enable_race_cb.setChecked(False)
        for session in e.get("sessions", []):
            if session.get("sessionType") == "P":
                self.practice_minutes_spin.setValue(int(session.get("sessionDurationMinutes", 60)))
                self.hour_of_day_spin.setValue(int(session.get("hourOfDay", 12)))
                self.time_multiplier_spin.setValue(int(session.get("timeMultiplier", 1)))
            elif session.get("sessionType") == "Q":
                self.enable_qualifying_cb.setChecked(True)
                self.qualifying_minutes_spin.setValue(int(session.get("sessionDurationMinutes", 10)))
            elif session.get("sessionType") == "R":
                self.enable_race_cb.setChecked(True)
                self.race_minutes_spin.setValue(int(session.get("sessionDurationMinutes", 20)))

        self.assist_auto_clutch_cb.setChecked(not a.get("disableAutoClutch", 0))
        self.assist_auto_engine_start_cb.setChecked(not a.get("disableAutoEngineStart", 0))
        self.assist_stability_cb.setChecked(a.get("stabilityControlLevelMax", 0) > 0)
        self.assist_auto_pit_limiter_cb.setChecked(not a.get("disableAutoPitLimiter", 0))
        self.assist_auto_lights_cb.setChecked(not a.get("disableAutoLights", 0))
        self.assist_auto_wipers_cb.setChecked(not a.get("disableAutoWipers", 0))

        self.formation_lap_spin.setValue(int(r.get("formationLapType", 3)))
        self.mandatory_pit_spin.setValue(int(r.get("mandatoryPitstopCount", 0)))
        self.pit_window_spin.setValue(int(r.get("pitWindowLengthSec", -1)))
        self.stint_time_spin.setValue(int(r.get("driverStintTimeSec", -1)))
        self.max_driving_spin.setValue(int(r.get("maxTotalDrivingTime", -1)))
        self.tyre_set_spin.setValue(int(r.get("tyreSetCount", 50)))

        self.entry_items = snap.get("entrylist", [])
        self._refresh_entry_tree()

    # ─────────────────────────── VALIDATION ─────────────────────────────────

    def validate_config(self):
        errors, warnings = [], []
        if not self.server_name_edit.text().strip():
            errors.append("Server name is empty.")
        slots = self.max_slots_spin.value()
        if slots < 1 or slots > 30:
            errors.append("Max slots must be between 1 and 30.")
        if slots > 10 and not (self.track_medals_spin.value() >= 3 and self.safety_rating_spin.value() >= 70):
            errors.append("maxCarSlots above 10 needs Track Medals ≥ 3 and Safety Rating ≥ 70, or reduce slots to ≤ 10.")
        if self.track_medals_spin.value() < 0:
            errors.append("trackMedalsRequirement cannot be -1. Use 0 for private servers.")
        if self.udp_port_spin.value() == self.tcp_port_spin.value():
            errors.append("UDP and TCP ports must be different.")
        track = self.track_combo.currentText()
        if track not in ALL_TRACKS:
            warnings.append("Selected track is not in the built-in list.")
        group = TRACK_TO_GROUP.get(track)
        if group and group != "Base game":
            warnings.append(f"{track} requires DLC pack: {group}. Your friend must own it too.")
        if not self.register_to_lobby_cb.isChecked() and not self.lan_discovery_cb.isChecked():
            warnings.append("Both lobby and LAN are disabled — server may be hard to find.")
        if not self.server_password_edit.text():
            warnings.append("No server password — public servers are ok, but not ideal for private races.")
        if self.practice_minutes_spin.value() < 5:
            errors.append("Practice duration must be at least 5 minutes.")
        return errors, warnings

    def validate_and_show(self):
        errors, warnings = self.validate_config()
        self.validation_text.clear()
        p = self.palette
        cursor = self.validation_text.textCursor()

        def _append(text, color):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
            self.validation_text.setTextCursor(cursor)

        if not errors and not warnings:
            self.validation_status_lbl.setText("✓  Validation OK")
            _append("No problems found.\n", p["success"])
            return True
        if errors:
            self.validation_status_lbl.setText(f"✗  {len(errors)} error(s)")
            _append("Errors:\n", p["error"])
            for e in errors:
                _append(f"  ✗  {e}\n", p["error"])
        if warnings:
            if not errors:
                self.validation_status_lbl.setText(f"⚠  {len(warnings)} warning(s)")
            _append("\nWarnings:\n", p["warning"])
            for w in warnings:
                _append(f"  ⚠  {w}\n", p["warning"])
        return not errors

    # ─────────────────────────── SAVE ───────────────────────────────────────

    def _create_backup(self):
        paths = self._get_paths()
        ts_dir = paths.backups_dir / now_stamp()
        ts_dir.mkdir(parents=True, exist_ok=True)
        for src in [paths.settings, paths.event, paths.configuration,
                    paths.assist_rules, paths.event_rules, paths.entrylist]:
            if src.exists():
                shutil.copy2(src, ts_dir / src.name)
        self._log(f"Backup created: {ts_dir}")

    def save_configs(self):
        if not self._validate_server_folder():
            return False
        if not self.validate_and_show():
            QMessageBox.critical(self, "Validation failed", "Fix errors before saving configs.")
            return False
        paths = self._get_paths()
        paths.log_dir.mkdir(exist_ok=True)
        paths.results_dir.mkdir(exist_ok=True)
        self._create_backup()
        write_json(paths.settings, self._build_settings_json())
        write_json(paths.event, self._build_event_json())
        write_json(paths.configuration, self._build_configuration_json())
        write_json(paths.assist_rules, self._build_assist_rules_json())
        write_json(paths.event_rules, self._build_event_rules_json())
        self.save_entrylist(silent=True)
        self._save_app_config()
        self._log("Configs saved.")
        return True

    def _save_app_config(self):
        self.app_config["server_dir"]   = self.server_dir_edit.text()
        self.app_config["theme_mode"]   = self.theme_mode
        self.app_config["show_only_owned_tracks"] = self.show_only_owned_cb.isChecked() if hasattr(self, "show_only_owned_cb") else False
        self.app_config["owned_track_groups"] = {
            g: cb.isChecked() for g, cb in self.track_group_cbs.items()
        } if hasattr(self, "track_group_cbs") else {}
        write_json(Path(APP_CONFIG_FILE), self.app_config)

    # ─────────────────────────── SERVER PROCESS ─────────────────────────────

    def _prepare_runtime_folders(self):
        paths = self._get_paths()
        for folder in [paths.log_dir, paths.server / "logs", paths.results_dir, paths.backups_dir]:
            if folder.exists() and not folder.is_dir():
                QMessageBox.critical(self, "Folder error",
                    f"ACC needs this path to be a folder, but it is a file:\n{folder}\n\nRename or delete it, then try again.")
                return False
            folder.mkdir(parents=True, exist_ok=True)
        log_file = paths.log_dir / "server.log"
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8"):
                pass
        except PermissionError:
            pids = self._find_running_server_pids()
            hint = (f"\n\nAnother ACC server is running and holding this file.\nPID(s): {', '.join(str(p) for p in pids)}"
                    if pids else "\n\nAnother process is holding this file open.")
            QMessageBox.critical(self, "Log file is busy",
                f"ACC cannot start because this file is locked:\n{log_file}{hint}\n\nStop the other server first.")
            return False
        except Exception as exc:
            QMessageBox.critical(self, "Log file error", f"Cannot access log file:\n{log_file}\n\n{exc}")
            return False
        return True

    def _find_running_server_pids(self):
        if os.name != "nt":
            return []
        code, out, _ = run_command(["tasklist", "/FI", "IMAGENAME eq accServer.exe", "/FO", "CSV", "/NH"], timeout=8)
        if code != 0 or not out.strip():
            return []
        pids = []
        for row in parse_csv_lines(out):
            if len(row) >= 2 and row[0].strip().lower() == "accserver.exe":
                try:
                    pids.append(int(row[1]))
                except ValueError:
                    pass
        return pids

    def start_server(self):
        if self.process and self.process.poll() is None:
            QMessageBox.information(self, "Info", "Server is already running from this launcher.")
            return
        running_pids = self._find_running_server_pids()
        if running_pids:
            QMessageBox.warning(self, "Server already running",
                f"Another accServer.exe is already running.\nPID(s): {', '.join(str(p) for p in running_pids)}\n\nStop it first.")
            self.server_status_lbl.setText(f"External server running: PID {running_pids[0]}")
            return
        if not self.save_configs():
            return
        if not self._prepare_runtime_folders():
            return
        paths = self._get_paths()
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(
                [str(paths.exe)], cwd=str(paths.server),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=flags,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Start error", str(exc))
            return

        self.server_reader = ServerReader(self.process, self)
        self.server_reader.line_received.connect(self._on_log_line)
        self.server_reader.process_stopped.connect(self._on_process_stopped)
        self.server_reader.start()

        self.server_status_lbl.setText(f"Server running, PID {self.process.pid}")
        self._set_server_badge(True)
        self._update_window_title(True)
        self._log(f"Started accServer.exe, PID {self.process.pid}")
        self.tab_widget.setCurrentWidget(self.tab_logs)
        QTimer.singleShot(1500, self.check_local_ports)

    def stop_server(self):
        target_pids = []
        if self.process and self.process.poll() is None:
            target_pids.append(self.process.pid)
        else:
            target_pids.extend(self._find_running_server_pids())

        if not target_pids:
            self.server_status_lbl.setText("Server stopped")
            self._log("Server is not running.")
            return

        self._log(f"Stopping server PID(s): {', '.join(str(p) for p in target_pids)}")
        try:
            if os.name == "nt":
                for pid in target_pids:
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self.process:
                self.process.terminate()
            time.sleep(0.5)
        except Exception as exc:
            self._log(f"Stop error: {exc}")

        self.server_status_lbl.setText("Server stopped")
        self.player_status_lbl.setText("Players: 0")
        self.lobby_status_lbl.setText("Lobby: unknown")
        self._set_server_badge(False)
        self._update_window_title(False)
        self._log("Server stopped.")

    def restart_server(self):
        self.stop_server()
        QTimer.singleShot(1200, self.start_server)

    def _on_process_stopped(self, code: int):
        self.server_status_lbl.setText("Server stopped")
        self._set_server_badge(False)
        self._update_window_title(False)
        self._log(f"Process exited with code {code}")

    def _on_log_line(self, line: str):
        if "RegisterToLobby succeeded" in line or "Lobby accepted connection" in line:
            self.lobby_status_lbl.setText("Lobby: registered")
        if "Updated lobby with" in line and "drivers" in line:
            m = re.search(r"Updated lobby with (\d+) drivers", line)
            if m: self.player_status_lbl.setText(f"Players: {m.group(1)}")
        if "client(s) online" in line:
            m = re.search(r"(\d+) client\(s\) online", line)
            if m: self.player_status_lbl.setText(f"Players: {m.group(1)}")
        self._log(line)

    # ─────────────────────────── LOGGING ────────────────────────────────────

    def _should_show_line(self, message: str) -> bool:
        if self.log_errors_only_cb.isChecked():
            return any(t in message for t in LOG_TAGS["error"])
        if not self.log_connections_cb.isChecked() and any(t in message for t in LOG_TAGS["connection"]):
            return False
        if not self.log_lobby_cb.isChecked() and "lobby" in message.lower():
            return False
        return True

    def _get_log_color(self, message: str) -> str:
        p = self.palette
        for tag, tokens in LOG_TAGS.items():
            if any(t in message for t in tokens):
                return p.get(tag, p["text"])
        return p["text"]

    def _log(self, message: str):
        if not hasattr(self, "log_text"):
            return
        if not self._should_show_line(message):
            return
        color = self._get_log_color(message)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(message + "\n")
        self.log_text.ensureCursorVisible()

    def _clear_log(self):
        self.log_text.clear()

    # ─────────────────────────── NETWORK ────────────────────────────────────

    def check_local_ports(self):
        tcp = self.tcp_port_spin.value()
        udp = self.udp_port_spin.value()
        lines = []
        if os.name == "nt":
            code, out, err = run_command(["netstat", "-ano"], timeout=8)
            if code != 0:
                lines.append(f"netstat error: {err}")
            else:
                tcp_ok = f":{tcp}" in out and "LISTENING" in out
                udp_ok = f":{udp}" in out and "UDP" in out
                lines.append(f"TCP {tcp}: {'LISTENING ✓' if tcp_ok else 'not listening'}")
                lines.append(f"UDP {udp}: {'listening ✓' if udp_ok else 'not found'}")
                self.port_status_lbl.setText(f"TCP {tcp}: {'OK' if tcp_ok else 'no'}  |  UDP {udp}: {'OK' if udp_ok else 'no'}")
        else:
            lines.append("Port check is Windows-only in this version.")
        lines += ["", "Local IPv4 addresses:"] + [f"  {ip}" for ip in get_local_ipv4_addresses()]
        self.network_text.setPlainText("\n".join(lines))

    def create_firewall_rules(self):
        if os.name != "nt":
            QMessageBox.warning(self, "Firewall", "This helper is Windows-only.")
            return
        if not is_windows_admin():
            QMessageBox.warning(self, "Admin required", "Run launcher as Administrator to create firewall rules.")
            return
        tcp = self.tcp_port_spin.value()
        udp = self.udp_port_spin.value()
        for proto, port in [("TCP", tcp), ("UDP", udp)]:
            run_command([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                f"New-NetFirewallRule -DisplayName 'ACC Server {proto} {port}' "
                f"-Direction Inbound -Protocol {proto} -LocalPort {port} -Action Allow -ErrorAction SilentlyContinue"
            ], timeout=15)
        self._log(f"Firewall rules requested for TCP {tcp} and UDP {udp}.")
        QMessageBox.information(self, "Firewall", "Firewall rules created or already existed.")

    def copy_ips(self):
        ips = get_local_ipv4_addresses()
        text = "Local IPs:\n" + "\n".join(f"  {ip}" for ip in ips)
        text += f"\n\nTCP: {self.tcp_port_spin.value()}\nUDP: {self.udp_port_spin.value()}"
        QApplication.clipboard().setText(text)
        self.network_text.setPlainText(text)
        self._log("IP info copied to clipboard.")

    def create_start_bat(self):
        if not self._validate_server_folder():
            return
        paths = self._get_paths()
        bat = paths.server / "start_acc_server_safe.bat"
        bat.write_text('@echo off\ncd /d "%~dp0"\naccServer.exe\npause\n', encoding="utf-8")
        self._log(f"Created {bat}")
        QMessageBox.information(self, "start.bat", f"Created:\n{bat}")

    def copy_share_info(self):
        group = TRACK_TO_GROUP.get(self.track_combo.currentText(), "Unknown")
        text = (
            f"Server: {self.server_name_edit.text()}\n"
            f"Password: {self.server_password_edit.text()}\n"
            f"Track: {self.track_combo.currentText()}\n"
            f"Track pack: {group}\n"
            f"Car group: {self.car_group_combo.currentText()}\n"
            f"TCP: {self.tcp_port_spin.value()}\n"
            f"UDP: {self.udp_port_spin.value()}\n"
            "Search in the normal ACC online server list. Use LAN only if on the same network/VPN."
        )
        QApplication.clipboard().setText(text)
        self._log("Share info copied to clipboard.")
        QMessageBox.information(self, "Share info", "Copied to clipboard.")

    # ─────────────────────────── CLOSE ──────────────────────────────────────

    def closeEvent(self, event):
        self._save_app_config()
        if self.process and self.process.poll() is None:
            reply = QMessageBox.question(self, "Server is running",
                "Stop the server before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_server()
        event.accept()


def _make_dark_palette():
    from PyQt6.QtGui import QPalette
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor("#101215"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#edf2f7"))
    p.setColor(QPalette.ColorRole.Base,            QColor("#0f1318"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#141820"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#edf2f7"))
    p.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Button,          QColor("#1d222a"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#edf2f7"))
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#3658d4"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Link,            QColor("#5b7cff"))
    p.setColor(QPalette.ColorRole.Dark,            QColor("#2d3440"))
    p.setColor(QPalette.ColorRole.Mid,             QColor("#252c36"))
    p.setColor(QPalette.ColorRole.Midlight,        QColor("#1d222a"))
    p.setColor(QPalette.ColorRole.Light,           QColor("#252c36"))
    p.setColor(QPalette.ColorRole.Shadow,          QColor("#000000"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor("#4a5568"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#4a5568"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#4a5568"))
    return p


if __name__ == "__main__":
    app = QApplication(sys.argv)
    acc_style = AccStyle()
    app.setStyle(acc_style)
    app.setPalette(_make_dark_palette())
    window = ACCServerLauncher()
    window.show()
    sys.exit(app.exec())
