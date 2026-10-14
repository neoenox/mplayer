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
        self.open_btn = QPushButton("開く")
        self.open_btn.clicked.connect(self.open_file_dialog)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.setText("再生")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.toggle_play)

        self.stop_btn = QPushButton("停止")
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
        # 誤操作防止: ファイル未ロード時は無効
        self.seek.setEnabled(False)

        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        self.vol.setMaximumWidth(120)
        self.vol.valueChanged.connect(self.change_volume)

        self.mute_btn = QPushButton("ミュート")
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_mute)

        self.fs_btn = QPushButton("全画面")
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

        self._is_fullscreen = False
        self._suppress_error_box = False
        # 遅延シークの世代管理。load()ごとに加算し、古いファイル向けの
        # 予約シークが新ファイルへ誤適用されるのを防ぐ (P5)。
        self._media_gen = 0

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
        self._suppress_error_box = False
        self._media_gen += 1
        self.player.setSource(QUrl.fromLocalFile(path))
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.seek.setEnabled(True)
        self.setWindowTitle(f"シンプル動画プレイヤー - {os.path.basename(path)}")
        self.player.play()
        return True

    # ---------- 操作 ----------
    @Slot()
    def toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
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
        gen, target = self._media_gen, self.seek.value()
        QTimer.singleShot(0, lambda: self._apply_seek(gen, target))

    @Slot(int)
    def seek_action(self, action: int) -> None:
        # actionTriggered precedes valueChanged; sliderPosition holds the new target.
        # Mouse drags remain handled once on release.
        if self.seek.isSliderDown():
            return
        gen, target = self._media_gen, self.seek.sliderPosition()
        QTimer.singleShot(0, lambda: self._apply_seek(gen, target))

    def _apply_seek(self, gen: int, target: int) -> None:
        if gen != self._media_gen:
            return
        try:
            self.player.setPosition(target)
        except Exception:
            pass

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


def main(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    w = PlayerWindow()
    w.show()
    # 起動引数で動画指定があれば自動オープン (検証用)
    args = argv if argv is not None else sys.argv
    if len(args) > 1 and os.path.isfile(args[1]):
        w.load(args[1])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
