"""Pure subtitle text processing used by the player UI."""
from __future__ import annotations

import re

# 字幕の文字コード選択肢。auto は BOM/UTF-8/CP932 を順に試す。
SUB_ENCODINGS = ("auto", "utf-8", "cp932")


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


def _is_srt_timestamp_line(line: str) -> bool:
    """SRT のタイムスタンプ行かどうか (本文の矢印と区別する)。"""
    return "-->" in line and bool(re.search(r"\d{1,2}:\d{2}", line))


def parse_srt(text: str) -> list[tuple[int, int, str]]:
    """SRT文字列を (開始ms, 終了ms, 本文) のリストに変換する。

    空行区切りが無い SRT も扱える。不正なブロックは黙って読み飛ばす。
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = normalized.split("\n")
    cues: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        if not _is_srt_timestamp_line(lines[i]):
            i += 1
            continue
        left, _, right = lines[i].partition("-->")
        try:
            start = _parse_srt_timestamp(left)
            # 末尾に座標等が付く形式 ("... --> 00:00:02,000 X1:..") を許容
            end = _parse_srt_timestamp(right.strip().split()[0])
        except Exception:
            i += 1
            continue
        body_lines: list[str] = []
        i += 1
        while i < len(lines) and not _is_srt_timestamp_line(lines[i]):
            stripped = lines[i].strip()
            # 次のcueの番号行は本文に含めない
            if (stripped.isdigit() and i + 1 < len(lines)
                    and _is_srt_timestamp_line(lines[i + 1])):
                break
            body_lines.append(lines[i])
            i += 1
        body = "\n".join(body_lines).strip()
        if body:
            cues.append((start, end, body))
    cues.sort(key=lambda c: c[0])
    return cues


def decode_subtitle_bytes(data: bytes, encoding: str = "auto") -> tuple[str, str]:
    """字幕のバイト列をテキストへ復号する。(本文, 採用した文字コード) を返す。"""
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


def contrast_outline(rgb) -> tuple[int, int, int]:
    """塗り色の輝度から縁取り色 (黒 or 白) を選ぶ。"""
    r, g, b = (int(v) for v in rgb)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if lum >= 128 else (255, 255, 255)
