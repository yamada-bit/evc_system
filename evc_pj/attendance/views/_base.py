"""
views パッケージ内の全モジュールが共有するミックスイン・定数・ユーティリティ。

【このファイルの用途】
- 外部（urls.py 等）からは attendance.views（__init__.py）経由でアクセスすること。
- views パッケージ内の各モジュールはここから必要なものだけをインポートする。

【含まれるもの】
- AttendanceLoginMixin  : 未ログイン時に勤怠専用ログイン画面へリダイレクト
- AttendanceAccessMixin : 権限不足時に専用403ページを表示
- MonthLockMixin        : 月報提出済みの場合に操作をブロックする Mixin
- using_db              : マルチDB環境でのDBエイリアス（全ORMクエリに必須）
- LEAVE_COST            : 有給系申請種別ごとの消費日数マップ
- get_fiscal_year()     : 日本の年度（4月始まり）計算
- get_pending_leave_days(): 承認待ち有給申請の合計消費日数
- LOCKED_STATUSES       : 月報ロック対象ステータスのセット（提出済み・確定済み）
- is_month_locked()     : 月報が提出済み/確定済みかどうかを判定（request を渡すとリクエストスコープでキャッシュ）
- format_duration()     : timedelta → 'H:MM' 文字列（fallback 引数で画面用/CSV用を切替）
"""
import logging
import re
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import DatabaseError
from django.db.models import Count
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from ..models import MonthlyReport, WorkApplication

logger = logging.getLogger(__name__)

# target_month_str の正規表現（YYYY-MM、月は 01〜12）
_MONTH_STR_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

# 月報ロック対象ステータス。このセットに含まれるステータスの月は打刻・日報・申請を操作不可にする。
# ⚠️ MonthlyReport のステータス追加時は必ずここを更新すること。
LOCKED_STATUSES: frozenset[str] = frozenset({'SUBMITTED', 'APPROVED'})


class AttendanceLoginMixin(LoginRequiredMixin):
    """
    未ログイン時に勤怠システム専用ログイン画面へリダイレクトする Mixin。

    Django 標準の LoginRequiredMixin はデフォルトで settings.LOGIN_URL へ
    リダイレクトするが、勤怠システムは独自のログイン画面を持つため
    login_url を上書きしている。
    """
    login_url = reverse_lazy('attendance:alogin')


class AttendanceAccessMixin:
    """
    権限不足時（UserPassesTestMixin.test_func が False を返した場合）に
    Django デフォルトのログインリダイレクトではなく、専用 403 画面を表示する Mixin。

    【MRO に関する注意】
    AttendanceLoginMixin と組み合わせる場合はクラス定義の順序が重要。
    正しい順序: class FooView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View)
    AttendanceAccessMixin を先に置くことで handle_no_permission が正しく呼ばれる。
    """
    login_url = reverse_lazy('attendance:alogin')

    def handle_no_permission(self):
        return render(self.request, "attendance/403.html", status=403)


# マルチDB環境でのDBエイリアス。settings.ATTENDANCE_DB で一元管理。
using_db: str = settings.ATTENDANCE_DB

# 有給系申請の消費日数マップ（代休・残業・打刻修正は有給残日数に影響しないため含まない）。
# ⚠️ 新しい有給種別を追加する場合は、このマップへの追加と WorkApplication.APPLY_TYPE_CHOICES の
# 両方を更新すること。片方だけ更新すると申請時の残日数チェックが狂う。
LEAVE_COST: dict[str, Decimal] = {
    'PAID_LEAVE': Decimal('1.0'),   # 全休: 1日消費
    'AM_LEAVE':   Decimal('0.5'),   # 午前半休: 0.5日消費
    'PM_LEAVE':   Decimal('0.5'),   # 午後半休: 0.5日消費
}


class MonthLockMixin:
    """
    月次ロック強制 Mixin。POST ハンドラ内で month_lock_response() を呼び、
    None 以外が返ったら即 return すること。

    使い方:
        class MyView(MonthLockMixin, AttendanceLoginMixin, View):
            month_lock_redirect = 'attendance:my_url'

            def post(self, request, ...):
                if resp := self.month_lock_response(request, month_str):
                    return resp

    【🔒 月次ロック呼び出し箇所】
    このMixinを使用しているビューを変更する場合は以下4箇所を確認すること:
      - punch.py       AttendancePunchView.post()
      - report.py      DailyReportSubmitView.post()
      - report.py      DailyReportDeleteView.post()
      - application.py WorkApplicationView.post()
    """
    month_lock_redirect: str = ''

    def month_lock_response(self, request, month_str: str):
        if not is_month_locked(request.user.user_id, month_str, request=request):
            return None
        messages.error(
            request,
            f"【操作拒否】{month_str}分の月報は既に提出または確定されているため、操作できません。",
        )
        return redirect(self.month_lock_redirect)


