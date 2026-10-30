"""認証フォーム。入力検証はサーバー側で行う（要件定義書 5.1 / 7.3）。"""
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterForm(FlaskForm):
    username = StringField(
        "ユーザー名",
        validators=[
            DataRequired(message="ユーザー名を入力してください。"),
            Length(min=3, max=20, message="ユーザー名は3〜20文字です。"),
            Regexp(
                r"^[A-Za-z0-9_]+$",
                message="ユーザー名は半角英数字とアンダースコアのみ使用できます。",
            ),
        ],
    )
    email = StringField(
        "メールアドレス",
        validators=[
            DataRequired(message="メールアドレスを入力してください。"),
            Length(max=225),
            Regexp(EMAIL_PATTERN, message="メールアドレスの形式が正しくありません。"),
        ],
    )
    password = PasswordField(
        "パスワード",
        validators=[
            DataRequired(message="パスワードを入力してください。"),
            Length(min=8, max=128, message="パスワードは8文字以上にしてください。"),
        ],
    )
    confirm = PasswordField(
        "パスワード（確認）",
        validators=[
            DataRequired(message="確認用のパスワードを入力してください。"),
            EqualTo("password", message="パスワードが一致しません。"),
        ],
    )
    submit = SubmitField("登録して始める")


class LoginForm(FlaskForm):
    email = StringField(
        "メールアドレス",
        validators=[
            DataRequired(message="メールアドレスを入力してください。"),
            Length(max=225),
        ],
    )
    password = PasswordField(
        "パスワード", validators=[DataRequired(message="パスワードを入力してください。")]
    )
    submit = SubmitField("ログイン")
