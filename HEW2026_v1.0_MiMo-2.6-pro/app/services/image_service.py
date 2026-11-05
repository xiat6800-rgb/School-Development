"""合成PNGの検証と保存。"""

import os
import uuid

from flask import current_app
from PIL import Image


class InvalidImageError(Exception):
    """PNGの形式・サイズ・寸法が要件を満たさない。"""


def validate_png(file_storage):
    """実際の画像形式・ファイルサイズ・寸法を検証し、PIL Image を返す。"""
    if file_storage is None or not file_storage.filename:
        raise InvalidImageError("PNGファイルが指定されていません。")
    data = file_storage.read()
    file_storage.seek(0)
    max_bytes = current_app.config["MAX_PNG_BYTES"]
    if len(data) == 0:
        raise InvalidImageError("PNGファイルが空です。")
    if len(data) > max_bytes:
        raise InvalidImageError("合成PNGは5MiB以内にしてください。")
    try:
        image = Image.open(file_storage)
        image.load()
    except Exception as exc:
        raise InvalidImageError("PNGとして読み込めません。") from exc
    finally:
        file_storage.seek(0)
    if image.format != "PNG":
        raise InvalidImageError("PNG形式で保存してください。")
    size = current_app.config["CANVAS_SIZE"]
    if image.size != (size, size):
        raise InvalidImageError(f"画像は{size}x{size}pxにしてください。")
    return image


def save_png(file_storage, artwork_id):
    """検証済みPNGをUUID名で保存し、保存先の相対パスを返す。"""
    rel_dir = os.path.join(str(artwork_id))
    abs_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    abs_path = os.path.join(abs_dir, filename)
    file_storage.save(abs_path)
    return os.path.join(rel_dir, filename).replace("\\", "/")
