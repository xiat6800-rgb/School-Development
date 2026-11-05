"""オークションモデル。1作品につき同時開催は最大1件（Ver0.5）。"""
from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Auction(db.Model):
    __tablename__ = "auctions"

    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    artwork_id = db.Column(
        db.BigInteger, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    start_price = db.Column(db.Integer, nullable=False)
    current_price = db.Column(db.Integer, nullable=False)
    # 最低落札価格は将来拡張用。Ver0.5 の判定では使わない
    reserve_price = db.Column(db.Integer, nullable=True)
    # active / ended / cancelled
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    start_time = db.Column(db.DateTime, nullable=False, default=utcnow)
    end_time = db.Column(db.DateTime, nullable=False)
    winner_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    winner_bid_id = db.Column(db.BigInteger, nullable=True)
    final_price = db.Column(db.Integer, nullable=True)
    # 現在の最高入札（差額消費・返却の判定に使う）
    highest_bid_id = db.Column(db.BigInteger, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    artwork = db.relationship("Artwork", backref="auctions")
    winner = db.relationship("User", foreign_keys=[winner_id])

    __table_args__ = (
        db.Index("idx_auctions_status_end_time", "status", "end_time"),
    )

    @property
    def seller(self):
        return self.artwork.artist

    @property
    def highest_bid(self):
        if not self.highest_bid_id:
            return None
        from .bid import Bid

        return db.session.get(Bid, self.highest_bid_id)

    @property
    def is_open(self):
        return self.status == "active" and utcnow() < self.end_time

    @property
    def is_awaiting_close(self):
        """終了日時を過ぎたが確定処理がまだの状態（結果確定待ち）。"""
        return self.status == "active" and utcnow() >= self.end_time
