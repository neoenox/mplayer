"""最小限のWindows用動画プレイヤー (Python 3.11 + PySide6/QtMultimedia).

バックエンド: PySide6に同梱の FFmpeg プラグイン (ffmpegmediaplugin.dll +
avcodec/avformat/avutil/swresample/swscale) が標準で使われる。
外部の VLC / FFmpeg 手動インストールは不要。

機能:
1. ファイル選択で開く / 2. ドラッグ&ドロップ / 3. 再生・一時停止・停止
4. シークバー+再生位置表示 / 5. 音量+ミュート / 6. ウィンドウ追従表示
7. 全画面切替 / 8. 終了・エラー時の安全な処理
"""
from __future__ import annotations

import bisect
import json
import os
import re
import sys

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QTextLayout,
    QTextOption,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

SUPPORTED_FILTER = (
    "動画ファイル (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.mpg *.mpeg *.wmv);;すべてのファイル (*.*)"
)

# ドロップ/フォルダ走査で扱う拡張子 (小文字で比較)。
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv"}
SUBTITLE_EXTS = {".srt"}
# フォルダをドロップした時に収集する最大件数 (巨大フォルダ対策)。
DROP_MAX_FILES = 500


def is_video_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def collect_video_files(path: str, recursive: bool = True,
                        limit: int = DROP_MAX_FILES) -> list[str]:
    """ファイル/フォルダから動画ファイルを集める。

    フォルダは既定で再帰的に走査し、名前順 (フォルダも名前順) で返す。
    隠しフォルダ (先頭 '.') は除外し、limit 件で打ち切る。
    """
    if os.path.isfile(path):
        return [path] if is_video_file(path) else []
    if not os.path.isdir(path):
        return []
    out: list[str] = []
    if recursive:
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(files):
                if is_video_file(name):
                    out.append(os.path.join(root, name))
                    if len(out) >= limit:
                        return out
    else:
        for name in sorted(os.listdir(path)):
            p = os.path.join(path, name)
            if os.path.isfile(p) and is_video_file(p):
                out.append(p)
                if len(out) >= limit:
                    return out
    return out

APP_NAME = "シンプル動画プレイヤー"
__version__ = "1.11.0"


def _resource_path(rel: str) -> str:
    """同梱リソースのパスを解決する (PyInstaller の _MEIPASS にも対応)。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


ICON_PATH = _resource_path(os.path.join("assets", "app.ico"))

# 前回再生位置の保存先 (アプリと同じフォルダ)。上限100件。
RESUME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume.json")
# セッション (音量/ミュート/速度/プレイリスト) の保存先。
# テスト時は MPLAYER_SESSION_FILE で隔離できる。
SESSION_FILE = os.environ.get(
    "MPLAYER_SESSION_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json"),
)
RESUME_MAX_ENTRIES = 100
RESUME_MIN_MS = 5000       # これより手前は記憶しない (先頭とみなす)
RESUME_TAIL_MS = 10000     # 終端付近は記憶しない (視聴済みとみなす)


def format_ms(ms: int) -> str:
    if ms <= 0:
        return "00:00"
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _parse_srt_timestamp(text: str) -> int:
    """'00:00:01,500' / '00:01:02.250' / '01:02' をミリ秒に変換する。"""
    t = text.strip().replace(",", ".")
    parts = t.split(":")
    if len(parts) == 3:
        h, m, sec = parts
    elif len(parts) == 2:
        h, (m, sec) = 0, parts
    else:
        raise ValueError(f"bad timestamp: {text!r}")
    return int(h) * 3600000 + int(m) * 60000 + int(round(float(sec) * 1000))


def parse_srt(text: str) -> list[tuple[int, int, str]]:
    """SRT文字列を (開始ms, 終了ms, 本文) のリストに変換する。

    不正なブロックは黙って読み飛ばす (破損ファイルでもクラッシュしない)。
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    cues: list[tuple[int, int, str]] = []
    for block in re.split(r"\n[ \t]*\n", normalized):
        lines = block.split("\n")
        ts_idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if ts_idx is None:
            continue
        left, _, right = lines[ts_idx].partition("-->")
        try:
            start = _parse_srt_timestamp(left)
            # 末尾に座標等が付く形式 ("... --> 00:00:02,000 X1:..") を許容
            end = _parse_srt_timestamp(right.strip().split()[0])
        except Exception:
            continue
        body = "\n".join(ln for ln in lines[ts_idx + 1:]).strip()
        if body:
            cues.append((start, end, body))
    cues.sort(key=lambda c: c[0])
    return cues


# 字幕の文字コード選択肢。auto は BOM/UTF-8/CP932 を順に試す。
SUB_ENCODINGS = ("auto", "utf-8", "cp932")
_ENCODING_LABELS = {"auto": "自動", "utf-8": "UTF-8", "cp932": "Shift_JIS"}


