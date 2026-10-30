"""作品・競売のお気に入りを扱うサービス。"""

from ..extensions import db
from ..models import ArtworkFavorite, AuctionFavorite


def is_artwork_favorited(user_id, artwork_id):
    return (
        db.session.scalar(
            db.select(ArtworkFavorite.id).where(
                ArtworkFavorite.user_id == user_id,
                ArtworkFavorite.artwork_id == artwork_id,
            )
        )
        is not None
    )


def is_auction_favorited(user_id, auction_id):
    return (
        db.session.scalar(
            db.select(AuctionFavorite.id).where(
                AuctionFavorite.user_id == user_id,
                AuctionFavorite.auction_id == auction_id,
            )
        )
        is not None
    )


def add_artwork_favorite(user_id, artwork_id):
    """作品のお気に入りを登録する。重複登録はしない。"""
    if is_artwork_favorited(user_id, artwork_id):
        return False
    db.session.add(ArtworkFavorite(user_id=user_id, artwork_id=artwork_id))
    db.session.commit()
    return True


def remove_artwork_favorite(user_id, artwork_id):
    """作品のお気に入りを解除する。"""
    favorite = db.session.scalar(
        db.select(ArtworkFavorite).where(
            ArtworkFavorite.user_id == user_id,
            ArtworkFavorite.artwork_id == artwork_id,
        )
    )
    if favorite is None:
        return False
    db.session.delete(favorite)
    db.session.commit()
    return True


def add_auction_favorite(user_id, auction_id):
    """競売のお気に入りを登録する。重複登録はしない。"""
    if is_auction_favorited(user_id, auction_id):
        return False
    db.session.add(AuctionFavorite(user_id=user_id, auction_id=auction_id))
    db.session.commit()
    return True


def remove_auction_favorite(user_id, auction_id):
    """競売のお気に入りを解除する。"""
    favorite = db.session.scalar(
        db.select(AuctionFavorite).where(
            AuctionFavorite.user_id == user_id,
            AuctionFavorite.auction_id == auction_id,
        )
    )
    if favorite is None:
        return False
    db.session.delete(favorite)
    db.session.commit()
    return True


def list_artwork_favorites(user_id, limit=30):
    """作品のお気に入り一覧を登録が新しい順に取得する。"""
    return db.session.scalars(
        db.select(ArtworkFavorite)
        .where(ArtworkFavorite.user_id == user_id)
        .order_by(ArtworkFavorite.created_at.desc())
        .limit(limit)
    ).all()


def list_auction_favorites(user_id, limit=30):
    """競売のお気に入り一覧を登録が新しい順に取得する。"""
    return db.session.scalars(
        db.select(AuctionFavorite)
        .where(AuctionFavorite.user_id == user_id)
        .order_by(AuctionFavorite.created_at.desc())
        .limit(limit)
    ).all()
