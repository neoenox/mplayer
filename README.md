# シンプル動画プレイヤー (Windows / Python + PySide6)

最小限のローカル動画再生アプリです。外部 VLC / FFmpeg の手動インストールは不要です。
PySide6 に同梱の FFmpeg バックエンド (`ffmpegmediaplugin.dll` + `avcodec-63` 等) で再生します。

## 動作環境

- Windows 10/11 (64bit)
- Python 3.11 (3.11.9で検証)
- 依存は `requirements.txt` に固定 (`requirements-lock.txt` は実測freeze)
- 外部VLC・FFmpegの手動インストール不要 (PySide6同梱のFFmpegを使用)

## セットアップ

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 起動

```bat
run.bat
rem 動画を指定して起動:
run.bat C:\path\to\movie.mp4
```

または:

```bat
.venv\Scripts\python.exe main.py
```

## 使い方 (日本語UI)

- 「開く」ボタン / ファイルメニュー / ドラッグ&ドロップで動画を開く
- 再生 / 一時停止 / 停止ボタン
- シークバーで位置移動、時間表示 `現在 / 全体`
- シークバーにフォーカスして矢印キーで1秒、PageUp/PageDownで10秒、Home/Endで先頭/末尾へ移動
- 音量スライダー + ミュート
- 全画面ボタン / F11 / ダブルクリックで切替、Esc で解除
- 再生終了・非対応ファイル・破損ファイルはダイアログ表示し、クラッシュしない

## 対応形式 (FFmpeg依存)

mp4 (H.264/AAC 推奨), mkv, avi, mov, webm, wmv 等。
Qt 6.12 時点で Windows でも FFmpeg が標準バックエンドです。

## 自動テスト (無音・無人で実行)

```bat
rem ワンコマンド検証 (venv作成〜全テスト):
check.bat
rem 直接実行・特定ステージ・詳細表示:
.venv\Scripts\python.exe tests\run_all.py
.venv\Scripts\python.exe tests\run_all.py p1b_seek
.venv\Scripts\python.exe tests\run_all.py -v
```

- 全ステージPASSを確認済み (詳細は `test_logs/summary.txt`)
- テスト中は音量0にするため音は出ません。製品の既定音量 (80) は変更しません
- 詳細ログは `test_logs/` に保存されます

## トラブルシュート

- 映像が出ない: ` .venv\Lib\site-packages\PySide6\plugins\multimedia\ffmpegmediaplugin.dll` の有無を確認
- 音が出ない: OS の音量ミキサーとアプリ内ミュートを確認
- コーデック不足 (例: HEVC 等): H.264/AAC の mp4 に変換して利用
