"""Silent self-update for portable Windows builds.

GitHub Releases の最新 portable zip をバックグラウンドで確認し、新しい版が
あれば次回起動用にステージングする。実際の差し替えはアプリ終了後に
PowerShell ヘルパーを detached で起動して行う (実行中exeは上書きできない)。

ダイアログは一切出さない。書き込み権限のない場所 (Program Files 等) では
何もせずログだけ残す。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile

RELEASES_API = "https://api.github.com/repos/neoenox/mplayer/releases/latest"
ASSET_RE = re.compile(r"mplayer-windows-v?[^/\\]+\.zip$", re.IGNORECASE)
LOG_NAME = "mplayer_autoupdate.log"
PRESERVE_FILES = ("resume.json", "session.json")
_TIMEOUT_CHECK = 8
_TIMEOUT_DOWNLOAD = 120

_PENDING: list[str | None] = [None]
_LOCK = threading.Lock()
_STATUS = {"text": "", "staged": False, "time": 0.0}
_PENDING_VERSION: list[str | None] = [None]
_LAST_TAG: list[str] = [""]
_CURRENT_VERSION: list[str] = [""]

_POWERSHELL = r"""param([string]$AppDir, [string]$StageDir, [string]$TargetPid, [string]$ExeName,
                        [string]$MarkerPath, [string]$FromVersion, [string]$ToVersion)
