"""主キー用の型。

設計上の型は BIGINT UNSIGNED（deploy.sql が正）。ただし SQLite では
BIGINT の主キーが自動採番されないため、SQLite のときだけ INTEGER に切り替える。
"""
from app.extensions import db

ID_TYPE = db.BigInteger().with_variant(db.Integer, "sqlite")
