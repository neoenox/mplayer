# Changelog

本プロジェクトの主な変更点を記録します。
形式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従います。

## [1.2.0] - 2026-10-16

### Added
- 字幕の表示設定: 「字幕」メニューからサイズ (小/中/大) と位置 (下/中央/上) を変更可能。
  設定は `session.json` に保存され次回起動時に復元されます

### Fixed
- テストランナーが子プロセスの日本語出力を cp932 で復号して落ちる問題を修正 (UTF-8 に統一)

### Changed
- CI の GitHub Actions を最新メジャーに更新 (checkout@v7, setup-python@v7,
  upload-artifact@v7, action-gh-release@v3)

## [1.1.0] - 2026-10-16

### Added
- セッションの永続化 (`session.json`): 音量・ミュート・再生速度・プレイリストを
  終了時に保存し、次回起動時に復元します
- テスト時に `MPLAYER_SESSION_FILE` で保存先を隔離できます

## [1.0.0] - 2026-10-16

初回リリース。Windows 向けの最小限のローカル動画プレイヤー。

### Added
- 動画を開く / ドラッグ&ドロップ / 再生・一時停止・停止
- シークバーと `現在 / 全体` の時間表示
- 音量スライダーとミュート
- 全画面切替 (ボタン / F11 / ダブルクリック、Esc で解除)
- 再生速度の切替 (0.5 / 1.0 / 1.5 / 2.0 倍)
- 前回再生位置の記憶と自動再開 (`resume.json`)
- キーボードショートカット (Space, ←/→, ↑/↓, F, M, S, Ctrl+←/→)
- 字幕 (.srt) 表示。動画と同名の `.srt` を自動読み込み、ON/OFF 切替
- プレイリストと連続再生 (終了時に次の動画へ自動送り)
- PyInstaller による配布用 exe のビルド (`build_exe.bat`) と自己診断 (`--selftest`)
- GitHub Actions による CI (テスト + exe ビルド) と、タグ push でのリリース自動作成

### Notes
- 再生には PySide6 同梱の FFmpeg バックエンドを使用し、外部 VLC / FFmpeg は不要。
- Qt 6.12 の FFmpeg バックエンドの既知の問題 (一時停止後の `stop()` など) を回避する
  実装を含みます。
