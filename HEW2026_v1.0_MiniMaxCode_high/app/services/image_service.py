"""PNG の検証と保存。

仕様決定事項3章：合成 PNG は 5MiB 以内。実在する PNG であることを
署名と IHDR で確認してから保存する。
"""

from __future__ import annotations

import base64
import binascii
import re
import struct
import uuid
import zlib
from pathlib import Path

from flask import current_app

from app.config import upload_root
from app.services.errors import ValidationError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_DATA_URL_PATTERN = re.compile(r"^data:image/png;base64,(?P<payload>.+)$", re.S)


def decode_data_url(text: str) -> bytes:
    """data URL 形式の PNG を素のバイト列へ戻す。"""
    if not text:
        raise ValidationError("画像データが空です。")
    match = _DATA_URL_PATTERN.match(text.strip())
    payload = match.group("payload") if match else text.strip()
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("画像データを読み取れませんでした。") from exc


def validate_png(data: bytes, max_bytes: int | None = None) -> dict:
    """PNG であることを検証し、寸法を返す。

    署名・IHDR チャンクを検査し、サイズ上限と Canvas 寸法の上限も見る。
    """
    limit = max_bytes if max_bytes is not None else current_app.config["MAX_IMAGE_BYTES"]
    if not data:
        raise ValidationError("画像データが空です。")
    if len(data) > limit:
        raise ValidationError(
            f"画像サイズが上限（{limit // 1024 // 1024}MiB）を超えています。"
        )
    if not data.startswith(PNG_SIGNATURE):
        raise ValidationError("PNG 形式の画像ではありません。")
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ValidationError("PNG のヘッダーが壊れています。")

    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise ValidationError("画像の寸法が不正です。")
    canvas_size = current_app.config["CANVAS_SIZE"]
    if width > canvas_size or height > canvas_size:
        raise ValidationError(
            f"画像の寸法は {canvas_size}×{canvas_size}px 以内にしてください。"
        )
    return {"width": width, "height": height, "size": len(data)}


def save_png(data: bytes, subdir: str = "artworks") -> str:
    """検証済み PNG を UUID 名のファイルへ保存し、相対パスを返す。"""
    validate_png(data)
    root: Path = upload_root(current_app.config["UPLOAD_FOLDER"])
    target_dir = root / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    (target_dir / filename).write_bytes(data)
    return f"{subdir}/{filename}"


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    """PNG のチャンク（長さ・種別・データ・CRC）を組み立てる。"""
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def create_solid_png(
    width: int = 512, height: int = 512, rgb: tuple[int, int, int] = (214, 232, 255)
) -> bytes:
    """単色塗りの PNG を生成する（デモデータ・テスト用）。"""
    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )
