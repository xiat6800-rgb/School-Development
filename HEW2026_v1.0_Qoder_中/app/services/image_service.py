"""画像サービス。PNG の検証と UUID ファイル名での保存を担当する。"""
import struct
import uuid
from pathlib import Path

from flask import current_app

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class InvalidImageError(Exception):
    """PNG の形式・サイズ・寸法が不正な場合に発生する。"""


def validate_png(data):
    """実際の画像形式・ファイルサイズ・寸法を検証する（要件定義書 5.2）。"""
    max_bytes = current_app.config["MAX_COMPOSITE_PNG_BYTES"]
    size = current_app.config["CANVAS_SIZE"]
    if not data or len(data) > max_bytes:
        raise InvalidImageError(f"合成PNGは {max_bytes // (1024 * 1024)}MiB 以内にしてください。")
    if not data.startswith(PNG_SIGNATURE):
        raise InvalidImageError("PNG 形式の画像ではありません。")
    # IHDR チャンク: 長さ(4) + 'IHDR'(4) + 幅(4) + 高さ(4)
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise InvalidImageError("PNG データが壊れています。")
    width, height = struct.unpack(">II", data[16:24])
    if width != size or height != size:
        raise InvalidImageError(f"画像は {size}×{size}px が必要です（実際: {width}×{height}px）。")
    return width, height


def save_png(data):
    """検証済み PNG を UUID のファイル名で保存し、相対保存先を返す。"""
    validate_png(data)
    filename = f"{uuid.uuid4().hex}.png"
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_bytes(data)
    return filename
