from app.extensions import db
from app.utils import utcnow


class LiveStream(db.Model):
    __tablename__ = "live_streams"

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), unique=True, nullable=False
    )
    status = db.Column(db.String(20), nullable=False, default="ready", index=True)
    preview_path = db.Column(db.String(500), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    end_reason = db.Column(db.String(80), nullable=True)
    disconnected_at = db.Column(db.DateTime, nullable=True)
    last_heartbeat_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    artwork = db.relationship("Artwork", back_populates="stream")
    comments = db.relationship(
        "StreamComment", back_populates="stream", order_by="StreamComment.id"
    )

    @property
    def streamer(self):
        return self.artwork.artist


class StreamComment(db.Model):
    __tablename__ = "stream_comments"

    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey("live_streams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="visible", index=True)
    moderated_at = db.Column(db.DateTime, nullable=True)
    purge_body_at = db.Column(db.DateTime, nullable=True, index=True)
    purged_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    stream = db.relationship("LiveStream", back_populates="comments")
    user = db.relationship("User")
    audits = db.relationship("CommentAudit", back_populates="comment")


class CommentAudit(db.Model):
    __tablename__ = "comment_audits"

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(
        db.Integer, db.ForeignKey("stream_comments.id"), nullable=False
    )
    operator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(300), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    comment = db.relationship("StreamComment", back_populates="audits")
    operator = db.relationship("User")
