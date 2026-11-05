"""出品設定・作品情報編集のフォーム。"""
from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ArtworkInfoForm(FlaskForm):
    title = StringField(
        "タイトル",
        validators=[
            DataRequired(message="タイトルを入力してください。"),
            Length(max=200, message="タイトルは200文字以内です。"),
        ],
    )
    description = TextAreaField(
        "説明", validators=[Optional(), Length(max=2000, message="説明は2000文字以内です。")]
    )
    tags = SelectMultipleField("タグ", coerce=int, validators=[Optional()])
    submit = SubmitField("保存する")


class ListingForm(ArtworkInfoForm):
    start_price = IntegerField(
        "開始価格（pt）",
        validators=[
            DataRequired(message="開始価格を入力してください。"),
            NumberRange(min=0, max=100_000_000, message="開始価格は0以上で入力してください。"),
        ],
    )
    end_time = StringField(
        "終了日時（日本時間）",
        validators=[DataRequired(message="終了日時を入力してください。")],
    )
    submit = SubmitField("出品して公開する")
