"""レイヤー資産の検証と ZIP 化。

仕様決定事項3章：
- 最大 10 レイヤー
- 各レイヤー PNG は 5MiB 以内、展開後合計 50MiB 以内（仮上限）
- ZIP は全レイヤーの PNG と構成情報（名前・順序・表示・不透明度）だけを持つ
- 元に戻す・やり直しの履歴は含めない
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from pathlib import Path

from flask import current_app

from app.config import upload_root
from app.services.errors import ValidationError
from app.services.image_service import decode_data_url, validate_png


def validate_layer_assets(layers: list[dict]) -> list[dict]:
    """レイヤー配列を検証し、正規化したリストを返す。

    各要素: ``{"name", "visible", "opacity", "data"}``
    ``data`` は data URL 文字列。検証後はバイト列へ_decodeして保持する。
    """
    if not isinstance(layers, list):
        raise ValidationError("レイヤーデータの形式が不正です。")

    max_layers = current_app.config["MAX_LAYERS"]
    if len(layers) == 0:
        raise ValidationError("少なくとも 1 枚のレイヤーが必要です。")
    if len(layers) > max_layers:
        raise ValidationError(f"レイヤー数は最大 {max_layers} 枚です。")

    max_layer_bytes = current_app.config["MAX_LAYER_BYTES"]
    max_total_bytes = current_app.config["MAX_LAYER_TOTAL_BYTES"]

    validated: list[dict] = []
    total = 0
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise ValidationError("レイヤーデータの形式が不正です。")
        name = str(layer.get("name") or f"layer{index + 1}")[:50]
        visible = bool(layer.get("visible", True))
        try:
            opacity = float(layer.get("opacity", 1.0))
        except (TypeError, ValueError) as exc:
            raise ValidationError("レイヤーの不透明度が不正です。") from exc
        opacity = min(1.0, max(0.0, opacity))

        raw = decode_data_url(layer.get("data") or "")
        if len(raw) > max_layer_bytes:
            raise ValidationError(
                f"レイヤー「{name}」が上限（{max_layer_bytes // 1024 // 1024}MiB）"
                "を超えています。"
            )
        validate_png(raw, max_bytes=max_layer_bytes)
        total += len(raw)
        if total > max_total_bytes:
            raise ValidationError(
                "レイヤーの合計サイズが上限"
                f"（{max_total_bytes // 1024 // 1024}MiB）を超えています。"
            )
        validated.append(
            {
                "name": name,
                "visible": visible,
                "opacity": opacity,
                "data": raw,
            }
        )
    return validated


def build_layer_archive(layers: list[dict], manifest: dict | None = None) -> bytes:
    """検証済みレイヤーから ZIP バイト列を作る。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, layer in enumerate(layers, start=1):
            archive.writestr(
                f"layers/{index:03d}_{layer['name']}.png", layer["data"]
            )
        payload = {
            "layers": [
                {
                    "name": layer["name"],
                    "order": index,
                    "visible": layer["visible"],
                    "opacity": layer["opacity"],
                    "file": f"layers/{index:03d}_{layer['name']}.png",
                }
                for index, layer in enumerate(layers, start=1)
            ],
            "note": "編集履歴（undo/redo）は含みません。",
        }
        if manifest:
            payload["manifest"] = manifest
        archive.writestr(
            "manifest.json", json.dumps(payload, ensure_ascii=False, indent=2)
        )
    return buffer.getvalue()


def save_layer_archive(layers: list[dict], manifest: dict | None = None) -> str:
    """レイヤー ZIP を保存し、相対パスを返す。"""
    archive = build_layer_archive(layers, manifest)
    root: Path = upload_root(current_app.config["UPLOAD_FOLDER"])
    target_dir = root / "layers"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.zip"
    (target_dir / filename).write_bytes(archive)
    return f"layers/{filename}"