$ErrorActionPreference = 'SilentlyContinue'
$log = Join-Path $env:TEMP 'mplayer_autoupdate.log'
function Log($m) { Add-Content -LiteralPath $log -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' apply: ' + $m) }
function Write-Result([bool]$Ok, [string]$Reason) {
    if (-not $MarkerPath) { return }
    $payload = @{ ok = $Ok; from = $FromVersion; to = $ToVersion; reason = $Reason; time = (Get-Date -Format o) } | ConvertTo-Json -Compress
    try { Set-Content -LiteralPath $MarkerPath -Value $payload -Encoding UTF8 }
    catch { Log ('marker failed: ' + $_.Exception.Message) }
}
$app = $AppDir.TrimEnd('\')
$stage = $StageDir.TrimEnd('\')
$pidToWait = [int]$TargetPid
for ($i = 0; $i -lt 400; $i++) {
    if (-not (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 250
}
if (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {
    Log 'old process still running; abort'
    Write-Result $false 'old process still running'
    exit 1
}

Start-Sleep -Milliseconds 1500
function Rename-WithRetry([string]$Path, [string]$NewName) {
    for ($i = 0; $i -lt 20; $i++) {
        try { Rename-Item -LiteralPath $Path -NewName $NewName -ErrorAction Stop; return }
        catch { Start-Sleep -Milliseconds 500 }
    }
    throw ('could not rename ' + $Path + ' after 10 seconds')
}
$parent = Split-Path -Parent $app
$leaf = Split-Path -Leaf $app
$backup = Join-Path $parent ('mplayer-backup-' + [guid]::NewGuid().ToString('N'))
foreach ($name in @('resume.json', 'session.json')) {
    $src = Join-Path $app $name
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $stage $name) -Force }
}
try {
    Rename-WithRetry $app (Split-Path -Leaf $backup)
    Rename-WithRetry $stage $leaf
    Start-Process -FilePath (Join-Path $app $ExeName) -WorkingDirectory $app
    Log 'update applied'
    Write-Result $true ''
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $backup -Recurse -Force
} catch {
    Log ('failed: ' + $_.Exception.Message)
    if ((Test-Path -LiteralPath $backup) -and (-not (Test-Path -LiteralPath $app))) {
        Rename-Item -LiteralPath $backup -NewName $leaf
    }
    Write-Result $false $_.Exception.Message
    exit 1
}
"""


def log(message: str) -> None:
    """サイレント更新の結果を一時ログに残す (UI は一切変更しない)。"""
    try:
        path = os.path.join(tempfile.gettempdir(), LOG_NAME)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def enabled() -> bool:
    """配布exeのみ自動更新を有効にする (開発/テストではネットワーク不使用)。"""
    if os.environ.get("MPLAYER_NO_AUTOUPDATE") == "1":
        return False
    return bool(getattr(sys, "frozen", False)) or \
        os.environ.get("MPLAYER_AUTOUPDATE") == "1"


def status() -> dict:
    """UI が表示する更新ステータスのスナップショット。"""
    with _LOCK:
        return dict(_STATUS)


def set_status(text: str, staged: bool = False) -> None:
    with _LOCK:
        _STATUS.update(text=text, staged=staged, time=time.time())


def clear_status() -> None:
    with _LOCK:
        _STATUS.update(text="", staged=False, time=0.0)


def state_dir() -> str:
    return os.environ.get(
        "MPLAYER_STATE_DIR",
        os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "mplayer"),
    )


def update_result_path() -> str:
    return os.path.join(state_dir(), "update_result.json")


def record_update_result(ok: bool, from_version: str = "", to_version: str = "",
                         reason: str = "") -> None:
    """次回起動に見せる更新結果を残す (成功・失敗どちらも)。"""
    path = update_result_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ok": bool(ok), "from": from_version, "to": to_version,
                   "reason": reason, "time": time.strftime("%Y-%m-%dT%H:%M:%S")},
                  f, ensure_ascii=False)


def consume_update_result() -> dict | None:
    """更新結果を読み取って削除する (一度だけ表示するため)。"""
    path = update_result_path()
    data = None
    try:
        with open(path, encoding="utf-8-sig") as f:
            value = json.load(f)
        data = value if isinstance(value, dict) else None
    except Exception:
        pass
    try:
        os.remove(path)
    except OSError:
        pass
    return data


def version_tuple(text) -> tuple[int, ...]:
    """'v1.27.0' / '1.27.1' を比較用の整数タプルにする。"""
    nums = re.findall(r"\d+", str(text))
    return tuple(int(n) for n in nums[:4]) if nums else (0,)


def is_newer(latest, current) -> bool:
    return version_tuple(latest) > version_tuple(current)


def find_portable_asset(release: dict) -> tuple[str | None, str | None]:
    """latest release から portable zip の URL と名前を取り出す。"""
    for asset in release.get("assets") or []:
        name = asset.get("name") or ""
        url = asset.get("browser_download_url")
        if url and ASSET_RE.search(name):
            return url, name
    return None, None


def fetch_latest(urlopen=None, timeout: float = _TIMEOUT_CHECK) -> dict:
    opener = urlopen or urllib.request.urlopen
    request = urllib.request.Request(RELEASES_API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "mplayer-silent-updater",
    })
    with opener(request, timeout=timeout) as response:
        return json.load(response)


def download(url: str, target: str, urlopen=None,
             timeout: float = _TIMEOUT_DOWNLOAD) -> str:
    opener = urlopen or urllib.request.urlopen
    request = urllib.request.Request(url, headers={
        "User-Agent": "mplayer-silent-updater",
    })
    with opener(request, timeout=timeout) as response, open(target, "wb") as f:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return target

def zip_has_app(zip_path: str) -> bool:
    """zip に mplayer.exe が入っているか (最低限の検証)。"""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return any(
                name.replace("\\", "/").lower().endswith("/mplayer.exe")
                or name.lower() == "mplayer.exe"
                for name in zf.namelist()
            )
    except Exception:
        return False


def stage_update(zip_path: str, stage_dir: str) -> str:
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir, ignore_errors=True)
    os.makedirs(stage_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(stage_dir)
    if not os.path.isfile(os.path.join(stage_dir, "mplayer.exe")):
        # zip が1階層のフォルダを持つ形式にも対応する。
        entries = [os.path.join(stage_dir, n) for n in os.listdir(stage_dir)
                   if os.path.isdir(os.path.join(stage_dir, n))]
        nested = next((p for p in entries
                       if os.path.isfile(os.path.join(p, "mplayer.exe"))), None)
        if nested is None:
            raise RuntimeError("portable zip has no mplayer.exe")
        for name in os.listdir(nested):
            os.replace(os.path.join(nested, name), os.path.join(stage_dir, name))
        shutil.rmtree(nested, ignore_errors=True)
    return stage_dir


def prepare(app_dir: str, current_version: str, urlopen=None) -> str | None:
    """更新があれば zip をダウンロードし、ステージング先を返す。"""
    release = fetch_latest(urlopen)
    tag = release.get("tag_name") or ""
    if not is_newer(tag, current_version):
        log(f"up to date (latest={tag}, current={current_version})")
        return None
    url, name = find_portable_asset(release)
    if not url:
        log(f"no portable asset in {tag}")
        return None
    parent = os.path.dirname(os.path.abspath(app_dir))
    if not os.access(parent, os.W_OK):
        log(f"skip: {parent} is not writable (silent update needs a portable folder)")
        return None

    fd, tmp_zip = tempfile.mkstemp(prefix="mplayer-update-", suffix=".zip")
    os.close(fd)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    stage = os.path.join(parent, f"mplayer-update-{version_tuple(tag)}-{stamp}-{os.getpid()}")
    try:
        download(url, tmp_zip, urlopen)
        if not zip_has_app(tmp_zip):
            raise RuntimeError(f"invalid portable zip: {name}")
        stage_update(tmp_zip, stage)
    except Exception as exc:
        shutil.rmtree(stage, ignore_errors=True)
        log(f"prepare failed: {exc}")
        return None
    finally:
        try:
            os.remove(tmp_zip)
        except OSError:
            pass
    _LAST_TAG[0] = tag
    log(f"staged {tag} -> {stage}")
    return stage


def start_background_check(app_dir: str, current_version: str) -> None:
    if not enabled():
        return
    _CURRENT_VERSION[0] = current_version
    set_status("更新を確認中…")

    def worker() -> None:
        try:
            stage = prepare(app_dir, current_version)
            if stage:
                with _LOCK:
                    _PENDING[0] = stage
                    _PENDING_VERSION[0] = _LAST_TAG[0]
                set_status("更新あり · 終了時に適用します", staged=True)
            else:
                set_status("最新版です")
        except Exception as exc:
            log(f"check failed: {exc}")
            set_status("更新の確認に失敗しました (詳細はログ)", staged=True)

    threading.Thread(target=worker, name="mplayer-updater", daemon=True).start()


def take_pending() -> str | None:
    with _LOCK:
        stage, _PENDING[0] = _PENDING[0], None
        return stage


def pending_update_info() -> tuple[str | None, str, str]:
    with _LOCK:
        return _PENDING[0], _PENDING_VERSION[0] or "", _CURRENT_VERSION[0]


def clear_pending() -> None:
    with _LOCK:
        _PENDING[0] = None
        _PENDING_VERSION[0] = None


def start_apply(app_dir: str, stage_dir: str, pid: int | None = None,
                exe_name: str = "mplayer.exe", marker_path: str = "",
                from_version: str = "", to_version: str = "") -> None:
    """アプリ終了後に差し替える PowerShell を detached で起動する。"""
    script = os.path.join(tempfile.gettempdir(), f"mplayer_update_{os.getpid()}.ps1")
    with open(script, "w", encoding="utf-8") as f:
        f.write(_POWERSHELL)
    args = ["powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", script,
            app_dir, stage_dir, str(os.getpid() if pid is None else pid), exe_name,
            marker_path, from_version, to_version]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
    log(f"apply scheduled: {stage_dir}")


def finalize(app_dir: str, exe_name: str = "mplayer.exe") -> None:
    """終了時に呼ばれる。保留中の更新があれば適用を開始する。"""
    if not enabled():
        return
    stage, to_ver, from_ver = pending_update_info()
    if stage and os.path.isdir(stage):
        set_status("更新を適用しています…", staged=True)
        try:
            os.makedirs(state_dir(), exist_ok=True)
            start_apply(app_dir, stage, exe_name=exe_name,
                        marker_path=update_result_path(),
                        from_version=from_ver, to_version=to_ver)
            clear_pending()
        except Exception as exc:
            log(f"apply failed: {exc}")
            record_update_result(False, from_ver, to_ver, str(exc))
            set_status("更新の適用に失敗しました (詳細はログ)", staged=True)
