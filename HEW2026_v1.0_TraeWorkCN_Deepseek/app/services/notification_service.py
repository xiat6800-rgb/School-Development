"""アプリ内通知とメール配信記録（要件定義書 5.9）。"""
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

from app.extensions import db
from app.models import Notification, NotificationDelivery
from app.utils import utcnow


def notify(user, notification_type, title, message, auction_id=None, bid_id=None):
    """アプリ内通知を保存し、メール配信を試みて結果を記録する。

    commit は呼び出し側のトランザクションに委ねる。
    """
    notification = Notification(
        user_id=user.id,
        notification_type=notification_type,
        title=title[:200],
        message=message,
        related_auction_id=auction_id,
        related_bid_id=bid_id,
    )
    db.session.add(notification)
    db.session.flush()

    delivery = NotificationDelivery(
        notification_id=notification.id,
        channel="email",
        recipient=user.email,
        delivery_status="pending",
    )
    db.session.add(delivery)
    db.session.flush()
    _try_send_email(notification, delivery)
    return notification


def _try_send_email(notification, delivery):
    config = current_app.config
    if not config.get("MAIL_SERVER"):
        # SMTP 未設定の開発環境では pending のまま残す（再送は将来対応）
        return

    message = EmailMessage()
    message["Subject"] = notification.title
    message["From"] = config["MAIL_DEFAULT_SENDER"]
    message["To"] = delivery.recipient
    message.set_content(notification.message)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(
            config["MAIL_SERVER"], config["MAIL_PORT"], timeout=5
        ) as server:
            if config["MAIL_USE_TLS"]:
                server.starttls(context=context)
            if config["MAIL_USERNAME"]:
                server.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
            server.send_message(message)
    except Exception as exc:  # 配信失敗は記録して処理を止めない
        delivery.delivery_status = "failed"
        delivery.error_message = str(exc)[:500]
    else:
        delivery.delivery_status = "sent"
        delivery.sent_at = utcnow()
