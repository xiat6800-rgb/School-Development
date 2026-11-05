"""サービス層の例外。

ルート層でまとめて捕捉し、flash メッセージへ変換する。
"""


class ServiceError(Exception):
    """サービス層の業務エラー基底。

    引数で個別メッセージを渡すと、インスタンス側の ``message`` が
    上書きされる（クラス既定値より優先される）。
    """

    status_code = 400
    message = "処理できませんでした。"

    def __init__(self, message: str | None = None, status_code: int | None = None):
        super().__init__(message or type(self).message)
        if message:
            self.message = message
        if status_code is not None:
            self.status_code = status_code


class ValidationError(ServiceError):
    """入力値が不正。"""

    status_code = 400
    message = "入力内容を確認してください。"


class NotFoundError(ServiceError):
    """対象が見つからない。"""

    status_code = 404
    message = "対象が見つかりませんでした。"


class PermissionDeniedError(ServiceError):
    """権限がない。"""

    status_code = 403
    message = "この操作を行う権限がありません。"


class BusinessRuleError(ServiceError):
    """業務ルールにより拒否された。"""

    status_code = 400
    message = "この操作はできません。"


class InsufficientPointsError(BusinessRuleError):
    """ポイント残高が不足している。"""

    message = "ポイント残高が不足しています。"


class ConflictError(ServiceError):
    """同一処理が競合・重複している。"""

    status_code = 409
    message = "すでに処理されています。"
