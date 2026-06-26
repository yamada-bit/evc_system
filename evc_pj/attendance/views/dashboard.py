"""
ダッシュボードビュー。

ログイン後のトップ画面。以下の4セクションを個別の try-except で組み立てて返す。
  1. 本日の打刻状況（未打刻/勤務中/休憩中/退勤済）
  2. 当月の勤務サマリー（出勤日数・実労働時間・残業時間・休憩時間）
  3. 当月の日次グラフ用データ（Chart.js 等での可視化を想定）
  4. 直近5件の自分の申請履歴
  （管理者 / staff のみ）未承認申請の件数バッジ
"""
import calendar
import json
import logging
from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from ..models import Attendance, DailyReport, WorkApplication
from ..utils.log_utils import log_user_id
from ._base import AttendanceLoginMixin, using_db

logger = logging.getLogger(__name__)


class DashboardView(AttendanceLoginMixin, TemplateView):
    """
    ログイン後のトップ画面（ダッシュボード）。

    【設計方針：セクションごとの個別 try-except】
    各セクション（本日の状況 / 月次サマリー / グラフ / 申請履歴）を
    1つの try-except にまとめず、個別にキャッチしている。
    これは「グラフ生成だけ失敗しても、サマリーは表示し続けたい」という
    意図的な設計で、1箇所の障害で画面全体が真っ白になることを防ぐ。
    エラーが起きたセクションは空データで代替表示される。
    """
    template_name = 'attendance/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        now_local = timezone.localtime(timezone.now())
        today = now_local.date()
        year, month = today.year, today.month

        logger.info(f"【アクセス】ダッシュボード閲覧 - ユーザー: {log_user_id(user.user_id)}")

        # 各セクションが失敗した場合のデフォルト値を事前に設定
        context['current_month_str'] = f"{year}年{month}月"
        context['attendance_today'] = None
        context['has_report'] = False
        context['status'] = 'NOT_YET'
        context['pending_count'] = 0

        # --- ① 本日の打刻状況取得 ---
        try:
            attendance = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date=today
            ).first()
            context['attendance_today'] = attendance
            context['has_report'] = DailyReport.objects.using(using_db).filter(
                user_id=user.user_id, report_date=today
            ).exists()

            if attendance:
                # 打刻状態のステートマシン: 出勤→勤務中→(休憩開始→休憩中→休憩終了→)退勤済
                if attendance.clock_in and not attendance.clock_out:
                    if attendance.break_start and not attendance.break_end:
                        context['status'] = 'BREAKING'  # 休憩中
                    else:
                        context['status'] = 'WORKING'   # 勤務中
                elif attendance.clock_in and attendance.clock_out:
                    context['status'] = 'LEFT'          # 退勤済

            # 管理者: 承認待ち件数をバッジ表示するためのカウント
            if user.is_staff or user.is_superuser:
                context['pending_count'] = WorkApplication.objects.using(using_db).filter(
                    status='PENDING'
                ).count()

        except Exception as e:
            logger.error(
                f"【読込エラー】ダッシュボード本日のデータ取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            messages.error(self.request, "本日のデータの読込中にエラーが発生しました。")

        _, num_days = calendar.monthrange(year, month)
        _base_qs = Attendance.objects.using(using_db).filter(
            user_id=user.user_id, work_date__year=year, work_date__month=month
        )

        # --- ② 当月サマリー集計（DB aggregate で 1 行取得）---
        # Python 側で全行ループして合計するのではなく、集計を DB に委ねることで
        # 転送データを最小化する（行数に関わらず常に 1 行のレスポンス）。
        try:
            agg = _base_qs.aggregate(
                work_days=Count('id', filter=Q(clock_in__isnull=False)),
                total_work=Sum('actual_work_hours'),
                total_overtime=Sum('overtime_hours'),
                total_break=Sum('break_hours'),
            )
            context['stats'] = {
                'work_days':      agg['work_days'] or 0,
                'work_hours':     round((agg['total_work']     or timedelta(0)).total_seconds() / 3600.0, 1),
                'overtime_hours': round((agg['total_overtime'] or timedelta(0)).total_seconds() / 3600.0, 1),
                'break_hours':    round((agg['total_break']    or timedelta(0)).total_seconds() / 3600.0, 1),
            }
        except Exception as e:
            logger.error(
                f"【集計エラー】当月サマリー計算失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            context['stats'] = {'work_days': 0, 'work_hours': 0.0, 'overtime_hours': 0.0, 'break_hours': 0.0}

        # --- ③ グラフ用データ生成（Chart.js 連携） ---
        # グラフには日別の時系列値が必要なため全行取得するが、
        # .only() でグラフに不要なカラム（打刻時刻・勤務区分等）の転送を省く。
        try:
            graph_rows = (
                _base_qs
                .only('work_date', 'actual_work_hours', 'overtime_hours')
                .order_by('work_date')
            )
            attendance_dict = {att.work_date: att for att in graph_rows}

            graph_dates: list[str] = []
            graph_work_hours: list[float] = []
            graph_overtime_hours: list[float] = []

            for day in range(1, num_days + 1):
                loop_date = date(year, month, day)
                att_data = attendance_dict.get(loop_date)
                graph_dates.append(loop_date.strftime('%m/%d'))
                graph_work_hours.append(
                    round(att_data.actual_work_hours.total_seconds() / 3600.0, 2)
                    if att_data and att_data.actual_work_hours else 0.0
                )
                graph_overtime_hours.append(
                    round(att_data.overtime_hours.total_seconds() / 3600.0, 2)
                    if att_data and att_data.overtime_hours else 0.0
                )

            context['graph_dates_json'] = json.dumps(graph_dates)
            context['graph_work_hours_json'] = json.dumps(graph_work_hours)
            context['graph_overtime_hours_json'] = json.dumps(graph_overtime_hours)

        except Exception as e:
            logger.error(
                f"【グラフエラー】グラフデータ生成失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            # グラフだけ失敗した場合でも他のセクションは表示を維持する（空配列で代替）
            context['graph_dates_json'] = json.dumps([])
            context['graph_work_hours_json'] = json.dumps([])
            context['graph_overtime_hours_json'] = json.dumps([])

        # --- ④ 直近の申請履歴取得 ---
        try:
            context['recent_applications'] = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id
            ).order_by('-id')[:5]
        except Exception as e:
            logger.error(
                f"【読込エラー】直近申請一覧の取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            context['recent_applications'] = []

        return context
