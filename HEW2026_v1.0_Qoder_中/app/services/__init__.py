"""サービス層へのショートカット。ルートから services.xxx_service.func() 形式で呼ぶ。"""
from . import (  # noqa: F401
    artwork_service,
    auction_service,
    auth_service,
    event_service,
    image_service,
    layer_service,
    notification_service,
    point_service,
    tag_service,
)
