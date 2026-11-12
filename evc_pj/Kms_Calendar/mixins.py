from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin

# 勤怠カレンダー・外勤報告書の利用権限（users.EvcUser.Meta.permissions）
KMS_CALENDAR_PERM = 'users.use_kms_calendar'


class KmsCalendarPermissionMixin(PermissionRequiredMixin):
    """Kms_Calendar のクラスベースビュー共通の権限チェック。

    未ログイン  → ログイン画面へリダイレクト
    権限なし    → HTTP 403
    （raise_exception=False のとき AccessMixin.handle_no_permission が上記のとおり振り分ける）
    """
    permission_required = KMS_CALENDAR_PERM


def kms_calendar_permission_required(view_func):
    """Kms_Calendar の関数ビュー用デコレータ（未ログインはログイン画面、権限なしは 403）"""
    return login_required(
        permission_required(KMS_CALENDAR_PERM, raise_exception=True)(view_func)
    )
