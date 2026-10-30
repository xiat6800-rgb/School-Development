"""サービスの例外定義。ルート側で捕捉して画面にメッセージを出す。"""


class DomainError(Exception):
    """業務ルール違反を表す基底例外。"""


class ValidationError(DomainError):
    """入力値が条件を満たさない。"""


class InsufficientPointsError(DomainError):
    """ポイント残高が不足している。"""


class BidError(DomainError):
    """入札を受け付けられない。"""


class PriceChangedError(BidError):
    """確認後に現在価格が変わった。再確認が必要。"""


class EventClosedError(DomainError):
    """イベント終了後で操作を受け付けられない。"""


class SaveError(DomainError):
    """正式保存を受け付けられない。"""


class InvalidImageError(DomainError):
    """画像の形式・容量・寸法が条件を満たさない。"""
