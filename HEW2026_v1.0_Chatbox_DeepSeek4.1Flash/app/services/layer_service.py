"""レイヤー画像と構成情報を ZIP として検証・保存する。"""

import io
import json
import re
import zipfile

from flask import current_app

from .errors import InvalidImageError, ValidationError
from . import image_service

SAFE_NAME = re.compile(r"[^0-9A-Za-z_.\-]+")
MANIFEST_NAME = "manifest.json"


def parse_manifest(raw_manifest):
    """クライアントから送られた構成情報（JSON 文字列）を検証する。"""
    if raw_manifest in (None, ""):
        raise ValidationError("レイヤー構成情報がありません。")
    try:
        manifest = json.loads(raw_manifest)
    except (TypeError, ValueError):
        raise ValidationError("レイヤー構成情報を読み取れません。")

    layers = manifest.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValidationError("レイヤー構成情報にレイヤーがありません。")

    max_layers = current_app.config["MAX_LAYERS"]
    if len(layers) > max_layers:
        raise ValidationError(f"レイヤーは最大 {max_layers} 枚までです。")

    normalized = []
    canvas_size = current_app.config["CANVAS_SIZE"]
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise ValidationError("レイヤー構成情報の形式が不正です。")
        name = str(layer.get("name") or f"layer{index + 1}").strip()[:50]
        raw_visible = layer.get("visible", True)
        visible = raw_visible if isinstance(raw_visible, bool) else True
        try:
            opacity = float(layer.get("opacity", 1.0))
        except (TypeError, ValueError):
            opacity = 1.0
        opacity = min(max(opacity, 0.0), 1.0)
        normalized.append(
            {
                "index": index,
                "name": name,
                "visible": visible,
                "opacity": round(opacity, 3),
            }
        )

    manifest_out = {"canvas_size": manifest.get("canvas_size", canvas_size)}
    manifest_out["layers"] = normalized
    return manifest_out


def validate_layers(layer_files, manifest):
    """レイヤー数・各容量・展開後合計・寸法を検証する。"""
    config = current_app.config
    max_layers = config["MAX_LAYERS"]
    if not layer_files:
        raise ValidationError("レイヤー画像がありません。")
    if len(layer_files) > max_layers:
        raise ValidationError(f"レイヤーは最大 {max_layers} 枚までです。")
    if len(layer_files) != len(manifest["layers"]):
        raise ValidationError("レイヤー画像の数と構成情報が一致しません。")

    total = 0
    sizes = []
    for index, data in enumerate(layer_files):
        width, height = image_service.validate_png(
            data,
            max_bytes=config["MAX_LAYER_PNG_BYTES"],
            expected_size=config["CANVAS_SIZE"],
            label=f"レイヤー{index + 1}",
        )
        total += len(data)
        sizes.append({"index": index, "width": width, "height": height})
        if total > config["MAX_LAYER_TOTAL_BYTES"]:
            raise InvalidImageError(
                "レイヤーの展開後合計が上限（50MiB）を超えています。"
            )
    return sizes


def build_layer_archive(layer_files, manifest):
    """全レイヤー PNG と構成情報を含む独自形式 ZIP を組み立てる。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            MANIFEST_NAME,
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        for index, data in enumerate(layer_files):
            layer = manifest["layers"][index]
            safe = SAFE_NAME.sub("_", layer["name"]) or f"layer{index + 1}"
            archive.writestr(f"layers/{index:02d}_{safe}.png", data)
    return buffer.getvalue()


def save_layer_archive(data, upload_root):
    """ZIP を保存し、相対パスを返す。"""
    return image_service.save_bytes(data, upload_root, "layers", ".zip")
