"""レイヤーサービス。全レイヤー PNG と構成情報 ZIP の検証・保存を担当する。"""
import io
import uuid
import zipfile
from pathlib import Path

from flask import current_app

MANIFEST_NAME = "manifest.json"


class InvalidLayerArchiveError(Exception):
    """レイヤー ZIP が不正な場合に発生する。"""


def validate_layer_assets(zip_bytes):
    """最大10レイヤー・寸法・構成情報・各画像と展開後合計の容量を検証する。"""
    max_layers = current_app.config["MAX_LAYERS"]
    max_each = current_app.config["MAX_LAYER_PNG_BYTES"]
    max_total = current_app.config["MAX_LAYER_TOTAL_BYTES"]

    if not zip_bytes:
        raise InvalidLayerArchiveError("レイヤーデータがありません。")
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        bad = zf.testzip()
        if bad is not None:
            raise InvalidLayerArchiveError(f"ZIP が壊れています: {bad}")
    except zipfile.BadZipFile as exc:
        raise InvalidLayerArchiveError("ZIP 形式を読み取れません。") from exc

    with zf:
        names = zf.namelist()
        if MANIFEST_NAME not in names:
            raise InvalidLayerArchiveError(f"{MANIFEST_NAME}（構成情報）が必要です。")
        layer_names = [n for n in names if n != MANIFEST_NAME]
        if len(layer_names) > max_layers:
            raise InvalidLayerArchiveError(f"レイヤーは最大 {max_layers} 枚までです。")
        total = 0
        for info in zf.infolist():
            total += info.file_size
            if total > max_total:
                raise InvalidLayerArchiveError(
                    f"展開後の合計が {max_total // (1024 * 1024)}MiB を超えています。"
                )
            if info.filename == MANIFEST_NAME:
                continue
            if info.file_size > max_each:
                raise InvalidLayerArchiveError(
                    f"レイヤー画像 1 枚は {max_each // (1024 * 1024)}MiB 以内にしてください。"
                )
            data = zf.read(info.filename)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise InvalidLayerArchiveError(
                    f"レイヤー画像が PNG 形式ではありません: {info.filename}"
                )
    return len(layer_names)


def save_layer_archive(zip_bytes):
    """検証済みレイヤー ZIP を UUID ファイル名で保存し、相対保存先を返す。"""
    validate_layer_assets(zip_bytes)
    filename = f"{uuid.uuid4().hex}.zip"
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_bytes(zip_bytes)
    return filename
