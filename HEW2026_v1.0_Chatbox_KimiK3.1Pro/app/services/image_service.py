import io
import json
import os
import struct
import uuid
import zipfile
from pathlib import Path

from flask import current_app

from app.constants import (
    CANVAS_SIZE, MAX_ARCHIVE_UNCOMPRESSED_BYTES, MAX_LAYER_BYTES,
    MAX_LAYERS, MAX_PNG_BYTES,
)
from app.services.common import BusinessError


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_png(data):
    if not data or len(data) > MAX_PNG_BYTES:
        raise BusinessError("合成PNGは5MiB以内で送信してください。")
    if not data.startswith(PNG_SIGNATURE) or len(data) < 33:
        raise BusinessError("PNG形式の画像ではありません。")
    if data[12:16] != b"IHDR":
        raise BusinessError("PNGのIHDRを確認できません。")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (CANVAS_SIZE, CANVAS_SIZE):
        raise BusinessError("画像は1,024×1,024pxで保存してください。")
    return width, height


def validate_layer_assets(data):
    if not data:
        raise BusinessError("レイヤーZIPが空です。")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if any(i.is_dir() for i in infos):
                infos = [i for i in infos if not i.is_dir()]
            total = sum(i.file_size for i in infos)
            if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise BusinessError("ZIP展開後の合計は50MiB以内にしてください。")
            if "layers.json" not in archive.namelist():
                raise BusinessError("ZIPにlayers.jsonがありません。")
            manifest = json.loads(archive.read("layers.json").decode("utf-8"))
            layers = manifest.get("layers")
            if not isinstance(layers, list) or not 1 <= len(layers) <= MAX_LAYERS:
                raise BusinessError("レイヤーは1〜10枚で保存してください。")
            expected = set()
            for index, layer in enumerate(layers, 1):
                name = layer.get("file")
                if not name or name != f"layers/layer_{index:02d}.png":
                    raise BusinessError("レイヤー構成情報が不正です。")
                if name in expected:
                    raise BusinessError("レイヤー名が重複しています。")
                expected.add(name)
                info = archive.getinfo(name)
                if info.file_size > MAX_LAYER_BYTES:
                    raise BusinessError("各レイヤーPNGは5MiB以内にしてください。")
                layer_data = archive.read(name)
                if not layer_data.startswith(PNG_SIGNATURE):
                    raise BusinessError("レイヤーはPNG形式にしてください。")
                width, height = struct.unpack(">II", layer_data[16:24])
                if (width, height) != (CANVAS_SIZE, CANVAS_SIZE):
                    raise BusinessError("全レイヤーを1,024×1,024pxにしてください。")
                opacity = layer.get("opacity")
                if not isinstance(opacity, (int, float)) or not 0 <= opacity <= 1:
                    raise BusinessError("レイヤー不透明度が不正です。")
            if expected != {n for n in archive.namelist() if n != "layers.json"}:
                raise BusinessError("ZIP内のPNGと構成情報が一致しません。")
    except (zipfile.BadZipFile, KeyError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, BusinessError):
            raise
        raise BusinessError("レイヤーZIPを検証できません。") from exc
    return True


def _upload_root():
    root = Path(current_app.config["UPLOAD_FOLDER"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_upload(relative_path):
    root = _upload_root().resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents:
        raise BusinessError("保存先が不正です。")
    return target


def save_png_and_archive(png_data, archive_data):
    validate_png(png_data)
    validate_layer_assets(archive_data)
    token = uuid.uuid4().hex
    png_relative = f"artworks/{token}.png"
    zip_relative = f"artworks/{token}.zip"
    png_path = resolve_upload(png_relative)
    zip_path = resolve_upload(zip_relative)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_temp = png_path.with_suffix(".png.tmp")
    zip_temp = zip_path.with_suffix(".zip.tmp")
    try:
        png_temp.write_bytes(png_data)
        zip_temp.write_bytes(archive_data)
        os.replace(png_temp, png_path)
        os.replace(zip_temp, zip_path)
    finally:
        for path in (png_temp, zip_temp):
            if path.exists():
                path.unlink()
    return png_relative, zip_relative


def save_stream_preview(data):
    if not data or len(data) > MAX_PNG_BYTES or not data.startswith(PNG_SIGNATURE):
        raise BusinessError("配信プレビューは5MiB以内のPNGにしてください。")
    relative = f"previews/{uuid.uuid4().hex}.png"
    path = resolve_upload(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)
    return relative