def decode_subtitle_bytes(data: bytes, encoding: str = "auto") -> tuple[str, str]:
    """字幕のバイト列をテキストへ復号する。(本文, 採用した文字コード) を返す。

    日本語 SRT は UTF-8 と Shift_JIS(CP932) が混在するため、
    encoding="auto" では BOM → UTF-8(厳密) → CP932 の順に判定する。
    明示指定が失敗した場合も自動判定へフォールバックする (化けより安全)。
    """
    if encoding in ("utf-8", "cp932"):
        try:
            return data.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            pass

    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace"), "utf-8"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace"), "utf-16"

    for enc in ("utf-8", "cp932"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


# 字幕の配色とフォント。縁取り色は塗り色の輝度から自動で決める (黒地に黒を防ぐ)。
SUB_COLORS = (
    ("白", (255, 255, 255)),
    ("黒", (0, 0, 0)),
    ("黄", (255, 235, 59)),
    ("水色", (79, 195, 247)),
    ("緑", (124, 252, 0)),
    ("ピンク", (255, 128, 171)),
)
SUB_FONTS = (
    ("既定", ""),
    ("游ゴシック UI", "Yu Gothic UI"),
    ("メイリオ", "Meiryo"),
    ("MS ゴシック", "MS Gothic"),
    ("Segoe UI", "Segoe UI"),
)


def contrast_outline(rgb) -> tuple[int, int, int]:
    """塗り色の輝度から縁取り色 (黒 or 白) を選ぶ。"""
    r, g, b = (int(v) for v in rgb)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if lum >= 128 else (255, 255, 255)


class SubtitleLabel(QLabel):
    """縁取り(アウトライン)付きの字幕ラベル。

    Qt の QLabel は文字の縁取りができないため、QTextLayout で折返しを計算し、
    QPainterPath で縁取り(太い線)と塗りを重ねて描画する。塗り色は設定でき、
    縁取り色は塗り色の輝度から自動で黒/白を選ぶ。背景の半透明帯も自前で描く。
    """

    INSET_X = 10.0
    INSET_Y = 2.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._outline = True
        self._outline_width = 3.0
        self._outline_color = QColor(0, 0, 0)
        self._fill_color = QColor(255, 255, 255)
        self._font_family = ""
        # 背景 (半透明の黒帯)。縁取りラベル側で描画する (QSS は使わない)。
        self._bg_color = QColor(0, 0, 0, 150)

    def set_outline(self, enabled: bool, width: float | None = None) -> None:
        self._outline = bool(enabled)
        if width is not None:
            self._outline_width = max(0.0, float(width))
        self.update()

    def outline(self) -> bool:
        return self._outline

    def set_fill_color(self, rgb) -> None:
        """文字色を設定し、縁取り色を輝度から自動選択する。"""
        r, g, b = (int(v) for v in rgb)
        self._fill_color = QColor(r, g, b)
        self._outline_color = QColor(*contrast_outline((r, g, b)))
        self.update()

    def fill_color(self) -> QColor:
        return QColor(self._fill_color)

    def outline_color(self) -> QColor:
        return QColor(self._outline_color)

    def set_font_family(self, family: str) -> None:
        """字幕フォントのファミリ名を設定する ("" はシステム既定)。"""
        self._font_family = str(family or "")
        self.update()

    def font_family(self) -> str:
        return self._font_family

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.fillRect(self.rect(), self._bg_color)

        text = self.text()
        if not text:
            p.end()
            return

        font = self.font()
        avail = max(1.0, self.width() - 2 * self.INSET_X)
        layout = QTextLayout(text, font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        option.setAlignment(self.alignment())
        layout.setTextOption(option)
        layout.beginLayout()
        lines = []
        height = 0.0
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(avail)
            line.setPosition(QPointF(0.0, height))
            height += line.height()
            lines.append(line)
        layout.endLayout()

        top = max(self.INSET_Y,
                  (self.height() - height) / 2.0 + self.INSET_Y / 2.0)
        for line in lines:
            snippet = text[line.textStart(): line.textStart() + line.textLength()]
            if not snippet.strip():
                continue
            path = QPainterPath()
            path.addText(
                QPointF(self.INSET_X + line.x(),
                        top + line.y() + line.ascent()), font, snippet)
            if self._outline and self._outline_width > 0:
                pen = QPen(self._outline_color)
                pen.setWidthF(self._outline_width * 2.0)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._fill_color)
            p.drawPath(path)
        p.end()


# キーボードショートカット (ヘルプ表示とテストで共用)。
SHORTCUTS = [
    ("Ctrl+O", "ファイルを開く"),
    ("Space", "再生 / 一時停止"),
    ("← / →", "5秒戻る / 5秒進む"),
    ("Ctrl+← / Ctrl+→", "前の動画 / 次の動画"),
    ("↑ / ↓", "音量 +10 / -10"),
    ("M", "ミュート切替"),
    ("S", "字幕 ON / OFF"),
    ("] / [", "再生速度 上げる / 下げる"),
    ("F / F11", "全画面切替"),
    ("Esc", "全画面を解除"),
    ("F1", "このヘルプを表示"),
]

MOUSE_HELP = [
    ("ダブルクリック", "全画面切替"),
    ("ドラッグ&ドロップ", "ファイル / フォルダを開く・プレイリストに追加"),
]

HELP_NOTES = [
    "フォルダをドロップすると、中の動画を名前順にまとめてプレイリストへ追加します (500件まで)。",
    "全画面では操作系が自動で隠れます。マウスを動かすと再表示されます (Esc で解除)。",
    "字幕の文字コードは自動判定します (「字幕」→「文字コード」で手動指定も可能)。",
    "「字幕」メニューからサイズ・位置・縁取り・文字色・フォントを変更できます。",
    "終了時に音量・速度・プレイリスト・字幕設定を保存し、次回起動時に復元します。",
    "動画と同じフォルダに同名の .srt があれば、自動で読み込みます。",
]


def build_help_html() -> str:
    """ヘルプダイアログの HTML を生成する。"""
    rows = "".join(
        f'<tr><td style="padding:2px 12px 2px 0;"><b>{k}</b></td>'
        f'<td style="padding:2px 0;">{v}</td></tr>'
        for k, v in SHORTCUTS)
    mouse = "".join(
        f'<tr><td style="padding:2px 12px 2px 0;"><b>{k}</b></td>'
        f'<td style="padding:2px 0;">{v}</td></tr>'
        for k, v in MOUSE_HELP)
    notes = "".join(f"<li>{n}</li>" for n in HELP_NOTES)
    return (
        f"<h3>{APP_NAME} v{__version__}</h3>"
        "<h4>キーボードショートカット</h4>"
        f"<table cellspacing='0'>{rows}</table>"
        "<h4>マウス操作</h4>"
        f"<table cellspacing='0'>{mouse}</table>"
        "<h4>ヒント</h4>"
        f"<ul>{notes}</ul>"
    )


class HelpDialog(QDialog):
    """ショートカット一覧と使い方のヒントを表示する非モーダルダイアログ。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ヘルプ / ショートカット")
        self.setModal(False)
        self.resize(560, 460)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser(self)
        self.browser.setObjectName("help_browser")
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(build_help_html())
        layout.addWidget(self.browser)
        close_btn = QPushButton("閉じる", self)
        close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_btn.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_btn)
        layout.addLayout(row)


class PlayerWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(960, 600)
        self.setAcceptDrops(True)

        # --- 再生エンジン ---
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget(self)
        # アスペクト比を保ったままウィンドウに追従
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.player.setVideoOutput(self.video)

        # 字幕オーバーレイ: 映像の上に重ねる。マウスは透過させ、
        # ダブルクリックでの全画面切替を妨げない。
        self.subtitle_label = SubtitleLabel(self.video)
        self.subtitle_label.setObjectName("subtitle_label")
        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.subtitle_label.setText("")
        self.subtitle_label.hide()
        # 字幕の表示設定 (サイズpx / 位置: top|middle|bottom / 縁取り / 文字コード)
        self._sub_size = 18
        self._sub_pos = "bottom"
        self._sub_outline = True
        self._sub_encoding = "auto"
        self._sub_color = (255, 255, 255)
        self._sub_font = ""
        # 映像の下端に配置 (addStretch で下寄せ)。背景は字幕行の高さのみ。
        self._overlay = QVBoxLayout(self.video)
        self._rebuild_overlay()

        # --- UI ---
        # NOTE: 操作系ウィジェットはフォーカスを受け取らない (NoFocus)。
        # Space/矢印キーがフォーカス先ウィジェットと二重に反応するのを防ぐ。
        # キーボード操作は下の QAction ショートカットに一本化する。
        self.open_btn = QPushButton("開く")
        self.open_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_btn.clicked.connect(self.open_file_dialog)

        self.play_btn = QPushButton()
        self.play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.setText("再生")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.toggle_play)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(140)

        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        # NOTE: sliderMoved ではなく sliderReleased でシークする。
        # ドラッグ中1pxごとに setPosition を呼ぶと FFmpeg バックエンドの
        # シーク要求が殺到し、イベントループがデッドロックする場合がある。
        # さらに setPosition はマウスイベント処理の外 (deferred) で呼ぶ。
        # リリースイベントの直下で呼ぶと Qt 6.12 の FFmpeg バックエンドで
        # 再入デッドロックを起こすことがある (検証で確認)。
        self.seek.sliderReleased.connect(self.seek_released)
        self.seek.actionTriggered.connect(self.seek_action)
        self.seek.setSingleStep(1000)
        self.seek.setPageStep(10000)
        self.seek.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # 誤操作防止: ファイル未ロード時は無効
        self.seek.setEnabled(False)

        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        self.vol.setMaximumWidth(120)
        self.vol.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.vol.valueChanged.connect(self.change_volume)

        self.mute_btn = QPushButton("ミュート")
        self.mute_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_mute)

        self.speed_btn = QPushButton("速度 1.0x")
        self.speed_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_btn.clicked.connect(self.cycle_speed)

        self.subs_btn = QPushButton("字幕")
        self.subs_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.subs_btn.setCheckable(True)
        self.subs_btn.setEnabled(False)
        self.subs_btn.clicked.connect(self.toggle_subtitles)

        self.pl_btn = QPushButton("リスト")
        self.pl_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pl_btn.setCheckable(True)
        self.pl_btn.toggled.connect(self._toggle_playlist_dock)

        self.fs_btn = QPushButton("全画面")
        self.fs_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fs_btn.clicked.connect(self.toggle_fullscreen)

        top_row = QHBoxLayout()
        top_row.addWidget(self.open_btn)
        top_row.addWidget(self.play_btn)
        top_row.addWidget(self.stop_btn)
        top_row.addWidget(self.seek, 1)
        top_row.addWidget(self.time_label)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("音量"))
        bottom_row.addWidget(self.vol)
        bottom_row.addWidget(self.mute_btn)
        bottom_row.addWidget(self.speed_btn)
        bottom_row.addWidget(self.subs_btn)
        bottom_row.addWidget(self.pl_btn)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.fs_btn)

        # 操作系は1つのウィジェットにまとめる (全画面時に一括で隠すため)。
        self.controls = QWidget(self)
        ctl_lay = QVBoxLayout(self.controls)
        ctl_lay.setContentsMargins(0, 0, 0, 0)
        ctl_lay.setSpacing(4)
        ctl_lay.addLayout(top_row)
        ctl_lay.addLayout(bottom_row)

        layout = QVBoxLayout()
        layout.addWidget(self.video, 1)
        layout.addWidget(self.controls)

        central = QWidget(self)
        central.setLayout(layout)
        self.setCentralWidget(central)
        self._central = central
        # 全画面時のフェード用に、映像領域・中央ウィジェットのマウス移動も拾う。
        self.video.setMouseTracking(True)
        central.setMouseTracking(True)
        self.video.installEventFilter(self)
        central.installEventFilter(self)

        # --- プレイリスト (連続再生) ---
        self.playlist = QListWidget()
        self.playlist.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.playlist.itemDoubleClicked.connect(self._on_playlist_activated)

        self.pl_dock = QDockWidget("プレイリスト", self)
        self.pl_dock.setObjectName("playlist_dock")
        pl_panel = QWidget()
        pl_lay = QVBoxLayout(pl_panel)
        pl_lay.setContentsMargins(4, 4, 4, 4)
        pl_lay.setSpacing(4)
        pl_top = QHBoxLayout()
        self.pl_add_btn = QPushButton("追加")
        self.pl_del_btn = QPushButton("削除")
        self.pl_clear_btn = QPushButton("クリア")
        for b in (self.pl_add_btn, self.pl_del_btn, self.pl_clear_btn):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            pl_top.addWidget(b)
        pl_bot = QHBoxLayout()
        self.prev_btn = QPushButton("前へ")
        self.next_btn = QPushButton("次へ")
        for b in (self.prev_btn, self.next_btn):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            pl_bot.addWidget(b)
        self.pl_add_btn.clicked.connect(self.add_files_dialog)
        self.pl_del_btn.clicked.connect(self.remove_selected)
        self.pl_clear_btn.clicked.connect(self.clear_playlist)
        self.prev_btn.clicked.connect(self.play_prev)
        self.next_btn.clicked.connect(self.play_next)
        pl_lay.addLayout(pl_top)
        pl_lay.addWidget(self.playlist, 1)
        pl_lay.addLayout(pl_bot)
        self.pl_dock.setWidget(pl_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.pl_dock)
        self.pl_dock.hide()
        self.pl_dock.visibilityChanged.connect(self.pl_btn.setChecked)

        # --- シグナル ---
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.playbackStateChanged.connect(self.on_state_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.errorChanged.connect(self.on_error)
        self.audio.setVolume(0.8)

        # --- メニュー / ショートカット ---
        file_menu = self.menuBar().addMenu("ファイル")
        open_act = QAction("開く...", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_act)

        sub_open_act = QAction("字幕を開く...", self)
        sub_open_act.triggered.connect(self.open_subtitle_dialog)
        file_menu.addAction(sub_open_act)

        pl_add_act = QAction("プレイリストに追加...", self)
        pl_add_act.triggered.connect(self.add_files_dialog)
        file_menu.addAction(pl_add_act)

        self.fs_act = QAction("全画面切替", self)
        self.fs_act.setShortcut(Qt.Key.Key_F11)
        self.fs_act.triggered.connect(self.toggle_fullscreen)
        self.addAction(self.fs_act)

        esc_act = QAction(self)
        esc_act.setShortcut(Qt.Key.Key_Escape)
        esc_act.triggered.connect(self.exit_fullscreen)
        self.addAction(esc_act)

        # Space: 再生/一時停止。ボタン類はNoFocusのため二重発火しない。
        space_act = QAction(self)
        space_act.setShortcut(Qt.Key.Key_Space)
        space_act.triggered.connect(self.toggle_play)
        self.addAction(space_act)

        left_act = QAction(self)
        left_act.setShortcut(Qt.Key.Key_Left)
        left_act.triggered.connect(lambda: self.seek_by(-5000))
        self.addAction(left_act)

        right_act = QAction(self)
        right_act.setShortcut(Qt.Key.Key_Right)
        right_act.triggered.connect(lambda: self.seek_by(5000))
        self.addAction(right_act)

        f_act = QAction(self)
        f_act.setShortcut(Qt.Key.Key_F)
        f_act.triggered.connect(self.toggle_fullscreen)
        self.addAction(f_act)

        m_act = QAction(self)
        m_act.setShortcut(Qt.Key.Key_M)
        m_act.triggered.connect(lambda: self.mute_btn.click())
        self.addAction(m_act)

        up_act = QAction(self)
        up_act.setShortcut(Qt.Key.Key_Up)
        up_act.triggered.connect(lambda: self.vol.setValue(min(100, self.vol.value() + 10)))
        self.addAction(up_act)

        down_act = QAction(self)
        down_act.setShortcut(Qt.Key.Key_Down)
        down_act.triggered.connect(lambda: self.vol.setValue(max(0, self.vol.value() - 10)))
        self.addAction(down_act)

        s_act = QAction(self)
        s_act.setShortcut(Qt.Key.Key_S)
        s_act.triggered.connect(lambda: self.subs_btn.click())
        self.addAction(s_act)

        next_act = QAction(self)
        next_act.setShortcut(QKeySequence("Ctrl+Right"))
        next_act.triggered.connect(self.play_next)
        self.addAction(next_act)

        prev_act = QAction(self)
        prev_act.setShortcut(QKeySequence("Ctrl+Left"))
        prev_act.triggered.connect(self.play_prev)
        self.addAction(prev_act)

        # 再生速度: ] で上げる / [ で下げる (端では据え置き)。
        self.speed_up_act = QAction(self)
        self.speed_up_act.setShortcut(QKeySequence(Qt.Key.Key_BracketRight))
        self.speed_up_act.triggered.connect(self.speed_up)
        self.addAction(self.speed_up_act)

        self.speed_down_act = QAction(self)
        self.speed_down_act.setShortcut(QKeySequence(Qt.Key.Key_BracketLeft))
        self.speed_down_act.triggered.connect(self.speed_down)
        self.addAction(self.speed_down_act)

        sub_menu = self.menuBar().addMenu("字幕")
        size_menu = sub_menu.addMenu("サイズ")
        self._sub_size_group = QActionGroup(self)
        for label, px in (("小 (14)", 14), ("中 (18)", 18), ("大 (26)", 26)):
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked(px == self._sub_size)
            a.triggered.connect(lambda _=False, v=px: self.set_subtitle_size(v))
            self._sub_size_group.addAction(a)
            size_menu.addAction(a)
        pos_menu = sub_menu.addMenu("位置")
        self._sub_pos_group = QActionGroup(self)
        for label, pos in (("下", "bottom"), ("中央", "middle"), ("上", "top")):
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked(pos == self._sub_pos)
            a.triggered.connect(lambda _=False, v=pos: self.set_subtitle_pos(v))
            self._sub_pos_group.addAction(a)
            pos_menu.addAction(a)

        self._sub_outline_act = QAction("縁取り", self)
        self._sub_outline_act.setCheckable(True)
        self._sub_outline_act.setChecked(self._sub_outline)
        self._sub_outline_act.triggered.connect(self.set_subtitle_outline)
        sub_menu.addAction(self._sub_outline_act)

        enc_menu = sub_menu.addMenu("文字コード")
        self._sub_enc_group = QActionGroup(self)
        for enc in SUB_ENCODINGS:
            a = QAction(_ENCODING_LABELS[enc], self)
            a.setCheckable(True)
            a.setChecked(enc == self._sub_encoding)
            a.triggered.connect(lambda _=False, v=enc: self.set_subtitle_encoding(v))
            self._sub_enc_group.addAction(a)
            enc_menu.addAction(a)

        color_menu = sub_menu.addMenu("文字色")
        self._sub_color_group = QActionGroup(self)
        for label, rgb in SUB_COLORS:
            a = QAction(label, self)
            a.setCheckable(True)
            a.setData(list(rgb))
            a.setChecked(tuple(rgb) == self._sub_color)
            a.triggered.connect(lambda _=False, v=rgb: self.set_subtitle_color(v))
            self._sub_color_group.addAction(a)
            color_menu.addAction(a)

        font_menu = sub_menu.addMenu("フォント")
        self._sub_font_group = QActionGroup(self)
        for label, family in SUB_FONTS:
            a = QAction(label, self)
            a.setCheckable(True)
            a.setData(family)
            a.setChecked(family == self._sub_font)
            a.triggered.connect(lambda _=False, v=family: self.set_subtitle_font(v))
            self._sub_font_group.addAction(a)
            font_menu.addAction(a)

        help_menu = self.menuBar().addMenu("ヘルプ")
        self.help_act = QAction("ショートカット一覧", self)
        self.help_act.setShortcut(Qt.Key.Key_F1)
        self.help_act.triggered.connect(self.show_shortcuts)
        help_menu.addAction(self.help_act)
        help_menu.addSeparator()
        about_act = QAction("バージョン情報", self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)
        self._help_dialog: HelpDialog | None = None
        self._is_fullscreen = False
        # 全画面で操作が無いとき操作系を隠すまでの待ち時間 (ms)。テストで短縮可能。
        self._fs_hide_ms = 2500
        self._fs_timer = QTimer(self)
        self._fs_timer.setSingleShot(True)
        self._fs_timer.timeout.connect(self._hide_fs_controls)
        self._suppress_error_box = False
        # 遅延シークの世代管理。load()ごとに加算し、古いファイル向けの
        # 予約シークが新ファイルへ誤適用されるのを防ぐ (P5)。
        self._media_gen = 0
        # 予約中のシーク先 (連続キー入力時に最新予約を基準にするため)。
        self._pending_seek = None
        # 再生速度 (QMediaPlayer.setPlaybackRate)。既定1.0。
        self._rates = [0.5, 1.0, 1.5, 2.0]
        self._rate_idx = 1
        # 前回再生位置。{abspath: {"pos": ms}}。読み込み失敗時は空扱い。
        self._resume = self._load_resume()
        self._current_path: str | None = None
        self._restore_pos: int | None = None
        # 字幕 (SRT)。cues は (開始ms, 終了ms, 本文) の昇順リスト。
        self._cues: list[tuple[int, int, str]] = []
        self._cue_starts: list[int] = []
        self._subs_enabled = False
        # 現在読み込んでいる字幕ファイル (文字コード切替時の再読込に使う)
        self._current_sub_path: str | None = None
        self._sub_used_encoding = ""
        # 全画面時にプレイリストの表示状態を退避
        self._dock_visible_before_fs = False

    # ---------- ファイル ----------
    @Slot()
    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "動画を開く", "", SUPPORTED_FILTER)
        if path:
            self.load(path)

    def load(self, path: str) -> bool:
        """動画を読み込む。失敗してもクラッシュせず False を返す。"""
        if not os.path.isfile(path):
            QMessageBox.warning(self, "エラー", f"ファイルが見つかりません:\n{path}")
            return False
        self._remember_current()
        self._suppress_error_box = False
        self._media_gen += 1
        self._pending_seek = None
        self._current_path = os.path.abspath(path)
        self._restore_pos = self._resume_pos_for(self._current_path)
        # 字幕をリセットし、同名 .srt があれば自動で読み込む
        self.clear_subtitles()
        self.player.setSource(QUrl.fromLocalFile(path))
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.seek.setEnabled(True)
        self.subs_btn.setEnabled(True)
        auto_sub = self._sibling_subtitle(self._current_path)
        if auto_sub:
            self.load_subtitles(auto_sub)
        self.setWindowTitle(f"{APP_NAME} v{__version__} - {os.path.basename(path)}")
        self.player.play()
        return True

    # ---------- 前回再生位置 ----------
    @staticmethod
    def _load_resume() -> dict:
        try:
            with open(RESUME_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_resume(self) -> None:
        try:
            while len(self._resume) > RESUME_MAX_ENTRIES:
                self._resume.pop(next(iter(self._resume)))
            with open(RESUME_FILE, "w", encoding="utf-8") as f:
                json.dump(self._resume, f, ensure_ascii=False)
        except Exception:
            pass

    def _resume_pos_for(self, path: str | None) -> int | None:
        if not path:
            return None
        try:
            pos = self._resume.get(path, {}).get("pos")
            return pos if isinstance(pos, int) and pos > 0 else None
        except Exception:
            return None

    def _remember_current(self) -> None:
        """現在の再生位置を保存 (先頭・終端付近は対象外)。"""
        try:
            path = self._current_path
            if not path:
                return
            pos, dur = self.player.position(), self.player.duration()
            if dur > 0 and RESUME_MIN_MS < pos < dur - RESUME_TAIL_MS:
                self._resume.pop(path, None)
                self._resume[path] = {"pos": pos}
                self._save_resume()
        except Exception:
            pass

    def _forget_current(self) -> None:
        """明示的な停止・視聴完了は記憶を消す (次回は先頭から)。"""
        try:
            if self._current_path and self._current_path in self._resume:
                del self._resume[self._current_path]
                self._save_resume()
        except Exception:
            pass

    # ---------- セッション (音量/ミュート/速度/プレイリスト) ----------
    @staticmethod
    def _load_session() -> dict:
        try:
            with open(SESSION_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_session(self) -> None:
        data = {
            "volume": self.vol.value(),
            "muted": self.mute_btn.isChecked(),
            "rate": self._rates[self._rate_idx],
            "subtitle_size": self._sub_size,
            "subtitle_pos": self._sub_pos,
            "subtitle_outline": self._sub_outline,
            "subtitle_encoding": self._sub_encoding,
            "subtitle_color": list(self._sub_color),
            "subtitle_font": self._sub_font,
            "playlist": [self.playlist.item(i).data(Qt.ItemDataRole.UserRole)
                         for i in range(self.playlist.count())],
        }
        try:
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _apply_session(self, s: dict) -> None:
        if not isinstance(s, dict):
            return
        vol = s.get("volume")
        if isinstance(vol, int) and 0 <= vol <= 100:
            self.vol.setValue(vol)  # change_volume 経由で audio にも反映
        muted = s.get("muted")
        if isinstance(muted, bool):
            self.mute_btn.setChecked(muted)
            self.audio.setMuted(muted)
        rate = s.get("rate")
        if rate in self._rates:
            self._rate_idx = self._rates.index(rate)
            try:
                self.player.setPlaybackRate(rate)
            except Exception:
                pass
            self.speed_btn.setText(f"速度 {rate}x")
        self.set_subtitle_size(s.get("subtitle_size"))
        self.set_subtitle_pos(s.get("subtitle_pos"))
        outline = s.get("subtitle_outline")
        if isinstance(outline, bool):
            self.set_subtitle_outline(outline)
        enc = s.get("subtitle_encoding")
        if enc in SUB_ENCODINGS:
            self._sub_encoding = enc
            act = getattr(self, "_sub_enc_group", None)
            if act is not None:
                for a in act.actions():
                    if a.text() == _ENCODING_LABELS[enc]:
                        a.setChecked(True)
                        break
        pl = s.get("playlist")
        if isinstance(pl, list):
            paths = [p for p in pl if isinstance(p, str)]
            if paths:
                self.add_to_playlist(paths)
        self.set_subtitle_color(s.get("subtitle_color"))
        self.set_subtitle_font(s.get("subtitle_font"))

    def restore_session(self) -> None:
        self._apply_session(self._load_session())

    # ---------- 字幕 ----------
    @staticmethod
    def _sibling_subtitle(video_path: str | None) -> str | None:
        """動画と同じフォルダの同名 .srt を探す。"""
        if not video_path:
            return None
        stem = os.path.splitext(video_path)[0]
        for cand in (stem + ".srt", stem + ".SRT", stem + ".Srt"):
            if os.path.isfile(cand):
                return cand
        return None

    # ---------- 字幕の表示設定 ----------
    def _rebuild_overlay(self) -> None:
        """位置設定に応じて字幕ラベルを再配置する。"""
        while self._overlay.count():
            self._overlay.takeAt(0)
        pos = self._sub_pos
        if pos == "top":
            self._overlay.setContentsMargins(0, 14, 0, 0)
            self._overlay.addWidget(self.subtitle_label)
            self._overlay.addStretch(1)
        elif pos == "middle":
            self._overlay.setContentsMargins(0, 0, 0, 0)
            self._overlay.addStretch(1)
            self._overlay.addWidget(self.subtitle_label)
            self._overlay.addStretch(1)
        else:
            self._overlay.setContentsMargins(0, 0, 0, 14)
            self._overlay.addStretch(1)
            self._overlay.addWidget(self.subtitle_label)
        self.subtitle_label.setStyleSheet(
            "#subtitle_label { color: white;"
            f" padding: 2px 10px; font-size: {self._sub_size}px;"
            + (f' font-family: "{self._sub_font}";' if self._sub_font else "")
            + " }")
        # 文字色 (縁取り色は輝度から自動決定)。
        self.subtitle_label.set_fill_color(self._sub_color)
        # 縁取り幅は文字サイズに追従させる (大きい文字ほど太く)。
        self.subtitle_label.set_outline(self._sub_outline,
                                        max(1.5, self._sub_size * 0.15))

    def set_subtitle_size(self, px: int) -> None:
        if isinstance(px, int) and 8 <= px <= 72:
            self._sub_size = px
            self._rebuild_overlay()

    def set_subtitle_pos(self, pos: str) -> None:
        if pos in ("top", "middle", "bottom"):
            self._sub_pos = pos
            self._rebuild_overlay()

    def set_subtitle_outline(self, enabled: bool) -> None:
        self._sub_outline = bool(enabled)
        act = getattr(self, "_sub_outline_act", None)
        if act is not None and act.isChecked() != self._sub_outline:
            act.setChecked(self._sub_outline)
        self.subtitle_label.set_outline(
            self._sub_outline, max(1.5, self._sub_size * 0.15))

    def set_subtitle_color(self, rgb) -> None:
        """字幕の文字色。既定 (白) 以外は縁取り色を自動で反転する。"""
        try:
            rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        except (TypeError, IndexError, ValueError):
            return
        if rgb not in [c for _, c in SUB_COLORS]:
            return
        self._sub_color = rgb
        grp = getattr(self, "_sub_color_group", None)
        if grp is not None:
            for a in grp.actions():
                if a.data() == list(rgb):
                    a.setChecked(True)
        self.subtitle_label.set_fill_color(rgb)

    def set_subtitle_font(self, family: str) -> None:
        """字幕フォントのファミリ。"" はシステム既定。"""
        family = str(family or "")
        if family not in [f for _, f in SUB_FONTS]:
            return
        self._sub_font = family
        grp = getattr(self, "_sub_font_group", None)
        if grp is not None:
            for a in grp.actions():
                if a.data() == family:
                    a.setChecked(True)
        self.subtitle_label.set_font_family(family)
        self._rebuild_overlay()

    def set_subtitle_encoding(self, enc: str) -> None:
        """文字コード指定。auto 以外は再読込して反映する。"""
        if enc not in SUB_ENCODINGS:
            return
        self._sub_encoding = enc
        act = getattr(self, "_sub_enc_group", None)
        if act is not None:
            for a in act.actions():
                if a.text() == _ENCODING_LABELS[enc]:
                    a.setChecked(True)
                    break
        if self._current_sub_path:
            self.load_subtitles(self._current_sub_path)

    def load_subtitles(self, path: str, encoding: str | None = None) -> bool:
        """SRT を読み込む。読み込めなければ False (クラッシュしない)。"""
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception:
            return False
        text, used = decode_subtitle_bytes(data, encoding or self._sub_encoding)
        cues = parse_srt(text)
        self._cues = cues
        self._cue_starts = [c[0] for c in cues]
        self._subs_enabled = bool(cues)
        self._current_sub_path = path if cues else None
        self._sub_used_encoding = used if cues else ""
        self.subs_btn.setChecked(bool(cues))
        self.subs_btn.setText("字幕 ON" if cues else "字幕")
        self.update_subtitle(self.player.position())
        return bool(cues)

    def clear_subtitles(self) -> None:
        self._cues = []
        self._cue_starts = []
        self._subs_enabled = False
        self._current_sub_path = None
        self._sub_used_encoding = ""
        self.subtitle_label.setText("")
        self.subtitle_label.hide()
        self.subs_btn.setChecked(False)
        self.subs_btn.setText("字幕")

    @Slot()
    def toggle_subtitles(self) -> None:
        # チェック状態はクリックで既に反転している。ONにしたい時に字幕が
        # 無ければ、同名 .srt の自動読み込みを試みる。
        want_on = self.subs_btn.isChecked()
        if want_on and not self._cues:
            auto = self._sibling_subtitle(self._current_path)
            if not (auto and self.load_subtitles(auto)):
                self.subs_btn.setChecked(False)
                self.subs_btn.setText("字幕")
                self.subtitle_label.hide()
                return
        self._subs_enabled = want_on
        self.subs_btn.setText("字幕 ON" if want_on else "字幕")
        self.update_subtitle(self.player.position())

    @Slot()
    def open_subtitle_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "字幕ファイルを選択", "",
            "字幕ファイル (*.srt);;すべてのファイル (*.*)")
        if path:
            self.load_subtitles(path)

    def _cue_text_at(self, pos: int) -> str:
        if not self._cues:
            return ""
        i = bisect.bisect_right(self._cue_starts, pos) - 1
        if i >= 0:
            start, end, body = self._cues[i]
            if start <= pos < end:
                return body
        return ""

    def update_subtitle(self, pos: int) -> None:
        text = self._cue_text_at(pos) if self._subs_enabled else ""
        if self.subtitle_label.text() != text:
            self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    # ---------- プレイリスト (連続再生) ----------
    def _toggle_playlist_dock(self, checked: bool) -> None:
        self.pl_dock.setVisible(bool(checked))

    def add_files_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "プレイリストに追加", "", SUPPORTED_FILTER)
        if paths:
            self.add_to_playlist(paths)

    def add_to_playlist(self, paths) -> int:
        existing = {self.playlist.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(self.playlist.count())}
        added = 0
        for p in paths:
            if not p or not os.path.isfile(p):
                continue
            ap = os.path.abspath(p)
            if ap in existing:
                continue
            it = QListWidgetItem(os.path.basename(p))
            it.setData(Qt.ItemDataRole.UserRole, ap)
            it.setToolTip(ap)
            self.playlist.addItem(it)
            existing.add(ap)
            added += 1
        if added and not self.pl_dock.isVisible():
            self.pl_dock.show()
        return added

    def remove_selected(self) -> None:
        for it in self.playlist.selectedItems():
            self.playlist.takeItem(self.playlist.row(it))

    def clear_playlist(self) -> None:
        self.playlist.clear()

    def _on_playlist_activated(self, item: QListWidgetItem) -> None:
        self.play_index(self.playlist.row(item))

    def _index_of_current(self) -> int:
        if not self._current_path:
            return -1
        for i in range(self.playlist.count()):
            if self.playlist.item(i).data(Qt.ItemDataRole.UserRole) == self._current_path:
                return i
        return -1

    def play_index(self, i: int) -> bool:
        if 0 <= i < self.playlist.count():
            path = self.playlist.item(i).data(Qt.ItemDataRole.UserRole)
            if path and self.load(path):
                self.playlist.setCurrentRow(i)
                return True
        return False

    def play_next(self) -> bool:
        return self._step_track(+1)

    def play_prev(self) -> bool:
        return self._step_track(-1)

    def _step_track(self, delta: int) -> bool:
        if self.playlist.count() == 0:
            return False
        row = self.playlist.currentRow()
        if row < 0:
            row = self._index_of_current()
        if row < 0:
            return self.play_index(0 if delta > 0 else self.playlist.count() - 1)
        nxt = row + delta
        if 0 <= nxt < self.playlist.count():
            return self.play_index(nxt)
        return False

    def _advance_if_in_playlist(self) -> bool:
        """再生中のファイルがリスト内にある場合のみ「次の曲」へ進む。"""
        idx = self._index_of_current()
        if idx < 0 or idx + 1 >= self.playlist.count():
            return False
        return self.play_index(idx + 1)

    # ---------- 操作 ----------
    @Slot()
    def toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._remember_current()
            self.player.pause()
        else:
            # ソース未設定ならファイル選択を促す
            if self.player.source().isEmpty():
                self.open_file_dialog()
                return
            self.player.play()

    @Slot()
    def stop(self) -> None:
        # 状態遷移はイベント処理の外で実行 (入力ディスパッチ内の再入デッドロック防止)。
        gen = self._media_gen
        QTimer.singleShot(0, lambda: self._apply_stop(gen))

    def _apply_stop(self, gen: int) -> None:
        if gen == self._media_gen:
            self._do_stop()

    def _do_stop(self) -> None:
        # NOTE: QMediaPlayer.stop() は使わない。一時停止→再開の履歴がある状態で
        # stop() を呼ぶと、呼び出し自体は復帰するが直後のイベント処理が
        # デッドロックする (Qt 6.12 FFmpegバックエンドの問題として確認)。
        # pause()+setPosition(0) の組み合わせは同条件で安全に動作する。
        # 見た目の振る舞い (停止+先頭戻し+「再生」表示) は同等。
        self._forget_current()
        try:
            self.player.pause()
        except Exception:
            return
        try:
            self.player.setPosition(0)
        except Exception:
            pass

    @Slot()
    def seek_released(self) -> None:
        # ドラッグ確定時に1回だけシーク (バックエンドへの要求殺到を避ける)。
        # QTimer経由で遅延実行し、マウスイベント処理内での再入を避ける。
        # 世代を添えて、予約実行前にファイルが切り替わっていたら破棄する。
        self._post_seek(self.seek.value())

    @Slot(int)
    def seek_action(self, action: int) -> None:
        # actionTriggered precedes valueChanged; sliderPosition holds the new target.
        # Mouse drags remain handled once on release.
        if self.seek.isSliderDown():
            return
        self._post_seek(self.seek.sliderPosition())

    def _apply_seek(self, gen: int, target: int) -> None:
        if gen != self._media_gen:
            return
        if self._pending_seek == target:
            self._pending_seek = None
        try:
            self.player.setPosition(target)
        except Exception:
            pass

    def _post_seek(self, target: int) -> None:
        gen = self._media_gen
        self._pending_seek = target
        QTimer.singleShot(0, lambda: self._apply_seek(gen, target))

    def seek_by(self, delta_ms: int) -> None:
        """キーボード用相対シーク。範囲外は丸め、安全な遅延経路を使う。
        連続入力時は予約中の値を基準に累積する。"""
        if self.player.duration() <= 0:
            return
        base = self._pending_seek if self._pending_seek is not None else self.player.position()
        target = min(max(base + delta_ms, 0), self.player.duration())
        self.seek.setValue(target)
        self._post_seek(target)

    @Slot()
    def cycle_speed(self) -> None:
        self._rate_idx = (self._rate_idx + 1) % len(self._rates)
        self._apply_rate()

    def speed_up(self) -> None:
        """再生速度を1段階上げる ([ は下げる)。端では据え置き。"""
        self._step_speed(+1)

    def speed_down(self) -> None:
        self._step_speed(-1)

    def _step_speed(self, delta: int) -> None:
        idx = min(max(self._rate_idx + delta, 0), len(self._rates) - 1)
        if idx == self._rate_idx:
            return
        self._rate_idx = idx
        self._apply_rate()

    def _apply_rate(self) -> None:
        rate = self._rates[self._rate_idx]
        try:
            self.player.setPlaybackRate(rate)
        except Exception:
            pass
        self.speed_btn.setText(f"速度 {rate}x")

    @Slot(int)
    def change_volume(self, value: int) -> None:
        self.audio.setVolume(value / 100.0)
        if value > 0 and self.mute_btn.isChecked():
            self.mute_btn.setChecked(False)
            self.audio.setMuted(False)

    @Slot()
    def toggle_mute(self) -> None:
        muted = self.mute_btn.isChecked()
        self.audio.setMuted(muted)

    @Slot()
    def toggle_fullscreen(self) -> None:
        if self._is_fullscreen:
            self.exit_fullscreen()
        else:
            self._is_fullscreen = True
            self._dock_visible_before_fs = self.pl_dock.isVisible()
            self.pl_dock.hide()
            self.menuBar().hide()
            self.showFullScreen()
            self.fs_btn.setText("全画面解除")
            self._show_fs_controls()
            self._fs_timer.start(self._fs_hide_ms)

    @Slot()
    def exit_fullscreen(self) -> None:
        if self._is_fullscreen:
            self._is_fullscreen = False
            self._fs_timer.stop()
            self._show_fs_controls()
            self.showNormal()
            self.menuBar().show()
            if self._dock_visible_before_fs:
                self.pl_dock.show()
            self.fs_btn.setText("全画面")

    # ---------- 全画面: 操作系の自動表示/フェード ----------
    def note_activity(self) -> None:
        """マウス操作などの合図。全画面中は操作系を表示してタイマーを張り直す。"""
        if not self._is_fullscreen:
            return
        self._show_fs_controls()
        self._fs_timer.start(self._fs_hide_ms)

    def _show_fs_controls(self) -> None:
        if not self.controls.isVisible():
            self.controls.setVisible(True)
        if self.cursor().shape() == Qt.CursorShape.BlankCursor:
            self.unsetCursor()

    def _hide_fs_controls(self) -> None:
        """全画面で一定時間操作が無いとき、操作系とカーソルを隠す。"""
        if not self._is_fullscreen:
            return
        self.controls.hide()
        self.setCursor(Qt.CursorShape.BlankCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.note_activity()
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        # 子ウィジェット (映像領域など) 上のマウス移動も活動として扱う。
        if event.type() == QEvent.Type.MouseMove and self._is_fullscreen:
            self.note_activity()
        return super().eventFilter(obj, event)

    @Slot()
    def show_shortcuts(self) -> None:
        """ショートカット一覧ダイアログを表示する (非モーダル・使い回し)。"""
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(self)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    @Slot()
    def show_about(self) -> None:
        QMessageBox.about(
            self, "バージョン情報",
            f"{APP_NAME} v{__version__}\n\n"
            "最小限のローカル動画プレイヤー (Windows / PySide6)。\n"
            "再生: PySide6同梱のFFmpegバックエンド。外部FFmpeg不要。")

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        # 再生を先に止めてから閉じる。stop() ではなく pause() を使う
        # (_do_stop と同じ理由: player.stop() 後のデッドロック防止)。
        # 閉じる前に位置を記憶する (次回起動時に再開できる)。
        self._remember_current()
        self._save_session()
        try:
            self.player.pause()
        except Exception:
            pass
        super().closeEvent(event)

    # ---------- ドラッグ&ドロップ ----------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        paths = [p for p in (u.toLocalFile() for u in urls) if p]
        if not paths:
            super().dropEvent(event)
            return

        # 字幕ファイル単体のドロップは、字幕として読み込む。
        if len(paths) == 1 and os.path.isfile(paths[0]) and \
                os.path.splitext(paths[0])[1].lower() in SUBTITLE_EXTS:
            if self.load_subtitles(paths[0]):
                event.acceptProposedAction()
                return

        videos: list[str] = []
        other_files: list[str] = []
        for p in paths:
            if os.path.isdir(p):
                videos.extend(collect_video_files(p))
            elif is_video_file(p):
                videos.append(p)
            elif os.path.isfile(p):
                other_files.append(p)

        # 重複を除去 (順序は保持)。
        seen: set[str] = set()
        unique: list[str] = []
        for v in videos:
            key = os.path.abspath(v)
            if key not in seen:
                seen.add(key)
                unique.append(v)
        videos = unique

        if not videos:
            # 動画が無い場合は従来動作 (先頭のファイルを開く)。
            if other_files:
                self.load(other_files[0])
                event.acceptProposedAction()
                return
            super().dropEvent(event)
            return

        if len(videos) == 1 and not other_files:
            self.load(videos[0])
            event.acceptProposedAction()
            return

        # 複数 (フォルダ展開含む) はプレイリストに追加し、先頭を再生する。
        self.add_to_playlist(videos)
        row = self._row_of_path(os.path.abspath(videos[0]))
        if row >= 0:
            self.play_index(row)
        event.acceptProposedAction()

    def _row_of_path(self, path: str) -> int:
        for i in range(self.playlist.count()):
            if self.playlist.item(i).data(Qt.ItemDataRole.UserRole) == path:
                return i
        return -1

    # ---------- 再生状態反映 ----------
    @Slot(int)
    def on_position_changed(self, pos: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        self.time_label.setText(f"{format_ms(pos)} / {format_ms(self.player.duration())}")
        self.update_subtitle(pos)

    @Slot(int)
    def on_duration_changed(self, dur: int) -> None:
        self.seek.setRange(0, max(0, dur))
        self.time_label.setText(f"{format_ms(self.player.position())} / {format_ms(dur)}")
        # 前回位置の復元 (1回のみ)。範囲外は無視し、安全な遅延経路を使う。
        if self._restore_pos is not None:
            pos, self._restore_pos = self._restore_pos, None
            if dur > 0 and RESUME_MIN_MS < pos < dur - RESUME_TAIL_MS:
                self._post_seek(pos)

    @Slot(QMediaPlayer.PlaybackState)
    def on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.play_btn.setText("一時停止")
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_btn.setText("再生")

    @Slot(QMediaPlayer.MediaStatus)
    def on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # 終了時は先頭に戻して停止表示にする (自動リピートはしない)。
            # player.stop() は使わない (_do_stop と同じ理由)。
            # 世代付き遅延で処理し、直後に別ファイルへ切り替わっていたら破棄する。
            gen = self._media_gen
            QTimer.singleShot(0, lambda: self._apply_eos(gen))
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            if not self._suppress_error_box:
                self._suppress_error_box = True
                QMessageBox.warning(self, "再生エラー", "このファイルは再生できません。対応形式か確認してください。")

    def _apply_eos(self, gen: int) -> None:
        if gen != self._media_gen:
            return
        if self.player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        # プレイリストに次があれば連続再生、なければ停止表示。
        if self._advance_if_in_playlist():
            return
        self._do_stop()
        self.time_label.setText(f"00:00 / {format_ms(self.player.duration())} (終了)")

    @Slot()
    def on_error(self) -> None:
        err = self.player.error()
        if err == QMediaPlayer.Error.NoError:
            return
        msg = self.player.errorString() or "不明な再生エラー"
        # InvalidMedia と重複表示しない
        if not self._suppress_error_box:
            self._suppress_error_box = True
            QMessageBox.warning(self, "再生エラー", f"読み込みに失敗しました:\n{msg}")


def _run_selftest(argv: list[str]) -> int:
    """配布exe/CI 用の自己診断。動画を開き、実際にデコードが進むか確認する。

    使い方:
        mplayer.exe --selftest <動画> [--selftest-out <結果jsonパス>]
    終了コード: 0=成功, 1=失敗。ウィンドウ付きexeでも結果が取れるよう、
    指定があればJSONファイルにも書き出す。
    """
    import time

    video = ""
    out_path = None
    try:
        i = argv.index("--selftest")
        if i + 1 < len(argv):
            video = argv[i + 1]
    except ValueError:
        pass
    if "--selftest-out" in argv:
        j = argv.index("--selftest-out")
        if j + 1 < len(argv):
            out_path = argv[j + 1]

    app = QApplication(argv[:1])
    w = PlayerWindow()
    w.show()
    w.vol.setValue(0)  # 診断中は無音
    result = {"ok": False, "reason": "", "position": 0, "duration": 0}

    if not video or not os.path.isfile(video):
        result["reason"] = f"video not found: {video!r}"
    else:
        w.load(video)
        deadline = time.time() + 15.0
        while time.time() < deadline:
            app.processEvents()
            pos, dur = w.player.position(), w.player.duration()
            if dur > 0 and pos > 0:
                result.update(ok=True, position=pos, duration=dur)
                break
            time.sleep(0.05)
        if not result["ok"]:
            result["reason"] = "no playback progress within 15s"

    try:
        w.player.pause()
    except Exception:
        pass
    if out_path:
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
        except Exception:
            pass
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    if "--selftest" in args:
        return _run_selftest(args)
    app = QApplication(sys.argv if argv is None else argv)
    if os.path.isfile(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    w = PlayerWindow()
    w.restore_session()
    w.show()
    # 起動引数で動画指定があれば自動オープン (検証用)
    if len(args) > 1 and os.path.isfile(args[1]):
        w.load(args[1])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
