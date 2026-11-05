"""登録・ログイン・復旧コードの業務処理。

仕様決定事項1章：
- 登録・ログインは一意のユーザー名とパスワードを使う
- メールアドレスは一切使わない
- 復旧コードはハッシュで保存し、使用後に無効化する
"""

from __future__ import annotations

import secrets

from app.extensions import db
from app.models.user import User
from app.services.errors import ValidationError

# ユーザー名の制約（db設計 4.1 と同じ）
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
PASSWORD_MIN_LENGTH = 8


def generate_recovery_code() -> str:
    """登録・再発行用の復旧コードを生成する。"""
    groups = ["".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4)) for _ in range(3)]
    return "-".join(groups)


def validate_username(username: str) -> str:
    """ユーザー名の形式を検証して返す。"""
    normalized = (username or "").strip()
    if not normalized:
        raise ValidationError("ユーザー名を入力してください。")
    if not USERNAME_MIN_LENGTH <= len(normalized) <= USERNAME_MAX_LENGTH:
        raise ValidationError(
            f"ユーザー名は {USERNAME_MIN_LENGTH}～{USERNAME_MAX_LENGTH} 文字で入力してください。"
        )
    if not all(ch.isalnum() or ch in "_-" for ch in normalized):
        raise ValidationError("ユーザー名は英数字と _ - のみ使用できます。")
    return normalized


def validate_password(password: str) -> str:
    """パスワードの強度を確認し返す。"""
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise ValidationError(
            f"パスワードは {PASSWORD_MIN_LENGTH} 文字以上で入力してください。"
        )
    return password


def register_user(username: str, password: str) -> tuple[User, str]:
    """ユーザーを登録し、復旧コードを 1 回だけ返す。

    サーバーには復旧コードのハッシュだけを保存する。
    """
    normalized = validate_username(username)
    validate_password(password)

    if User.query.filter_by(username=normalized).first() is not None:
        raise ValidationError("そのユーザー名はすでに使用されています。")

    user = User(
        username=normalized,
        disp_name=f"user{User.query.count() + 1}",
        point_balance=0,
    )
    user.set_password(password)
    code = generate_recovery_code()
    user.set_recovery_code(code)
    db.session.add(user)
    db.session.flush()
    return user, code


def authenticate(username: str, password: str) -> User:
    """ユーザー名とパスワードを照合してユーザーを返す。"""
    normalized = (username or "").strip()
    user = User.query.filter_by(username=normalized).first()
    if user is None or not user.is_active:
        raise ValidationError("ユーザー名またはパスワードが正しくありません。")
    if not user.check_password(password):
        raise ValidationError("ユーザー名またはパスワードが正しくありません。")
    return user


def reset_password_with_code(username: str, code: str, new_password: str) -> User:
    """復旧コードでパスワードを再設定する。使用したコードは無効化する。"""
    normalized = (username or "").strip()
    validate_password(new_password)
    user = User.query.filter_by(username=normalized).first()
    if user is None:
        raise ValidationError("ユーザー名または復旧コードが正しくありません。")
    if not user.check_recovery_code((code or "").strip()):
        raise ValidationError("ユーザー名または復旧コードが正しくありません。")
    user.set_password(new_password)
    user.invalidate_recovery_code()
    return user


def regenerate_recovery_code(user: User, current_password: str) -> str:
    """現在のパスワードを確認して復旧コードを再発行する。

    旧コードは無効化され、新しいコードを 1 回だけ返す。
    """
    if not user.check_password(current_password or ""):
        raise ValidationError("現在のパスワードが正しくありません。")
    code = generate_recovery_code()
    user.set_recovery_code(code)
    return code
