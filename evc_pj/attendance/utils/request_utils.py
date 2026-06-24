import hashlib


def get_client_ip(
    request,
):
    """
    クライアントIP取得
    """

    x_forwarded_for = (
        request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )
    )

    if x_forwarded_for:

        return (
            x_forwarded_for
            .split(",")[0]
            .strip()
        )

    return request.META.get(
        "REMOTE_ADDR"
    )
# ハッシュ値を使ってログ出力(ユーザIDはハッシュ値で)
def get_hash(dat):
    if dat:
        hs = hashlib.sha256(dat.encode()).hexdigest()
    else:
        hs = 'None'
    return hs

def log_user_id(user_id) -> str:
    """ログ出力用にuser_id（メールアドレス）をハッシュ化する"""
    return get_hash(user_id)
