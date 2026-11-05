"""お気に入り一覧の取得ヘルパー。"""
from ..models.favorite import ArtworkFavorite, AuctionFavorite


def list_artwork_favorites(user):
    """本人の作品お気に入り一覧（登録日時の降順）。"""
    rows = (
        ArtworkFavorite.query.filter_by(user_id=user.id)
        .order_by(ArtworkFavorite.created_at.desc(), ArtworkFavorite.id.desc())
        .all()
    )
    return [row.artwork for row in rows if row.artwork]


def list_auction_favorites(user):
    """本人のオークションお気に入り一覧（登録日時の降順）。"""
    rows = (
        AuctionFavorite.query.filter_by(user_id=user.id)
        .order_by(AuctionFavorite.created_at.desc(), AuctionFavorite.id.desc())
        .all()
    )
    return [row.auction for row in rows if row.auction]
