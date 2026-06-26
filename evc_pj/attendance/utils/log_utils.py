import hashlib

from django.conf import settings


def get_client_ip(request) -> str:
    """
    クライアントIPを返す。ロギング専用。認証・認可には使用しないこと。

    settings.USE_X_FORWARDED_FOR=True の場合のみ X-Forwarded-For を参照する。
    この設定が無効（デフォルト）の場合は REMOTE_ADDR を使用するため、
    リバースプロキシを介さない環境でのヘッダー偽装を防ぐ。
    """
    if getattr(settings, 'USE_X_FORWARDED_FOR', False):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_user_id(user_id: str) -> str:
    """ログ出力用にuser_id（メールアドレス）をSHA256ハッシュ化する"""
    if not user_id:
        return "None"
    return hashlib.sha256(user_id.encode()).hexdigest()
