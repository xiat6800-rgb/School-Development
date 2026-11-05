"""認証サービス。復旧コードの生成・ハッシュ保存を担当する。"""
import secrets


def generate_recovery_code():
    """登録・再発行用の復旧コードを生成する。保存はハッシュのみ。"""
    return secrets.token_hex(8).upper()


def issue_recovery_code(user):
    """新しい復旧コードを発行し、旧コードを無効化して平文を一度だけ返す。"""
    code = generate_recovery_code()
    user.set_recovery_code(code)
    return code
