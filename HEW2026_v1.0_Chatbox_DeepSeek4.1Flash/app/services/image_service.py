"""PNG の検証と保存。Pillow などの外部依存を増やさずヘッダーを検査する。"""

import os
import uuid

from .errors import InvalidImageError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MIN_PNG_HEADER_LENGTH = 33


def _default_limit():
    from flask import current_app

    return current_app.config["MAX_COMPOSITE_PNG_BYTES"]


def validate_png(data, max_bytes=None, expected_size=None, label="PNG"):
    """実際の画像形式・容量・寸法を検証し、(幅, 高さ) を返す。

    拡張子ではなく PNG シグネチャと IHDR を確認する。
    """
    limit = max_bytes if max_bytes is not None else _default_limit()
    if not data:
        raise InvalidImageError(f"{label} が空です。")
    if len(data) > limit:
        raise InvalidImageError(
            f"{label} の容量が上限（{limit // (1024 * 1024)}MiB）を超えています。"
        )
    if not data.startswith(PNG_SIGNATURE):
        raise InvalidImageError(f"{label} が PNG 形式ではありません。")
    if len(data) < MIN_PNG_HEADER_LENGTH or data[12:16] != b"IHDR":
        raise InvalidImageError(f"{label} のヘッダーが壊れています。")

    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise InvalidImageError(f"{label} の寸法が不正です。")
    if expected_size is not None and (width != expected_size or height != expected_size):
        raise InvalidImageError(
            f"{label} の寸法は {expected_size}×{expected_size}px である必要があります"
            f"（実際は {width}×{height}px）。"
        )
    return width, height


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def save_bytes(data, upload_root, subdir, suffix):
    """バイト列を UUID 名で保存し、UPLOAD_ROOT からの相対パスを返す。"""
    directory = os.path.join(upload_root, subdir)
    _ensure_dir(directory)
    filename = f"{uuid.uuid4().hex}{suffix}"
    with open(os.path.join(directory, filename), "wb") as handle:
        handle.write(data)
    return f"{subdir}/{filename}"


def save_png(data, upload_root, subdir="composite"):
    """検証済み PNG を保存し、相対パスを返す。"""
    return save_bytes(data, upload_root, subdir, ".png")


def absolute_path(upload_root, relative_path):
    """相対パスを絶対パスへ解決する。"""
    if not relative_path:
        return None
    return os.path.join(upload_root, relative_path)
