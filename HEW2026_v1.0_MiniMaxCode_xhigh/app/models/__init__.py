"""モデルのまとめて読み込み。

``create_app`` から import され、``db.create_all()`` や
Flask-Migrate が全テーブルを把握できるようにする。
"""

from app.models.artwork import Artwork, DrawingSession
from app.models.auction import Auction
from app.models.auto_bid import AutoBidSetting
from app.models.bid import Bid
from app.models.cancellation import AuctionCancellation
from app.models.favorite import ArtworkFavorite, AuctionFavorite
from app.models.notification import Notification
from app.models.tag import ArtworkTag, Tag
from app.models.user import User
from app.models.wallet import BonusGrant, WalletTransaction

__all__ = [
    "Artwork",
    "ArtworkFavorite",
    "ArtworkTag",
    "Auction",
    "AuctionCancellation",
    "AuctionFavorite",
    "AutoBidSetting",
    "Bid",
    "BonusGrant",
    "DrawingSession",
    "Notification",
    "Tag",
    "User",
    "WalletTransaction",
]
