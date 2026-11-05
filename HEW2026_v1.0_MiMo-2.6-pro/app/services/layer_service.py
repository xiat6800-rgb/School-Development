"""レイヤー付きZIP（アプリ独自形式）の検証と保存。

ZIP 構成:
    manifest.json   名前・順序・表示状態・不透明度
    layers/000.png  レイヤーPNG（非表示レイヤーも含む）
編集履歴（元に戻す履歴）は含めない。
"""

import io
import json
import os
import zipfile

from flask import current_app
from PIL import Image


class InvalidLayerError(Exception):
    """レイヤー構成・容量・寸法が要件を満たさない。"""


def _validate_layer_image(data, index):
    max_bytes = current_app.config["MAX_LAYER_BYTES"]
    if len(data) == 0:
        raise InvalidLayerError(f"レイヤー{index}のPNGが空です。")
    if len(data) > max_bytes:
        raise InvalidLayerError(f"レイヤー{index}のPNGは5MiB以内にしてください。")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise InvalidLayerError(
            f"レイヤー{index}がPNGとして読み込めません。"
        ) from exc
    if image.format != "PNG":
        raise InvalidLayerError(f"レイヤー{index}はPNG形式にしてください。")
    size = current_app.config["CANVAS_SIZE"]
    if image.size != (size, size):
        raise InvalidLayerError(
            f"レイヤー{index}は{size}x{size}pxにしてください。"
        )


def validate_layer_assets(layer_files, manifest):
    """最大10レイヤー・寸法・構成情報・容量を検証する。

    layer_files: レイヤーPNGの FileStorage リスト（表示順）
    manifest: [{"name": str, "visible": bool, "opacity": float}, ...]
    戻り値: バイト列のリスト
    """
    max_layers = current_app.config["MAX_LAYERS"]
    if not layer_files:
        raise InvalidLayerError("レイヤーが指定されていません。")
    if len(layer_files) > max_layers:
        raise InvalidLayerError(f"レイヤーは最大{max_layers}枚までです。")
    if not isinstance(manifest, list) or len(manifest) != len(layer_files):
        raise InvalidLayerError("レイヤー構成情報が画像と一致しません。")

    total_limit = current_app.config["MAX_LAYERS_TOTAL_BYTES"]
    layer_bytes = []
    total = 0
    for index, (file_storage, entry) in enumerate(zip(layer_files, manifest)):
        if not isinstance(entry, dict):
            raise InvalidLayerError(f"レイヤー{index}の構成情報が不正です。")
        for key in ("name", "visible", "opacity"):
            if key not in entry:
                raise InvalidLayerError(
                    f"レイヤー{index}の構成情報に {key} がありません。"
                )
        opacity = entry["opacity"]
        try:
            opacity_value = float(opacity)
        except (TypeError, ValueError) as exc:
            raise InvalidLayerError(
                f"レイヤー{index}の不透明度が不正です。"
            ) from exc
        if not 0.0 <= opacity_value <= 1.0:
            raise InvalidLayerError(
                f"レイヤー{index}の不透明度は0〜1で指定してください。"
            )
        data = file_storage.read()
        file_storage.seek(0)
        _validate_layer_image(data, index)
        total += len(data)
        if total > total_limit:
            raise InvalidLayerError("レイヤー合計は展開後50MiB以内にしてください。")
        layer_bytes.append(data)
    return layer_bytes


def save_layer_archive(layer_bytes, manifest, artwork_id):
    """全レイヤーPNGと構成情報をZIPとして保存し、相対パスを返す。"""
    rel_dir = str(artwork_id)
    abs_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(abs_dir, "layers.zip")
    with zipfile.ZipFile(abs_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        normalized = []
        for index, entry in enumerate(manifest):
            normalized.append(
                {
                    "name": str(entry["name"])[:100],
                    "order": index,
                    "visible": bool(entry["visible"]),
                    "opacity": float(entry["opacity"]),
                    "file": f"layers/{index:03d}.png",
                }
            )
            archive.writestr(f"layers/{index:03d}.png", layer_bytes[index])
        archive.writestr(
            "manifest.json",
            json.dumps({"layers": normalized}, ensure_ascii=False, indent=2),
        )
    return os.path.join(rel_dir, "layers.zip").replace("\\", "/")
