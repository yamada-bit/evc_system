"""
クロスDB ユーザー情報取得ユーティリティ。

勤怠モデル（Attendance 等）は kmsdatabase にあり、User は default DB にある。
ORM の JOIN が使えないため、user_id のリストで User を一括取得して Python 側で
結合する「user_map パターン」を各ビューで共通利用できるよう関数化している。
"""
from django.contrib.auth import get_user_model

User = get_user_model()


def build_user_map(user_ids) -> dict:
    """
    user_id のコレクションから {user_id: User} の辞書を生成して返す。

    使い方:
        user_map = build_user_map(obj.user_id for obj in queryset)
        for obj in queryset:
            obj.assigned_user = user_map.get(obj.user_id)

    N+1 問題を防ぐため、ループの外で一度だけ呼び出すこと。
    """
    ids = set(user_ids)
    if not ids:
        return {}
    return {u.user_id: u for u in User.objects.filter(user_id__in=ids)}
