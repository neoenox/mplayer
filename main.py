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

import json
import os
import sys

from PySide6.QtCore import Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

SUPPORTED_FILTER = (
    "動画ファイル (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.mpg *.mpeg *.wmv);;すべてのファイル (*.*)"
)

# 前回再生位置の保存先 (アプリと同じフォルダ)。上限100件。
RESUME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume.json")
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


class PlayerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("シンプル動画プレイヤー")
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
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.fs_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.video, 1)
        layout.addLayout(top_row)
        layout.addLayout(bottom_row)

        central = QWidget(self)
        central.setLayout(layout)
        self.setCentralWidget(central)

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

        self._is_fullscreen = False
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
        self.player.setSource(QUrl.fromLocalFile(path))
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.seek.setEnabled(True)
        self.setWindowTitle(f"シンプル動画プレイヤー - {os.path.basename(path)}")
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
            self.showFullScreen()
            self.fs_btn.setText("全画面解除")

    @Slot()
    def exit_fullscreen(self) -> None:
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.showNormal()
            self.fs_btn.setText("全画面")

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        # 再生を先に止めてから閉じる。stop() ではなく pause() を使う
        # (_do_stop と同じ理由: player.stop() 後のデッドロック防止)。
        # 閉じる前に位置を記憶する (次回起動時に再開できる)。
        self._remember_current()
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
        if urls:
            local = urls[0].toLocalFile()
            if local:
                self.load(local)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    # ---------- 再生状態反映 ----------
    @Slot(int)
    def on_position_changed(self, pos: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        self.time_label.setText(f"{format_ms(pos)} / {format_ms(self.player.duration())}")

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
    w = PlayerWindow()
    w.show()
    # 起動引数で動画指定があれば自動オープン (検証用)
    if len(args) > 1 and os.path.isfile(args[1]):
        w.load(args[1])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