def get_fiscal_year(d: date | None = None) -> int:
    """
    日本の年度（4月始まり）を返す。
    例: 2026年3月15日 → 2025年度, 2026年4月1日 → 2026年度
    d が None の場合はシステム日付（ローカル時刻）を使用する。
    """
    if d is None:
        d = timezone.localtime(timezone.now()).date()
    return d.year if d.month >= 4 else d.year - 1


def get_pending_leave_days(user_id: str, fiscal_year: int) -> Decimal:
    """
    指定ユーザー・年度の承認待ち（PENDING）有給申請の合計消費日数を返す。

    【用途】
    WorkApplicationView の申請時に「残日数 - 承認待ち日数 >= 申請日数」を
    チェックするための値として使用する。これにより、承認待ちの申請がある
    状態でさらに申請しても「残日数不足」として弾ける（二重申請防止）。

    【承認済みは含まない理由】
    承認済み（APPROVED）の申請は既に LeaveBalance.used_days に反映済みのため、
    ここで再カウントすると二重減算になる。
    """
    fy_start = date(fiscal_year, 4, 1)
    fy_end   = date(fiscal_year + 1, 3, 31)
    # DB 側で apply_type ごとに件数を集約（最大3行）してから Python 側で合計する。
    # 全件フェッチ→Python 集計より大幅に効率的。
    rows = (
        WorkApplication.objects.using(using_db)
        .filter(
            user_id=user_id,
            status='PENDING',
            apply_type__in=LEAVE_COST.keys(),
            target_date__gte=fy_start,
            target_date__lte=fy_end,
        )
        .values('apply_type')
        .annotate(cnt=Count('id'))
    )
    return sum((LEAVE_COST[row['apply_type']] * row['cnt'] for row in rows), Decimal('0'))


def is_month_locked(user_id: str, target_month_str: str, *, request=None) -> bool:
    """
    指定ユーザー・年月の月報が「ロック状態」かどうかを返す。

    SUBMITTED（提出済み）または APPROVED（確定済み）の場合に True を返す。
    True のとき、その月の打刻・日報・申請は一切操作できない。

    【request キャッシュ】
    request を渡すと、同一リクエスト内で同じ (user_id, month) の再チェック時に
    DB クエリをスキップしてキャッシュ値を返す。キャッシュは request オブジェクトに
    属性として保持するためリクエストスコープに閉じており、プロセス間の汚染はない。
    MonthLockMixin.month_lock_response() は自動的に request を渡す。

    【呼び出し箇所（🔒 月次ロック）】
    このチェックを変更・廃止する場合は以下の4箇所すべてに影響する:
      - punch.py       AttendancePunchView.post()
      - report.py      DailyReportSubmitView.post() / get()
      - report.py      DailyReportDeleteView.post()
      - application.py WorkApplicationView.post()
    """
    if not target_month_str or not _MONTH_STR_RE.match(target_month_str):
        logger.error(
            "is_month_locked: 不正な target_month_str=%r (user_id=%r)。"
            "データ保護のためロック扱いで返します。",
            target_month_str, user_id,
        )
        return True

    _CACHE_ATTR = '_attendance_month_lock_cache'
    if request is not None:
        cache: dict = getattr(request, _CACHE_ATTR, None)
        if cache is None:
            cache = {}
            setattr(request, _CACHE_ATTR, cache)
        cache_key = (user_id, target_month_str)
        if cache_key in cache:
            return cache[cache_key]

    try:
        result = MonthlyReport.objects.using(using_db).filter(
            user_id=user_id,
            target_month=target_month_str,
            status__in=LOCKED_STATUSES,
            delete_flg=0,
        ).exists()
    except DatabaseError:
        logger.error(
            "is_month_locked: DB例外が発生しました (user_id=%r, target_month_str=%r)。"
            "データ保護のためロック扱いで返します。",
            user_id, target_month_str,
            exc_info=True,
        )
        return True

    if request is not None:
        cache[cache_key] = result  # type: ignore[possibly-undefined]
    return result


def format_duration(td, fallback: str = "-") -> str:
    """
    timedelta を 'H:MM' 形式の文字列に変換する。
    None や timedelta 以外の値が渡された場合は fallback を返す。

    - 画面表示用（デフォルト）: format_duration(td)          → None 時に '-'
    - CSV 出力用:               format_duration(td, "0:00")   → None 時に '0:00'
    """
    if td is None or not hasattr(td, 'total_seconds'):
        return fallback
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}:{minutes:02d}"


# Excel / LibreOffice が数式として解釈する先頭文字。
# これらで始まるセル値の先頭に ' を付加して文字列扱いにする（数式インジェクション対策）。
_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def csv_safe(value: str) -> str:
    """CSV セルの数式インジェクションを防ぐサニタイザー。ユーザー由来の全セルに適用すること。"""
    if value and value[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value


def format_td_for_csv(td) -> str:
    """CSV出力用のtimedelta変換。None時は '0:00' を返す。format_duration(td, '0:00') のショートハンド。"""
    return format_duration(td, "0:00")
