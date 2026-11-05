"""認証まわりの補助処理。"""

import secrets


def generate_recovery_code():
    """登録・再発行用の復旧コードを生成する。

    画面に一度だけ表示し、保存はハッシュだけ行う。
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = []
    for _ in range(4):
        groups.append("".join(secrets.choice(alphabet) for _ in range(4)))
    return "-".join(groups)
