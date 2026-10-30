"""PNG の検証と保存。

- 形式は PNG のみ（マジックバイトと IHDR を確認）
- 受け取る前に base64 文字列長でも上限を確認し、デコード後のバイト数も検証する
- ファイル名は UUID をサーバー側で決める（ユーザー入力を使わない）
- 保存先は static の外。配信は権限チェック付きルート経由に限る
"""
import base64
import binascii
import os
import struct
import uuid

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ImageValidationError(ValueError):
    pass


def save_png_data_url(data_url, upload_folder, max_bytes, max_width, max_height):
    """data URL 形式の PNG を検証して保存し、保存ファイル名を返す。"""
    if not isinstance(data_url, str) or not data_url.startswith("data:image/png;base64,"):
        raise ImageValidationError("PNG 形式の画像データを受け取れませんでした。")

    encoded = data_url.split(",", 1)[1]
    # base64 は元データの約 4/3。デコード前に明らかな超過を弾く。
    if len(encoded) > (max_bytes // 3 + 1) * 4 + 16:
        raise ImageValidationError("画像サイズが上限を超えています。")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ImageValidationError("画像データを読み取れませんでした。")

    if len(raw) > max_bytes:
        raise ImageValidationError("画像サイズが上限を超えています。")
    if not raw.startswith(PNG_SIGNATURE):
        raise ImageValidationError("PNG 形式ではありません。")
    if len(raw) < 33 or raw[12:16] != b"IHDR":
        raise ImageValidationError("PNG のヘッダーが不正です。")

    width, height = struct.unpack(">II", raw[16:24])
    if width <= 0 or height <= 0:
        raise ImageValidationError("画像の寸法が不正です。")
    if width > max_width or height > max_height:
        raise ImageValidationError(
            f"画像の寸法は {max_width}×{max_height} 以下にしてください。"
        )

    os.makedirs(upload_folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(upload_folder, filename)
    with open(path, "wb") as handle:
        handle.write(raw)
    return filename
