# attendance/views.py
"""
=====================================================================
勤怠管理システム（attendance アプリ） ビュー層
=====================================================================

【このファイルの役割】
社員の日々の打刻、日報、各種就業申請（残業・有休・打刻修正等）、
月次締め（月報提出・承認）、管理者によるCSVエクスポート・承認処理を
すべて扱うビュー集約ファイル。

【関連テーブルとその役割（models.py参照）】
- Attendance（tr_attendance）
    1人1日1レコード。出退勤・休憩の打刻実績と、そこから自動計算される
    実労働時間/残業時間/休憩時間を保持する「実績の正」のテーブル。
    保存時（save()）に打刻データから各種時間を自動計算するロジックが
    組み込まれている点に注意（詳細はmodels.py側のdocstringを参照）。
- DailyReport（tr_daily_report）
    1人1日1レコード。その日の業務内容・勤務場所・所感を記録する日報。
    Attendanceとは1対1（OneToOne）で緩く紐づくが、Attendanceが
    無くても日報単体での登録が可能（attendance=Nullを許容）。
- WorkApplication（tr_application）
    残業・有休（全休/午前半休/午後半休）・代休・打刻修正の5種類の
    申請を扱う。1人・1日・1申請種別につき1レコードまで（DB制約あり）。
    承認されるとAttendanceの該当レコードが更新される「申請→反映」の
    ワークフローを構成する。
- MonthlyReport（tr_monthly_report）
    1人1ヶ月1レコード。月報提出（status='SUBMITTED'）すると、
    対象月のAttendance/DailyReport/WorkApplicationへの新規登録・編集・
    削除がビュー側で一律ロックされる「月次締め」を担う。
    上長が承認（status='APPROVED'）すると確定。差し戻し時は
    'REJECTED'に戻り、再度ロック解除される。

【全体のデータフロー（社員側）】
    1. AttendancePunchView で日々打刻（出勤/退勤/休憩開始/休憩終了）
       → Attendance.save() が実労働時間・残業時間を自動計算
    2. DailyReportSubmitView で日報を都度登録・編集
    3. 打刻ミスや有休取得の必要があれば WorkApplicationView から申請
       → 申請時点ではAttendanceは更新されず、ステータスPENDINGのまま
    4. 月末、MonthlyReportView から月報を提出（status='SUBMITTED'）
       → 以降、対象月の打刻・日報・新規申請は一切ブロックされる

【全体のデータフロー（管理者/承認者側）】
    1. ApplicationApprovalView で申請一覧・月報提出一覧を確認
    2. 申請を承認/却下 → 承認時にAttendanceへ自動反映（後述の注意点参照）
    3. 月報を確定（承認）/差し戻し
    4. AdminReportListView / AdminReportCsvDownloadView / 
       ExportAttendanceCSVView で日報・勤怠データを閲覧/CSV出力

【⚠️ 引き継ぎ時に特に注意すべきポイント】
1. ロックの仕組み（月報提出済みなら操作不可）は、各ビューの先頭付近で
   `MonthlyReport...status__in=['SUBMITTED', 'APPROVED']` のexists()
   チェックとして個別に実装されている（共通化されていない）。
   ロック判定ロジックを変更する場合は、AttendancePunchView /
   DailyReportSubmitView / DailyReportDeleteView / WorkApplicationView の4箇所すべてを
   同時に修正する必要がある。各箇所には 🔒【月次ロック N/4】のコメントを付けている。

2. 申請承認時のAttendance更新は、申請種別によって「通常のsave()経由」
   と「QuerySet.update()経由（save()をバイパス）」を使い分けている。
   - CORRECTION（打刻修正）: 打刻データ自体を書き換えるため、
     Attendance.save()の自動計算ロジックに乗せる必要があり、
     通常の `attendance.save()` を使う。
   - OVERTIME（残業）/ PAID_LEAVE・COMP_LEAVE（有休・代休）:
     打刻データに基づかない「申請された値」をそのまま確定させたいため、
     save()の自動計算で上書きされないよう `QuerySet.update()` を使う。
   このルールを忘れて安易に `attendance.save()` に統一してしまうと、
   残業申請・有休申請の承認結果が打刻ベースの再計算で消えてしまう
   （実際に過去に発生したバグ。詳細はmodels.py側コメント参照）。

3. DBは複数DB構成（マルチDB）。`using_db` 変数（settings経由で
   'kmsdatabase' 等のDBエイリアスを取得）を、ORMクエリには必ず
   `.objects.using(using_db)` の形で明示的に付与する必要がある。
   付け忘れるとdefault DBに対してクエリが飛び、データが見つからない
   /書き込まれない、といった気づきにくいバグになるため要注意。

4. ユーザーモデル（User）はAttendance等とは別データベースにあり、
   外部キーは `db_constraint=False` でDBレベルの制約を外している。
   そのため `att.user.user_name` のようにリレーション経由でアクセス
   すると、別DBへの追加クエリが都度発生する（N+1問題）。
   一覧画面では原則、`user_id` のリストを集めて
   `User.objects.filter(user_id__in=...)` で一括取得し、
   Python側の辞書（user_map）で引く方式に統一している。

5. 「未知のaction_type/punch_type/apply_typeを必ずハンドリングして
   redirectを返す」設計を徹底している。Djangoのビューはレスポンスを
   返さない分岐があると500エラーになるため、新しい申請種別や打刻種別を
   追加する際は、対応するハンドリング漏れがないか必ず確認すること。
=====================================================================
"""
import calendar
import csv
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import jpholiday  # 祝日判定ライブラリ
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.db import transaction, IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from attendance.forms import AttendanceLoginForm
from attendance.utils.request_utils import get_client_ip, get_hash, log_user_id

from .models import Attendance, DailyReport, LeaveBalance, MonthlyReport, WorkApplication

User = get_user_model()


class AttendanceLoginMixin(LoginRequiredMixin):
    login_url = reverse_lazy('attendance:alogin')


class AttendanceAccessMixin:
    """attendanceアプリ独自の403ページを表示するMixin"""
    login_url = reverse_lazy('attendance:alogin')

    def handle_no_permission(self):
        return render(self.request, "attendance/403.html", status=403)


# DBエイリアスはハードコードを避け、settings.py側で一元管理する想定
# settings.py に ATTENDANCE_DB_ALIAS = 'kmsdatabase' を定義し、未設定時は 'kmsdatabase' をデフォルトとする
# using_db = getattr(settings, 'ATTENDANCE_DB_ALIAS', 'kmsdatabase')
using_db = 'kmsdatabase'

logger = logging.getLogger(__name__)

# 有給系申請の消費日数マップ（代休・残業・打刻修正は有給残日数に影響しない）
LEAVE_COST: dict[str, Decimal] = {
    'PAID_LEAVE': Decimal('1.0'),
    'AM_LEAVE':   Decimal('0.5'),
    'PM_LEAVE':   Decimal('0.5'),
}


def get_fiscal_year(d: date | None = None) -> int:
    """日本の年度を返す（4月始まり）。例: 2026年4月〜2027年3月 → 2026"""
    if d is None:
        d = timezone.localtime(timezone.now()).date()
    return d.year if d.month >= 4 else d.year - 1


def get_pending_leave_days(user_id: str, fiscal_year: int) -> Decimal:
    """承認待ち有給申請の消費日数合計を返す（残日数チェック時の二重申請防止用）"""
    fy_start = date(fiscal_year, 4, 1)
    fy_end   = date(fiscal_year + 1, 3, 31)
    pending = WorkApplication.objects.using(using_db).filter(
        user_id=user_id,
        status='PENDING',
        apply_type__in=LEAVE_COST.keys(),
        target_date__gte=fy_start,
        target_date__lte=fy_end,
    )
    return sum((LEAVE_COST.get(a.apply_type, Decimal('0')) for a in pending), Decimal('0'))


def format_duration(td):
    """
    timedeltaを 'H:MM' 形式の文字列に変換する共通ヘルパー。
    Noneや異常値の場合は '-' を返す（画面表示用）。
    """
    if not td or not hasattr(td, 'total_seconds'):
        return "-"
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}:{minutes:02d}"


def format_td_for_csv(td):
    """
    CSV出力用のtimedelta→'H:MM'文字列変換。
    Noneや異常値の場合は '0:00' を返す（CSVの列が空にならないように）。
    """
    if not td or not hasattr(td, 'total_seconds'):
        return "0:00"
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = int((total_seconds % 3600) // 60)
    return f"{hours}:{minutes:02d}"

# =====================================================================
# 1. 認証（ログイン・ログアウト）ブロック
# =====================================================================
class AttendanceLoginView(LoginView):
    """
    ログイン画面。

    【役割】
    勤怠システム専用のログインフォームを表示し、認証成功時は
    打刻画面（attendance_punch）へリダイレクトする。

    【セキュリティ上の注意】
    - ログイン成功時に `session.cycle_key()` でセッションIDを再生成し、
      セッション固定攻撃（Session Fixation）を防止している。
      この処理を消すとセキュリティ上の脆弱性になるため削除しないこと。
    - ログイン試行のユーザーIDはハッシュ化してログ出力している
      （個人情報保護のため、生のIDをログに残さない設計）。
    """
    template_name = "attendance/attendance_login.html"
    form_class = AttendanceLoginForm

    def get_success_url(self):
        return reverse_lazy('attendance:attendance_punch')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_name'] = 'alogin'
        return context

    def form_valid(self, form):
        # セッション固定攻撃対策のため、ログイン成功時にセッションキーを再生成
        self.request.session.cycle_key()

        user_id = form.cleaned_data.get('username')
        user_id_hash = get_hash(user_id)  # 個人情報保護のためのハッシュ化

        logger.info(
            f"[AUTH][LOGIN_SUCCESS] IP: {get_client_ip(self.request)} "
            f"ユーザー(HASH): {user_id_hash}"
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        err = form.errors.as_text()
        logger.warning(
            f"[AUTH][LOGIN_FAILED] IP: {get_client_ip(self.request)} "
            f"原因: {err.strip()}"
        )
        return super().form_invalid(form)

# =====================================================================
# 2. メインダッシュボード ブロック
# =====================================================================
class DashboardView(AttendanceLoginMixin, TemplateView):
    """
    ログイン後のトップ画面（ダッシュボード）。

    【表示内容】
    - 本日の打刻状況（未打刻/勤務中/休憩中/退勤済）
    - 当月の勤務日数・実労働時間・残業時間・休憩時間のサマリー
    - 当月の日次グラフ用データ（実労働時間/残業時間の推移、Chart.js等で利用想定）
    - 直近5件の自分の申請履歴
    - （管理者/staffのみ）未承認申請の件数バッジ

    【設計上の注意】
    各セクション（本日の状況/月次サマリー/グラフ/申請履歴）は、
    1つのtry-exceptブロックにまとめず個別にtry-exceptしている。
    これは「グラフ生成だけ失敗しても、他のサマリー情報は表示し続けたい」
    という意図的な設計。1箇所の障害で画面全体が真っ白になるのを防ぐ。
    """
    template_name = 'attendance/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        now_local = timezone.localtime(timezone.now())
        today = now_local.date()
        year, month = today.year, today.month

        logger.info(f"【アクセス】ダッシュボード閲覧 - ユーザー: {log_user_id(user.user_id)}")

        context['current_month_str'] = f"{year}年{month}月"
        context['attendance_today'] = None
        context['has_report'] = False
        context['status'] = 'NOT_YET'
        context['pending_count'] = 0

        # --- 本日の打刻状況取得 ---
        try:
            # マルチDBへの明示的な接続
            attendance = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date=today, delete_flg=0
            ).first()
            context['attendance_today'] = attendance
            context['has_report'] = DailyReport.objects.using(using_db).filter(
                user_id=user.user_id, report_date=today, delete_flg=0
            ).exists()

            if attendance:
                if attendance.clock_in and not attendance.clock_out:
                    if attendance.break_start and not attendance.break_end:
                        context['status'] = 'BREAKING'  # 休憩中
                    else:
                        context['status'] = 'WORKING'   # 勤務中
                elif attendance.clock_in and attendance.clock_out:
                    context['status'] = 'LEFT'          # 退勤済
            # 管理者：承認待ち件数のカウント通知
            if user.is_staff or user.is_superuser:
                context['pending_count'] = WorkApplication.objects.using(using_db).filter(
                    status='PENDING', delete_flg=0
                ).count()

        except Exception as e:
            logger.error(
                f"【読込エラー】ダッシュボード本日のデータ取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            messages.error(self.request, "本日のデータの読込中にエラーが発生しました。")

        # --- 当月サマリー集計 ---
        try:
            month_attendances_all = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date__year=year, work_date__month=month, delete_flg=0
            )

            total_work_seconds = 0
            total_overtime_seconds = 0
            total_break_seconds = 0
            work_days_count = 0

            for att in month_attendances_all:
                if att.clock_in:
                    work_days_count += 1
                if att.actual_work_hours:
                    total_work_seconds += att.actual_work_hours.total_seconds()
                if att.overtime_hours:
                    total_overtime_seconds += att.overtime_hours.total_seconds()
                if att.break_hours:
                    total_break_seconds += att.break_hours.total_seconds()

            context['stats'] = {
                'work_days': work_days_count,
                'work_hours': round(total_work_seconds / 3600.0, 1),
                'overtime_hours': round(total_overtime_seconds / 3600.0, 1),
                'break_hours': round(total_break_seconds / 3600.0, 1),
            }
        except Exception as e:
            logger.error(
                f"【集計エラー】当月サマリー計算失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            context['stats'] = {'work_days': 0, 'work_hours': 0.0, 'overtime_hours': 0.0, 'break_hours': 0.0}

        # --- グラフ用データ生成 (Chart.js連携) ---
        try:
            _, num_days = calendar.monthrange(year, month)
            month_attendances = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date__year=year, work_date__month=month, delete_flg=0
            ).order_by('work_date')

            attendance_dict = {att.work_date: att for att in month_attendances}

            graph_dates = []
            graph_work_hours = []
            graph_overtime_hours = []

            for day in range(1, num_days + 1):
                loop_date = date(year, month, day)
                att_data = attendance_dict.get(loop_date)

                graph_dates.append(loop_date.strftime('%m/%d'))

                if att_data and att_data.actual_work_hours:
                    graph_work_hours.append(round(att_data.actual_work_hours.total_seconds() / 3600.0, 2))
                else:
                    graph_work_hours.append(0.0)

                if att_data and att_data.overtime_hours:
                    graph_overtime_hours.append(round(att_data.overtime_hours.total_seconds() / 3600.0, 2))
                else:
                    graph_overtime_hours.append(0.0)

            context['graph_dates_json'] = json.dumps(graph_dates)
            context['graph_work_hours_json'] = json.dumps(graph_work_hours)
            context['graph_overtime_hours_json'] = json.dumps(graph_overtime_hours)

        except Exception as e:
            logger.error(
                f"【グラフエラー】グラフデータ生成失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            context['graph_dates_json'] = json.dumps([])
            context['graph_work_hours_json'] = json.dumps([])
            context['graph_overtime_hours_json'] = json.dumps([])

        try:
            # --- ④ 直近の申請データの取得 ---
            context['recent_applications'] = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id, delete_flg=0
            ).order_by('-id')[:5]
        except Exception as e:
            logger.error(
                f"【読込エラー】直近申請一覧の取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            context['recent_applications'] = []

        return context

# =====================================================================
# 3. 日常の打刻アクション ブロック
# =====================================================================
class AttendancePunchView(AttendanceLoginMixin, View):
    """
    打刻画面（出勤/退勤/休憩開始/休憩終了）。

    【業務ルール】
    - 1日1レコード。打刻順序は 出勤 → (休憩開始 → 休憩終了)* → 退勤 の
      順序を守る必要があり、順序を無視した打刻（例: 出勤前に退勤）は
      POST処理内のガード条件で弾かれる。
    - 当月の月報が提出済み（SUBMITTED）または確定済み（APPROVED）の
      場合、当日の打刻は一切できない（給与計算の基礎データを
      確定後に変更させないための業務ルール）。

    【実労働時間・残業時間の計算タイミング】
    打刻保存（attendance.save()）のたびに、Attendanceモデルのsave()
    メソッド内で実労働時間・残業時間が自動再計算される
    （本ビュー側では計算ロジックを持たない。計算ロジックの修正は
    models.py の Attendance.save() を参照）。
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        today = timezone.localtime(timezone.now()).date()
        try:
            attendance = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date=today, delete_flg=0
            ).first()
        except Exception as e:
            logger.error(
                f"【読込エラー】打刻画面表示用データ取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            messages.error(request, "本日の打刻データの取得に失敗しました。")
            attendance = None
        return render(request, 'attendance/punch.html', {'attendance': attendance})
    # 💡 データの多重送信や瞬時の競合から計算ロジックを守るため、デコレータで関数全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        user = request.user
        now_datetime = timezone.localtime(timezone.now())
        today = now_datetime.date()
        punch_type = request.POST.get('punch_type')
        target_month_str = today.strftime('%Y-%m')

        # 月報が確定/提出済みの場合は打刻自体をブロック
        # 🔒 【月次ロック 1/4】AttendancePunchView — 他の3箇所と必ず同時に変更すること
        # → DailyReportSubmitView(views.py:601), DailyReportDeleteView(views.py:688), WorkApplicationView(views.py:1190)
        if MonthlyReport.objects.using(using_db).filter(
            user_id=user.user_id, target_month=target_month_str, status__in=['SUBMITTED', 'APPROVED'], delete_flg=0
        ).exists():
            logger.warning(
                f"[PUNCH][BLOCKED] 提出済月報への打刻試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            messages.error(
                request,
                f"【操作拒否】{target_month_str}分の月報は既に提出または確定されているため、打刻できません。"
            )
            return redirect('attendance:attendance_punch')

        # 未知のpunch_typeは早期リターン（不正パラメータ対策）
        valid_punch_types = {'clock_in', 'clock_out', 'break_start', 'break_end'}
        if punch_type not in valid_punch_types:
            logger.warning(f"【不正パラメータ】未知の打刻種別: {punch_type}（ユーザー: {log_user_id(user.user_id)}）")
            messages.error(request, "不正なリクエストです。")
            return redirect('attendance:attendance_punch')

        logger.info(f"【打刻リクエスト】ユーザー: {log_user_id(user.user_id)}, アクション: {punch_type}")

        try:
            # 連打・競合防止のため select_for_update を完全紐付け
            attendance = Attendance.objects.using(using_db).select_for_update().filter(
                user_id=user.user_id, work_date=today, delete_flg=0
            ).first()
            if not attendance:
                creator_name = user.user_name or user.user_id
                attendance = Attendance(user_id=user.user_id, work_date=today, create_user=creator_name)

            success_message = ""

            if punch_type == 'clock_in':
                if attendance.clock_in:
                    messages.warning(request, "既に出勤打刻が記録されています。")
                    return redirect('attendance:attendance_punch')
                attendance.clock_in = now_datetime
                success_message = "出勤を記録しました。"

            elif punch_type == 'clock_out':
                if not attendance.clock_in:
                    messages.warning(request, "出勤打刻が確認できません。")
                    return redirect('attendance:attendance_punch')
                if attendance.clock_out:
                    messages.warning(request, "既に退勤打刻が記録されています。")
                    return redirect('attendance:attendance_punch')
                attendance.clock_out = now_datetime
                success_message = "退勤を記録しました。お疲れ様でした！"

            elif punch_type == 'break_start':
                if not attendance.clock_in or attendance.clock_out:
                    messages.warning(request, "勤務時間外は休憩を開始できません。")
                    return redirect('attendance:attendance_punch')
                if attendance.break_start and not attendance.break_end:
                    messages.warning(request, "既に休憩を開始しています。")
                    return redirect('attendance:attendance_punch')
                attendance.break_start = now_datetime
                success_message = "休憩開始を記録しました。"

            elif punch_type == 'break_end':
                if not attendance.break_start or attendance.break_end:
                    messages.warning(request, "休憩が開始されていないか、既に終了しています。")
                    return redirect('attendance:attendance_punch')
                attendance.break_end = now_datetime
                success_message = "休憩終了を記録しました。"
            else:
                logger.warning(f"【不正パラメータ】未知の打刻種別: {punch_type}（ユーザー: {log_user_id(user.user_id)}）")
                messages.error(request, "不正なリクエストです。")
                return redirect('attendance:attendance_punch')

            attendance.update_user = user.user_name or user.user_id
            attendance.save(using=using_db)
            logger.info(f"【打刻成功】ユーザー: {log_user_id(user.user_id)}, 確定種別: {punch_type}")
            messages.success(request, success_message)

        except Exception as e:
            logger.critical(
                f"【打刻システム障害】ユーザー: {log_user_id(user.user_id)}, 種別: {punch_type} - {str(e)}",
                exc_info=True
            )
            messages.error(request, "サーバーエラーにより打刻を保存できませんでした。")

        return redirect('attendance:attendance_punch')

# =====================================================================
# 4. 日報管理（提出・削除）ブロック
# =====================================================================
class DailyReportSubmitView(AttendanceLoginMixin, View):
    """
    日報の登録・編集画面。

    【業務ルール】
    - GETパラメータ/POSTパラメータの `date`/`target_date` で対象日を
      指定する（未指定時は本日扱い）。1人1日1レコードのため、
      既存の日報があれば編集、無ければ新規作成（upsert的な動作）。
    - その日のAttendanceが既に存在すれば日報に紐付けるが、
      Attendanceが無くても日報単体の登録は可能
      （例: 客先常駐で打刻システムを使わない社員の日報運用等を想定）。
    - 対象月の月報が提出済み/確定済みの場合は新規登録・編集ともに不可。

    【URL設計の注意】
    GETとPOSTで日付の受け渡し方法が異なる
    （GET: クエリパラメータ `?date=`, POST: フォームの `target_date`）。
    画面遷移（フォーム送信後のリダイレクト）でもクエリパラメータに
    変換し直しているため、テンプレート側のフォーム実装を変更する際は
    この非対称性に注意すること。
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        date_str = request.GET.get('date')

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localtime(timezone.now()).date()
        except ValueError:
            logger.warning(f"【入力不正】date_strのフォーマット不正: {date_str} ユーザー: {log_user_id(user.user_id)}")
            messages.warning(request, "日付の指定が不正なため、本日の日報を表示します。")
            target_date = timezone.localtime(timezone.now()).date()

        try:
            report = DailyReport.objects.using(using_db).filter(
                user_id=user.user_id, report_date=target_date, delete_flg=0
            ).first()
            # ロック状態をテンプレートへ渡すためのフラグ判定
            target_month_str = target_date.strftime('%Y-%m')
            is_locked = MonthlyReport.objects.using(using_db).filter(
                user_id=user.user_id, target_month=target_month_str, status__in=['SUBMITTED', 'APPROVED'], delete_flg=0
            ).exists()
        except Exception as e:
            logger.error(
                f"【読込エラー】日報画面表示用データ取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            messages.error(request, "日報データの取得中にエラーが発生しました。")
            report = None
            is_locked = False

        context = {
            'report': report,
            'target_date': target_date,
            'target_date_str': target_date.strftime('%Y-%m-%d'),
            'is_locked': is_locked
        }
        return render(request, 'attendance/report.html', context)
    # 💡 1レコードの更新ですが、get_or_createの挙動と確定済チェックの安全性を担保するため関数全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        user = request.user
        date_str = request.POST.get('target_date')

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localtime(timezone.now()).date()
        except ValueError:
            logger.warning(f"【入力不正】target_dateのフォーマット不正: {date_str} ユーザー: {log_user_id(user.user_id)}")
            messages.warning(request, "日付の指定が不正なため、本日の日付で処理します。")
            target_date = timezone.localtime(timezone.now()).date()

        # 🔒 【月次ロック 2/4】DailyReportSubmitView — 他の3箇所と必ず同時に変更すること
        # → AttendancePunchView(views.py:444), DailyReportDeleteView(views.py:688), WorkApplicationView(views.py:1190)
        target_month_str = target_date.strftime('%Y-%m')
        if MonthlyReport.objects.using(using_db).filter(
            user_id=user.user_id, target_month=target_month_str, status__in=['SUBMITTED', 'APPROVED'], delete_flg=0
        ).exists():
            logger.warning(
                f"[REPORT][BLOCKED] 提出済月報への日報操作試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            messages.error(request, f"【保存拒否】{target_month_str}分の月報が提出済みの新規日報操作は行えません。")
            return redirect('attendance:monthly_report')

        work_location = request.POST.get('work_location')
        task_summary = request.POST.get('task_summary')
        comment = request.POST.get('comment')

        try:
            report = DailyReport.objects.using(using_db).select_for_update().filter(
                user_id=user.user_id, report_date=target_date, delete_flg=0
            ).first()
            created = False

            if not report:
                creator_name = user.user_name or user.user_id
                attendance = Attendance.objects.using(using_db).filter(
                    user_id=user.user_id, work_date=target_date, delete_flg=0
                ).first()

                report = DailyReport(
                    user_id=user.user_id,
                    report_date=target_date,
                    attendance=attendance,
                    create_user=creator_name
                )
                created = True

            report.task_summary = task_summary
            report.comment = comment
            report.work_location = work_location
            report.update_user = user.user_name or user.user_id
            report.save(using=using_db)

            action_label = "登録" if created else "更新"
            logger.info(f"【日報保存成功】ユーザー: {log_user_id(user.user_id)}, 日付: {target_date}, 処理: {action_label}")
            messages.success(request, f"{target_date.strftime('%m/%d')} の日報を{action_label}しました。")

        except Exception as e:
            logger.error(f"【日報保存エラー】ユーザー: {log_user_id(user.user_id)} - {str(e)}", exc_info=True)
            messages.error(request, "日報の保存に失敗しました。")

        return redirect(f"{reverse_lazy('attendance:daily_report_submit')}?date={target_date.strftime('%Y-%m-%d')}")


class DailyReportDeleteView(AttendanceLoginMixin, View):
    """
    日報の削除処理（POST専用、画面は持たない）。

    【業務ルール】
    - 自分の日報のみ削除可能（`user_id=user.user_id`で他人の日報への
      アクセスを防止。IDを直接POSTされても他人のデータは削除できない）。
    - 対象月の月報が提出済み/確定済みの場合は削除不可。
    """
    # 💡 削除処理と確定チェックのデータ整合性を守るため、トランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        report_id = request.POST.get('report_id')
        user = request.user

        # report_idが未指定/不正値の場合の早期検知
        if not report_id:
            logger.warning(f"【不正削除検知】report_id未指定。ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "削除対象が指定されていません。")
            return redirect('attendance:monthly_report')

        try:
            report = DailyReport.objects.using(using_db).select_for_update().filter(
                id=report_id, user_id=user.user_id, delete_flg=0
            ).first()
        except (ValueError, ValidationError):
            logger.warning(f"【不正削除検知】report_idが不正な形式です: {report_id} ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "削除対象の指定が不正です。")
            return redirect('attendance:monthly_report')

        if not report:
            logger.warning(f"【不正削除検知】存在しないか他人の日報削除。ユーザー: {log_user_id(user.user_id)}, ID: {report_id}")
            messages.error(request, "対象の日報が見つからないか、権限がありません。")
            return redirect('attendance:monthly_report')

        # 🚨 ロックガード：確定済み月の日報は削除不可
        # 🔒 【月次ロック 3/4】DailyReportDeleteView — 他の3箇所と必ず同時に変更すること
        # → AttendancePunchView(views.py:444), DailyReportSubmitView(views.py:601), WorkApplicationView(views.py:1190)
        target_month_str = report.report_date.strftime('%Y-%m')
        if MonthlyReport.objects.using(using_db).filter(
            user_id=user.user_id, target_month=target_month_str, status__in=['SUBMITTED', 'APPROVED'], delete_flg=0
        ).exists():
            logger.warning(
                f"[REPORT][BLOCKED] 確定済月の日報削除試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            messages.error(request, "確定済みの月の為、日報を削除できません。")
            return redirect('attendance:monthly_report')

        try:
            target_date_str = report.report_date.strftime('%Y-%m-%d')
            report.delete_flg = 1
            report.update_user = user.user_name or user.user_id
            report.save(using=using_db, update_fields=['delete_flg', 'update_user', 'update_date'])
            logger.info(f"【日報削除成功】ユーザー: {log_user_id(user.user_id)}, 日付: {target_date_str}")
            messages.success(request, f"{target_date_str} の日報を削除しました。")
        except Exception as e:
            logger.error(f"【日報削除エラー】ユーザー: {log_user_id(user.user_id)} - {str(e)}", exc_info=True)
            messages.error(request, "日報の削除中にエラーが発生しました。")

        return redirect('attendance:monthly_report')

# =====================================================================
# 5. 月次勤務一覧・月報提出 ブロック
# =====================================================================
class MonthlyReportView(AttendanceLoginMixin, TemplateView):
    """
    月報画面（カレンダー形式の月次一覧表示 + 月報提出）。

    【GET: 表示内容】
    対象月（GETパラメータ`month`、'YYYY-MM'形式、未指定時は当月）の
    日別データを1日分ずつ組み立て、以下を1行にまとめて返す:
      - 出退勤時刻、実労働/残業/休憩時間（表示用にフォーマット済み）
      - 祝日判定（jpholidayライブラリ使用）
      - その日の日報の有無・概要
      - その日に紐づく申請のステータス・種別
    また、月報自体のステータス（未提出/提出済/確定/差し戻し）も
    あわせて返す。

    【POST: 月報提出（action_type='submit_monthly_report'）】
    対象月のAttendanceを集計し、MonthlyReportレコードを
    作成または更新してstatus='SUBMITTED'にする。
    これにより当月のAttendance/DailyReport/WorkApplicationの
    新規登録・編集・削除がロックされる（各ビュー側の判定ロジックを参照）。

    【⚠️ 注意: 月報提出は「再提出可能」】
    get_or_create + 未createdなら値を更新、という実装のため、
    一度SUBMITTEDになった月報でも、ロジック上は再度POSTすれば
    再集計・再提出が可能（ロックされるのはAttendance/DailyReport側の
    操作であり、月報自体の再提出を防ぐ仕組みはこのビュー内には無い）。
    差し戻し（REJECTED）後の再提出フローもこの同じPOST処理を通る。
    """
    template_name = 'attendance/monthly_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        target_month_str = self.request.GET.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')

        # --- 年月パース（ここで失敗したら以降の処理ができないので個別にハンドリング） ---
        try:
            parsed_date = datetime.strptime(target_month_str, '%Y-%m')
        except ValueError:
            logger.warning(
                f"【パラメータ不正】month指定が不正: {target_month_str} ユーザー: {log_user_id(user.user_id)}"
            )
            messages.warning(self.request, "年月の指定が不正なため、当月のデータを表示します。")
            target_month_str = timezone.localtime(timezone.now()).strftime('%Y-%m')
            parsed_date = datetime.strptime(target_month_str, '%Y-%m')

        year, month = parsed_date.year, parsed_date.month
        prev_month = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        context['prev_month_str'] = prev_month.strftime('%Y-%m')
        context['next_month_str'] = next_month.strftime('%Y-%m')
        context['target_month'] = target_month_str

        # --- 月内データの展開（DBアクセス起因のエラーはここでまとめてキャッチ） ---
        try:
            _, num_days = calendar.monthrange(year, month)
            # 🛠️ 強化: values() ではなく、パフォーマンスを高めつつオブジェクトとしてクエリする(.only)
            # これにより辞書バグを防ぎ、かつDB負荷を最適化します
            attendances = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date__year=year, work_date__month=month, delete_flg=0
            ).only('work_date', 'clock_in', 'clock_out', 'actual_work_hours', 'overtime_hours', 'break_hours', 'work_type')
            attendance_dict = {att.work_date: att for att in attendances}
            # 日報マッピング
            reports = DailyReport.objects.using(using_db).filter(
                user_id=user.user_id, report_date__year=year, report_date__month=month, delete_flg=0
            )
            report_dict = {r.report_date: r for r in reports}
            # 申請状況マッピング
            applications = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id, target_date__year=year, target_date__month=month, delete_flg=0
            )
            application_dict = {app.target_date: app for app in applications}
            # 月次締め状況の確認
            monthly_report = MonthlyReport.objects.using(using_db).filter(
                user_id=user.user_id, target_month=target_month_str, delete_flg=0
            ).first()
            context['monthly_report_status'] = monthly_report.status if monthly_report else 'UNSUBMITTED'
            context['monthly_report_comment'] = monthly_report.approval_comment if monthly_report else ''

            # 1日〜月末までをスイープして画面行を生成
            days_in_month = []
            for day in range(1, num_days + 1):
                loop_date = date(year, month, day)
                att = attendance_dict.get(loop_date)

                day_data = {
                    'work_date': loop_date,
                    'clock_in': att.clock_in if att else None,
                    'clock_out': att.clock_out if att else None,
                    'display_work_hours': format_duration(att.actual_work_hours) if att else "-",
                    'display_overtime_hours': format_duration(att.overtime_hours) if att else "-",
                    'display_break_hours': format_duration(att.break_hours) if att else "-",
                    'weekday': loop_date.strftime('%a'),
                    'is_holiday': jpholiday.is_holiday(loop_date),
                    'display_work_type': att.get_work_type_display() if att else "出勤",
                }
                # 日報紐付け
                rep = report_dict.get(loop_date)
                day_data['has_report'] = rep is not None
                day_data['report_summary'] = rep.task_summary if rep else ''
                # 申請紐付け 
                app = application_dict.get(loop_date)
                day_data['app_status'] = app.status if app else None
                day_data['app_type'] = app.apply_type if app else None

                days_in_month.append(day_data)

            context['days_in_month'] = days_in_month

        except Exception as e:
            logger.error(
                f"【画面エラー】月報テーブル生成に失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            messages.error(self.request, "月次データの展開中にエラーが発生しました。")
            context['days_in_month'] = []
            context.setdefault('monthly_report_status', 'UNSUBMITTED')
            context.setdefault('monthly_report_comment', '')

        return context
    # 💡 月次集計データの計算から、get_or_createによる生成・保存までを一貫して守るため関数全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        """月報の確定提出を受け付けるPOSTロジック"""
        user = request.user
        action_type = request.POST.get('action_type')
        target_month_str = request.GET.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')

        if action_type == 'submit_monthly_report':
            try:
                parsed_date = datetime.strptime(target_month_str, '%Y-%m')
            except ValueError:
                logger.warning(
                    f"【パラメータ不正】月報提出時のmonth指定が不正: {target_month_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "年月の指定が不正なため、月報を提出できませんでした。")
                return redirect(f"{request.path}?month={target_month_str}")

            # 承認済み月報への再提出ブロック（管理者の承認を社員が無効化できないよう保護）
            existing = MonthlyReport.objects.using(using_db).filter(
                user_id=user.user_id, target_month=target_month_str
            ).first()
            if existing and existing.status == 'APPROVED':
                logger.warning(
                    f"[MONTHLY][BLOCKED] 承認済み月報への再提出試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
                )
                messages.error(request, f"【操作拒否】{target_month_str}分の月報は既に確定承認済みのため、再提出できません。")
                return redirect(f"{request.path}?month={target_month_str}")

            try:
                attendances = Attendance.objects.using(using_db).filter(
                    user_id=user.user_id, work_date__year=parsed_date.year, work_date__month=parsed_date.month, delete_flg=0
                )

                total_days = attendances.filter(clock_in__isnull=False).count()
                total_work = timedelta(0)
                total_overtime = timedelta(0)

                for att in attendances:
                    if att.actual_work_hours:
                        total_work += att.actual_work_hours
                    if att.overtime_hours:
                        total_overtime += att.overtime_hours

                creator_name = user.user_name or user.user_id

                monthly_report, created = MonthlyReport.objects.using(using_db).get_or_create(
                    user_id=user.user_id,
                    target_month=target_month_str,
                    defaults={
                        'total_work_days': total_days,
                        'total_work_hours': total_work,
                        'total_overtime_hours': total_overtime,
                        'status': 'SUBMITTED',
                        'create_user': creator_name,
                        'update_user': creator_name
                    }
                )

                if not created:
                    monthly_report.total_work_days = total_days
                    monthly_report.total_work_hours = total_work
                    monthly_report.total_overtime_hours = total_overtime
                    monthly_report.status = 'SUBMITTED'
                    monthly_report.update_user = creator_name
                    monthly_report.save(using=using_db)

                messages.success(request, f"{target_month_str}分の月報を提出しました。確定ロック中となります。")
                logger.info(
                    f"【月報提出成功】ユーザー: {log_user_id(user.user_id)}, 月: {target_month_str}, 出勤日数: {total_days}"
                )

            except Exception as e:
                logger.error(
                    f"【提出エラー】月報締め処理失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                    exc_info=True
                )
                messages.error(request, "月報の確定処理中にエラーが発生しました。")

            return redirect(f"{request.path}?month={target_month_str}")

        # 未知のaction_typeは必ずハンドリングして応答を返す（Noneを返してエラーになるのを防止）
        logger.warning(f"【不正パラメータ】未知のaction_type: {action_type}（ユーザー: {log_user_id(user.user_id)}）")
        messages.error(request, "不正な操作です。")
        return redirect(f"{request.path}?month={target_month_str}")

# =====================================================================
# 6. 管理者専用（確認・検索・CSVエクスポート）ブロック
# =====================================================================
class AdminReportListView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, ListView):
    """
    【管理者専用】全社員の日報一覧画面。

    対象月（`month`）・対象社員（`user_id`）でフィルタ可能。
    `test_func()` で `is_staff` または `is_superuser` のみアクセスを許可
    （`UserPassesTestMixin` の標準動作により、権限が無い場合は
    `handle_no_permission()` が呼ばれ、ここでは403ではなくDjango標準の
    ログインリダイレクト/拒否動作にログ出力を追加している）。
    """
    template_name = "attendance/admin_report_list.html"
    context_object_name = "reports"

    def test_func(self):
        # dispatch() の中で自動実行される権限チェック。False なら handle_no_permission() へ進む
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        logger.warning(
            f"【不正アクセス警告】非管理者が管理者専用一覧にアクセスを試みました。"
            f"ユーザーID: {getattr(self.request.user, 'user_id', 'AnonymousUser')}"
        )
        return super().handle_no_permission()

    def get_queryset(self):
        month_str = self.request.GET.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')
        try:
            target_date = datetime.strptime(month_str, '%Y-%m')
            year, month = target_date.year, target_date.month
        except ValueError:
            logger.warning(f"【パラメータ不正】一覧表示用month指定が不正: {month_str}")
            now_local = timezone.localtime(timezone.now())
            year, month = now_local.year, now_local.month

        try:
            queryset = DailyReport.objects.using(using_db).filter(report_date__year=year, report_date__month=month, delete_flg=0)

            selected_user_id = self.request.GET.get('user_id')
            if selected_user_id:
                queryset = queryset.filter(user_id=selected_user_id)

            reports = list(queryset.order_by('-report_date', '-id'))
            # 【マルチDB高速化】Pythonインメモリ側でのユーザー結合
            # 💡 【重要バグ修正】別DBカスタムユーザーとのインメモリ安全結合（予約語競合対策）
            if reports:
                user_ids = [r.user_id for r in reports if r.user_id]
                users = User.objects.filter(user_id__in=user_ids)
                user_map = {u.user_id: u for u in users}

                for report in reports:
                    report.assigned_user = user_map.get(report.user_id)

            return reports
        except Exception as e:
            logger.error(f"【読込エラー】管理者用日報一覧の取得失敗 - {str(e)}", exc_info=True)
            messages.error(self.request, "日報一覧の取得中にエラーが発生しました。")
            return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target_month'] = self.request.GET.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')
        context['selected_user_id'] = self.request.GET.get('user_id')
        try:
            context['staff_list'] = User.objects.filter(is_active=True).order_by('user_name')
        except Exception as e:
            logger.error(f"【読込エラー】社員一覧の取得失敗 - {str(e)}", exc_info=True)
            context['staff_list'] = []
        return context


class AdminReportCsvDownloadView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View):
    """
    📥 【管理者限定】全社日報データをExcel対応のShift-JIS(cp932)でBOMなし書き出し

    【なぜcp932なのか】
    社内のExcel運用に合わせ、Shift-JIS(cp932)で出力している
    （UTF-8版はExportAttendanceCSVView側で別途用意されている）。
    `response.charset = 'cp932'` を明示しないと、Djangoの
    HttpResponseは実際にはUTF-8でエンコードしてしまう点に注意
    （content_typeのcharset指定だけでは効かない、Django特有の挙動）。

    【cp932非対応文字への対応】
    絵文字等、cp932で表現できない文字が日報本文に含まれていた場合、
    通常のwriterow()でUnicodeEncodeErrorが発生する。
    本実装ではtry-exceptで個別行のエラーを検知し、該当行のみ
    `errors='replace'` で代替文字に変換して再書き込みすることで、
    1行のエラーでCSV全体の出力が失敗しないようにしている。
    """
    def test_func(self):
        # dispatch() の中で自動実行される権限チェック。False なら handle_no_permission() へ進む
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        logger.warning(
            f"【不正アクセス警告】非管理者がCSVダウンロードを試みました。"
            f"ユーザーID: {getattr(self.request.user, 'user_id', 'AnonymousUser')}"
        )
        return super().handle_no_permission()

    def get(self, request, *args, **kwargs):
        month_str = request.GET.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')
        selected_user_id = request.GET.get('user_id')

        logger.info(
            f"【CSVエクスポート実行】管理者: {log_user_id(request.user.user_id)}, "
            f"条件[月]: {month_str}, [社員]: {selected_user_id}"
        )

        # 年月フォーマットのバリデーションは個別に行い、原因を明確にする
        try:
            target_date = datetime.strptime(month_str, '%Y-%m')
        except ValueError:
            logger.warning(f"【CSV出力エラー】無効な年月フォーマットが指定されました: {month_str}")
            messages.error(request, "年月の指定が不正です。")
            return redirect('attendance:admin_report_list')

        try:
            queryset = DailyReport.objects.using(using_db).filter(
                report_date__year=target_date.year, report_date__month=target_date.month, delete_flg=0
            )
            if selected_user_id:
                queryset = queryset.filter(user_id=selected_user_id)

            reports = list(queryset.order_by('report_date'))

            response = HttpResponse(content_type='text/csv')
            # content_typeのcharset指定だけでなく、response.charsetを明示的に設定する
            # （HttpResponseの実エンコード処理はresponse.charsetを参照するため）
            response.charset = 'cp932'
            filename = f"daily_reports_{month_str}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            writer = csv.writer(response)
            writer.writerow(['日付', '社員ID', '氏名', '勤務場所', '業務内容', '所感・連絡事項'])

            if reports:
                user_ids = [r.user_id for r in reports if r.user_id]
                user_map = {u.user_id: u for u in User.objects.filter(user_id__in=user_ids)}

                for r in reports:
                    user_obj = user_map.get(r.user_id)
                    user_name = user_obj.user_name if user_obj else "所属不明"
                    safe_summary = (r.task_summary or '').replace('\r\n', ' ').replace('\n', ' ')
                    safe_comment = (r.comment or '').replace('\r\n', ' ').replace('\n', ' ')
                    work_location_display = (
                        r.get_work_location_display() if hasattr(r, 'get_work_location_display')
                        else (r.work_location or '未指定')
                    )
                    try:
                        # response.charsetがcp932なので、ここでは事前エンコードせず素の文字列を渡す
                        writer.writerow([
                            r.report_date.strftime('%Y/%m/%d'),
                            r.user_id,
                            user_name,
                            work_location_display,
                            safe_summary,
                            safe_comment,
                        ])
                    except UnicodeEncodeError:
                        # cp932非対応文字（絵文字など）が含まれる場合のみ代替文字に変換して再書き込み
                        logger.warning(
                            f"【CSV文字化け回避】社員ID:{r.user_id} 日付:{r.report_date} "
                            f"の内容にcp932非対応文字を検知したため代替文字で出力します。"
                        )
                        writer.writerow([
                            r.report_date.strftime('%Y/%m/%d'),
                            r.user_id,
                            user_name,
                            work_location_display,
                            safe_summary.encode('cp932', errors='replace').decode('cp932'),
                            safe_comment.encode('cp932', errors='replace').decode('cp932'),
                        ])

            logger.info(f"【CSV出力完了】件数: {len(reports)}件")
            return response

        except Exception as e:
            logger.critical(
                f"【CSV出力致命的エラー】管理者: {log_user_id(request.user.user_id)} - 原因: {str(e)}",
                exc_info=True
            )
            messages.error(request, "CSVの生成中に予期せぬエラーが発生しました。")
            return redirect('attendance:admin_report_list')


class WorkApplicationView(AttendanceLoginMixin, View):
    """
    各種就業申請の入力・一覧画面。

    【申請種別ごとの必須項目（apply_type別）】
    - OVERTIME（残業申請）:
        `requested_overtime_hours`（HH:MM形式）が必須。
        承認されると、この値でそのままAttendance.overtime_hoursが
        上書きされる（打刻ベースの自動計算値は使われない）。
    - CORRECTION（打刻修正申請）:
        `corrected_clock_in` / `corrected_clock_out`（HH:MM形式）、
        必要に応じて `corrected_break_hours`（HH:MM形式）を指定。
        承認されると、この時刻でAttendanceのclock_in/clock_outが
        書き換えられ、実労働時間・残業時間が打刻ベースで再計算される。
    - PAID_LEAVE / AM_LEAVE / PM_LEAVE / COMP_LEAVE（休暇系）:
        時刻指定は不要。`reason`（申請理由）のみ必須。
        承認されると、対象日のAttendance.work_typeが該当区分に
        変更される（全休・代休の場合は出退勤・労働時間も0クリアされる）。

    【重複申請防止】
    同一ユーザー・同一対象日・同一申請種別の組み合わせは1件まで
    （DBのunique_together制約 + ビュー側の事前exists()チェックの二重防御）。
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        default_date = request.GET.get('date', '')
        try:
            my_applications = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id, delete_flg=0
            ).order_by('-target_date', '-create_date')
        except Exception as e:
            logger.error(f"【読込エラー】申請一覧の取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}", exc_info=True)
            messages.error(request, "申請一覧の取得中にエラーが発生しました。")
            my_applications = []

        # 有給残日数（当年度）
        fiscal_year = get_fiscal_year()
        try:
            leave_balance = LeaveBalance.objects.using(using_db).filter(
                user_id=user.user_id, fiscal_year=fiscal_year
            ).first()
            pending_leave_days = get_pending_leave_days(user.user_id, fiscal_year)
        except Exception as e:
            logger.error(f"【読込エラー】有給残日数取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}", exc_info=True)
            leave_balance = None
            pending_leave_days = Decimal('0')

        context = {
            'my_applications': my_applications,
            'apply_type_choices': WorkApplication.APPLY_TYPE_CHOICES,
            'default_date': default_date,
            'leave_balance': leave_balance,
            'pending_leave_days': pending_leave_days,
            'fiscal_year': fiscal_year,
        }
        return render(request, 'attendance/application_form.html', context)
    # 💡 申請重複チェックからインサート処理までをアトミックに保つため関数全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        user = request.user
        apply_type = request.POST.get('apply_type')
        target_date_str = request.POST.get('target_date')
        reason = request.POST.get('reason')
        corrected_clock_in_str = request.POST.get('corrected_clock_in') or None
        corrected_clock_out_str = request.POST.get('corrected_clock_out') or None
        corrected_break_hours_str = request.POST.get('corrected_break_hours') or None

        # --- apply_typeのホワイトリスト検証 ---
        valid_apply_types = {choice[0] for choice in WorkApplication.APPLY_TYPE_CHOICES}
        if apply_type not in valid_apply_types:
            logger.warning(f"【入力不正】未知のapply_type: {apply_type} ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "申請種別の指定が不正です。")
            return redirect('attendance:work_application')

        # --- target_dateのフォーマット検証（不正値はモデル保存前に弾く） ---
        try:
            parsed_target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            logger.warning(f"【入力不正】target_dateのフォーマット不正: {target_date_str} ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "対象日の形式が不正です。")
            return redirect('attendance:work_application')

        # --- 月報提出済み・確定済み月への申請ブロック ---
        # 🔒 【月次ロック 4/4】WorkApplicationView — 他の3箇所と必ず同時に変更すること
        # → AttendancePunchView(views.py:444), DailyReportSubmitView(views.py:601), DailyReportDeleteView(views.py:688)
        target_month_str = parsed_target_date.strftime('%Y-%m')
        if MonthlyReport.objects.using(using_db).filter(
            user_id=user.user_id, target_month=target_month_str, status__in=['SUBMITTED', 'APPROVED'], delete_flg=0
        ).exists():
            logger.warning(
                f"[APPLICATION][BLOCKED] 提出済月報への申請試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            messages.error(request, f"【申請拒否】{target_month_str}分の月報は既に提出または確定されているため、申請できません。")
            return redirect('attendance:work_application')

        # --- 有給系申請: 残日数チェック ---
        if apply_type in LEAVE_COST:
            cost = LEAVE_COST[apply_type]
            fiscal_year = get_fiscal_year(parsed_target_date)
            balance = LeaveBalance.objects.using(using_db).filter(
                user_id=user.user_id, fiscal_year=fiscal_year
            ).first()
            if balance is None:
                logger.warning(
                    f"[LEAVE][NO_BALANCE] 有給残日数未登録 - ユーザー: {log_user_id(user.user_id)}, {fiscal_year}年度"
                )
                messages.error(
                    request,
                    f"{fiscal_year}年度の有給残日数が登録されていません。管理者にご連絡ください。"
                )
                return redirect('attendance:work_application')
            pending_days = get_pending_leave_days(user.user_id, fiscal_year)
            available = balance.remaining_days - pending_days
            if available < cost:
                logger.warning(
                    f"[LEAVE][INSUFFICIENT] 有給残日数不足 - ユーザー: {log_user_id(user.user_id)}, "
                    f"利用可能: {available}日, 申請: {cost}日"
                )
                messages.error(
                    request,
                    f"有給残日数が不足しています（利用可能: {available}日、申請: {cost}日）。"
                )
                return redirect('attendance:work_application')

        # --- CORRECTION申請時の時刻フォーマット検証 ---
        if apply_type == 'CORRECTION':
            try:
                if corrected_clock_in_str:
                    datetime.strptime(corrected_clock_in_str, '%H:%M')
                if corrected_clock_out_str:
                    datetime.strptime(corrected_clock_out_str, '%H:%M')
            except ValueError:
                logger.warning(
                    f"【入力不正】出退勤修正時刻のフォーマット不正 "
                    f"in:{corrected_clock_in_str} out:{corrected_clock_out_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "修正時刻の形式（HH:MM）が不正です。")
                return redirect('attendance:work_application')

            # 出勤・退勤の両方が指定されている場合は前後関係も検証する
            if corrected_clock_in_str and corrected_clock_out_str:
                t_in = datetime.strptime(corrected_clock_in_str, '%H:%M').time()
                t_out = datetime.strptime(corrected_clock_out_str, '%H:%M').time()
                if t_in >= t_out:
                    logger.warning(
                        f"【入力不正】修正後の出勤時刻が退勤時刻以降です。ユーザー: {log_user_id(user.user_id)}, "
                        f"in:{corrected_clock_in_str} out:{corrected_clock_out_str}"
                    )
                    messages.error(request, "修正後の出勤時刻は退勤時刻より前である必要があります。")
                    return redirect('attendance:work_application')
        # 💡 【型クラッシュバグ修正】画面から送られた休憩時間文字列(HH:MM)をDurationField型へ安全キャスト
        corrected_break_hours = None
        if corrected_break_hours_str and apply_type == 'CORRECTION':
            try:
                t = datetime.strptime(corrected_break_hours_str, "%H:%M")
                corrected_break_hours = timedelta(hours=t.hour, minutes=t.minute)
            except ValueError:
                # 不正値を黙って1時間に補完するのはデータ汚染のリスクがあるため、
                # エラーとして弾いてユーザーに再入力させる
                logger.warning(
                    f"【入力不正】休憩時間フォーマット不正: {corrected_break_hours_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "休憩時間の形式（HH:MM）が不正です。")
                return redirect('attendance:work_application')

        # --- OVERTIME申請時の申請残業時間の検証 ---
        # 承認時にこの値でAttendance.overtime_hoursを上書きするため、必須項目として扱う
        requested_overtime_hours = None
        if apply_type == 'OVERTIME':
            requested_overtime_hours_str = request.POST.get('requested_overtime_hours') or None
            if not requested_overtime_hours_str:
                logger.warning(f"【入力不正】残業申請なのにrequested_overtime_hours未入力 ユーザー: {log_user_id(user.user_id)}")
                messages.error(request, "残業申請には申請時間（HH:MM）の入力が必須です。")
                return redirect('attendance:work_application')
            try:
                t = datetime.strptime(requested_overtime_hours_str, "%H:%M")
                requested_overtime_hours = timedelta(hours=t.hour, minutes=t.minute)
            except ValueError:
                logger.warning(
                    f"【入力不正】残業申請時間フォーマット不正: {requested_overtime_hours_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "残業申請時間の形式（HH:MM）が不正です。")
                return redirect('attendance:work_application')
            if requested_overtime_hours <= timedelta(0):
                logger.warning(
                    f"【入力不正】残業申請時間が0以下です: {requested_overtime_hours_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "残業申請時間は0より大きい値を指定してください。")
                return redirect('attendance:work_application')

        creator_name = getattr(user, 'user_name', None) or getattr(user, 'user_id', None) or 'SYSTEM_USER'

        logger.info(
            f"【申請処理開始】ユーザー: {log_user_id(user.user_id)}, 種別: {apply_type}, 対象日: {parsed_target_date}"
        )

        try:
            # exists()チェックとsave()の間に競合状態（race condition）が起こり得るため、
            # 最終的な防御線としてはWorkApplicationモデル側に
            # unique_together/UniqueConstraint(user_id, target_date, apply_type) を設定すること。
            # ここでの事前チェックはユーザーへの分かりやすいメッセージ表示のために行う。
            already_exists = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id,
                target_date=parsed_target_date,
                apply_type=apply_type,
                delete_flg=0
            ).exists()

            if already_exists:
                messages.warning(request, "この日付に対する同じ申請はすでに提出されています。")
                return redirect('attendance:dashboard')

            # 対象日の既存Attendanceがあれば紐付ける（無くても申請自体は可能。例えば未出勤日の有休申請など）
            related_attendance = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date=parsed_target_date, delete_flg=0
            ).first()

            application = WorkApplication(
                user_id=user.user_id,
                apply_type=apply_type,
                target_date=parsed_target_date,
                attendance=related_attendance,
                reason=reason,
                corrected_clock_in=corrected_clock_in_str,
                corrected_clock_out=corrected_clock_out_str,
                corrected_break_hours=corrected_break_hours,
                requested_overtime_hours=requested_overtime_hours,
                status='PENDING',
                create_user=creator_name,
                update_user=creator_name
            )
            application.save(using=using_db)

            logger.info(f"【申請処理成功】ユーザー: {log_user_id(user.user_id)}, 申請ID: {application.id}")
            messages.success(request, "申請を提出しました。上長の承認をお待ちください。")

        except IntegrityError:
            # DB側のユニーク制約による多重申請防止（competing requestsのフォールバック）
            logger.warning(
                f"【重複申請検知】ユーザー:{log_user_id(user.user_id)} 日付:{parsed_target_date} 種別:{apply_type}"
            )
            messages.warning(request, "同じ申請が既に存在します。")

        except Exception as e:
            logger.critical(
                f"【申請重大エラー】ユーザー: {log_user_id(user.user_id)} - エラー内容: {str(e)}",
                exc_info=True
            )
            messages.error(request, "システムエラーにより申請を送信できませんでした。")

        return redirect('attendance:work_application')


class ApplicationApprovalView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View):
    """
    【管理者専用】各種申請・月報の承認/却下を行う画面。

    `test_func()` で is_staff または is_superuser のみアクセスを許可。
    権限がない場合は `handle_no_permission()` が呼ばれ、
    attendance/403.html を返す（AttendanceAccessMixin の動作）。

    【POST: action_typeによる分岐】
    - 'approve' / 'reject':
        WorkApplication（残業/休暇/打刻修正申請）の承認・却下。
        承認時のAttendance反映ロジックは申請種別ごとに異なる
        （詳細はpost()メソッド内コメントを参照。特に
        「save()経由 vs QuerySet.update()経由」の使い分けが重要）。
    - 'approve_month' / 'reject_month':
        MonthlyReport（月報）の確定・差し戻し。
        確定（approve_month）すると status='APPROVED' / is_closed=1 / closed_date=現在日時 がセットされる。
        差し戻し（reject_month）すると status='REJECTED' / is_closed=0 に戻る。

        【is_closed の位置づけ】
        打刻・日報・申請のロック判定はすべて status フィールドで行っており
        （status__in=['SUBMITTED', 'APPROVED']）、is_closed を参照している
        箇所は現状ない。is_closed は「APPROVED 後は管理者でも差し戻し不可」
        といった厳格な締め処理が必要になった際の拡張ポイントとして
        意図的に残している。実装する場合は reject_month 分岐に
        `if report.is_closed: return error` のガードを追加すること。
    """
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        logger.warning(
            f"【不正アクセス警告】非管理者が管理者承認ページにアクセスを試みました。"
            f"ユーザーID: {getattr(self.request.user, 'user_id', 'AnonymousUser')}"
        )
        return super().handle_no_permission()

    def get(self, request, *args, **kwargs):
        try:
            # 💡 【重要】別DBカスタムユーザーとのインメモリ安全結合（一覧表示バグ回避）
            pending_applications = WorkApplication.objects.using(using_db).filter(
                status='PENDING', delete_flg=0
            ).order_by('target_date')
            pending_months = MonthlyReport.objects.using(using_db).filter(
                status='SUBMITTED', delete_flg=0
            ).order_by('target_month', 'user_id')

            if pending_applications:
                user_ids = [app.user_id for app in pending_applications]
                user_map = {u.user_id: u for u in User.objects.filter(user_id__in=user_ids)}
                for app in pending_applications:
                    app.assigned_user = user_map.get(app.user_id)

            if pending_months:
                user_ids = [rep.user_id for rep in pending_months]
                user_map = {u.user_id: u for u in User.objects.filter(user_id__in=user_ids)}
                for rep in pending_months:
                    rep.assigned_user = user_map.get(rep.user_id)

        except Exception as e:
            logger.error(f"【読込エラー】承認待ち一覧の取得失敗 - {str(e)}", exc_info=True)
            messages.error(request, "承認待ちデータの取得中にエラーが発生しました。")
            pending_applications = []
            pending_months = []

        context = {
            'pending_applications': pending_applications,
            'pending_months': pending_months,
        }
        return render(request, 'attendance/application_approval.html', context)
    # 💡 複数のDB更新（WorkApplicationとAttendance等）が連動して走るため、with構文で安全にブロックロック・処理
    def post(self, request, *args, **kwargs):
        user = request.user
        action_type = request.POST.get('action_type')
        approver_name = getattr(user, 'user_name', None) or getattr(user, 'user_id', None) or 'ADMIN'
        # --- A. 各種申請(残業・有給・打刻修正)の承認ロジック ---
        if action_type in ['approve', 'reject']:
            app_id = request.POST.get('application_id')
            comment = request.POST.get('comment', '')

            if not app_id:
                logger.warning(f"【申請処理エラー】application_id未指定 - 処理者: {log_user_id(user.user_id)}")
                messages.error(request, "対象の申請が指定されていません。")
                return redirect('attendance:application_approval')

            try:
                # 💡 データの不整合を防ぐため、承認/却下処理全体をトランザクション化
                with transaction.atomic(using=using_db):
                    application = WorkApplication.objects.using(using_db).select_for_update().get(pk=app_id)
                    applicant_id = application.user_id

                    if action_type == 'approve':
                        # 出退勤修正の前後関係チェック（承認時点でのデータ不整合を防止）
                        if application.apply_type == 'CORRECTION':
                            if (application.corrected_clock_in and application.corrected_clock_out
                                    and application.corrected_clock_in >= application.corrected_clock_out):
                                logger.warning(
                                    f"【承認時データ不整合】出勤時刻が退勤時刻以降です。"
                                    f"申請者:{applicant_id} 申請ID:{app_id}"
                                )
                                messages.error(
                                    request,
                                    "修正後の出勤時刻が退勤時刻以降になっているため承認できません。"
                                    "申請内容を確認してください。"
                                )
                                return redirect('attendance:application_approval')

                        # 残業申請承認時、申請残業時間が未設定（旧データ等）の場合は承認をブロックする
                        if application.apply_type == 'OVERTIME' and not application.requested_overtime_hours:
                            logger.warning(
                                f"【承認時データ不整合】残業申請に申請残業時間が設定されていません。"
                                f"申請者:{applicant_id} 申請ID:{app_id}"
                            )
                            messages.error(
                                request,
                                "この残業申請には申請時間が設定されていないため承認できません。"
                                "申請者に再申請を依頼してください。"
                            )
                            return redirect('attendance:application_approval')

                        application.status = 'APPROVED'

                        if application.apply_type == 'CORRECTION':
                            if application.corrected_clock_in and application.corrected_clock_out:
                                dt_in = datetime.combine(application.target_date, application.corrected_clock_in)
                                dt_out = datetime.combine(application.target_date, application.corrected_clock_out)

                                attendance, created = Attendance.objects.using(using_db).select_for_update().get_or_create(
                                    user_id=application.user_id,
                                    work_date=application.target_date
                                )

                                attendance.clock_in = (
                                    timezone.make_aware(dt_in) if timezone.is_naive(dt_in) else dt_in
                                )
                                attendance.clock_out = (
                                    timezone.make_aware(dt_out) if timezone.is_naive(dt_out) else dt_out
                                )

                                # 🔧 修正: timedelta(0)（休憩なしへの修正）はfalsyなため、
                                # `if application.corrected_break_hours:` だと条件に入らず無視されてしまう。
                                # Noneかどうかで明示的に判定する。
                                if application.corrected_break_hours is not None:
                                    attendance.break_hours = application.corrected_break_hours
                                attendance.work_type = 'NORMAL'
                                attendance.break_start = None
                                attendance.break_end = None
                                # CORRECTIONはclock_in/clock_outを変更し、それに基づく
                                # 実労働時間・残業時間の再計算が必要なため、通常通りsave()を使う
                                # （save()内の自動計算ロジックに委ねる）
                                attendance.save(using=using_db)

                                logger.info(
                                    f"【打刻修正反映成功】承認者: {log_user_id(user.user_id)} -> 申請者: {applicant_id}, "
                                    f"対象日: {application.target_date}"
                                )

                        elif application.apply_type == 'OVERTIME':
                            # (b) 申請された残業時間でAttendance.overtime_hoursを上書きする仕様。
                            # 通常のattendance.save()を使うと、Attendance.save()内の自動計算ロジックが
                            # clock_in/clock_outから残業時間を再計算してしまい、申請値が反映されないため、
                            # モデルのsave()をバイパスするQuerySet.update()を使った別経路で明示的に上書きする。
                            attendance, created = Attendance.objects.using(using_db).select_for_update().get_or_create(
                                user_id=application.user_id,
                                work_date=application.target_date,
                                defaults={'create_user': approver_name}
                            )
                            Attendance.objects.using(using_db).filter(pk=attendance.pk).update(
                                overtime_hours=application.requested_overtime_hours,
                                update_user=approver_name,
                                update_date=timezone.now(),
                            )
                            logger.info(
                                f"【残業申請承認・反映成功】承認者: {log_user_id(user.user_id)} -> 申請者: {applicant_id}, "
                                f"対象日: {application.target_date}, "
                                f"申請残業時間: {application.requested_overtime_hours}"
                            )

                        # ⚠️ 【申請種別追加時の必須対応】新しい apply_type を APPLY_TYPE_CHOICES に追加した場合は、
                        # 必ずここに elif を追加すること。追加しないと承認しても Attendance が更新されずサイレントに素通りする。
                        elif application.apply_type in ['PAID_LEAVE', 'AM_LEAVE', 'PM_LEAVE', 'COMP_LEAVE']:
                            attendance, created = Attendance.objects.using(using_db).select_for_update().get_or_create(
                                user_id=application.user_id,
                                work_date=application.target_date,
                                defaults={'create_user': approver_name}
                            )

                            if application.apply_type == 'AM_LEAVE':
                                new_work_type = 'AM_LEAVE'
                            elif application.apply_type == 'PM_LEAVE':
                                new_work_type = 'PM_LEAVE'
                            elif application.apply_type == 'COMP_LEAVE':
                                new_work_type = 'COMP_LEAVE'
                            else:
                                new_work_type = 'PAID_LEAVE'

                            update_fields = {
                                'work_type': new_work_type,
                                'update_user': approver_name,
                                'update_date': timezone.now(),
                            }

                            # 🔧 修正: 全休・代休の場合は出退勤を明示的にクリアし、
                            # 実労働・残業時間を明示的に0としてセットする。
                            # attendance.save()を経由すると、Attendance.save()内の自動計算ロジックが
                            # 必ず実行され「打刻データに基づく計算結果」で上書きされてしまうため
                            # （clock_in/clock_out=Noneなら自動的にNoneクリアされ、明示した
                            # timedelta(0)が保持されない）、save()をバイパスするQuerySet.update()を使い、
                            # 別経路で明示的に0を確定させる。
                            if new_work_type in ['PAID_LEAVE', 'COMP_LEAVE']:
                                update_fields.update({
                                    'clock_in': None,
                                    'clock_out': None,
                                    'actual_work_hours': timedelta(0),
                                    'overtime_hours': timedelta(0),
                                })

                            Attendance.objects.using(using_db).filter(pk=attendance.pk).update(**update_fields)

                            logger.info(
                                f"【勤務区分連動成功】上長承認に伴い、{application.user_id} の "
                                f"{application.target_date} を自動更新しました。区分: {new_work_type}"
                            )

                            # 有給系（PAID_LEAVE / AM_LEAVE / PM_LEAVE）は残日数を消費
                            if application.apply_type in LEAVE_COST:
                                cost = LEAVE_COST[application.apply_type]
                                fiscal_year = get_fiscal_year(application.target_date)
                                balance = LeaveBalance.objects.using(using_db).select_for_update().filter(
                                    user_id=application.user_id, fiscal_year=fiscal_year
                                ).first()
                                if balance:
                                    LeaveBalance.objects.using(using_db).filter(pk=balance.pk).update(
                                        used_days=balance.used_days + cost,
                                        update_user=approver_name,
                                        update_date=timezone.now(),
                                    )
                                    logger.info(
                                        f"【有給残日数更新】申請者: {application.user_id}, "
                                        f"{fiscal_year}年度, 消費: {cost}日"
                                    )
                                else:
                                    logger.warning(
                                        f"【有給残日数なし】申請者: {application.user_id}, "
                                        f"{fiscal_year}年度のレコードが存在しません。残日数は更新されませんでした。"
                                    )

                        else:
                            # 新しい申請種別が追加されたが上記分岐に対応が漏れている場合の安全網
                            logger.error(
                                f"【承認処理漏れ】未対応の申請種別です。Attendanceへの反映が行われませんでした。"
                                f" 申請ID: {app_id}, 種別: {application.apply_type}"
                                f" → ApplicationApprovalView の approve 分岐に elif を追加してください。"
                            )

                        logger.info(
                            f"【申請承認】承認者: {log_user_id(user.user_id)} -> 申請者: {applicant_id}, "
                            f"申請ID: {app_id}, 種別: {application.apply_type}"
                        )
                        messages.success(request, "申請を承認しました。")

                    else:
                        application.status = 'REJECTED'
                        logger.info(
                            f"【申請却下】却下者: {log_user_id(user.user_id)} -> 申請者: {applicant_id}, "
                            f"申請ID: {app_id}, コメント: {comment}"
                        )
                        messages.warning(request, "申請を却下しました。")

                    application.approver_id = user.user_id
                    application.approval_comment = comment
                    application.approval_date = timezone.now()
                    application.update_user = approver_name
                    application.save(using=using_db)

            except WorkApplication.DoesNotExist:
                logger.error(
                    f"【申請処理エラー】指定された申請IDが見つかりません。ID: {app_id}, 処理者: {log_user_id(user.user_id)}"
                )
                messages.error(request, "指定された申請が見つかりませんでした。")
            except Exception as e:
                logger.error(
                    f"【申請処理システムエラー】申請ID: {app_id} の処理中に予期せぬエラーが発生。原因: {str(e)}",
                    exc_info=True
                )
                messages.error(request, "申請の処理中にシステムエラーが発生しました。")
        # --- B. 月報締めの承認・差し戻しロジック ---
        elif action_type in ['approve_month', 'reject_month']:
            report_id = request.POST.get('report_id')
            comment = request.POST.get('comment', '')

            if not report_id:
                logger.warning(f"【月報処理エラー】report_id未指定 - 処理者: {log_user_id(user.user_id)}")
                messages.error(request, "対象の月報が指定されていません。")
                return redirect('attendance:application_approval')

            try:
                # 💡 月報のステータス更新・確定ロック処理を安全にアトミック化
                with transaction.atomic(using=using_db):
                    report = MonthlyReport.objects.using(using_db).select_for_update().get(pk=report_id)
                    target_user_id = report.user_id

                    if action_type == 'approve_month':
                        report.status = 'APPROVED'
                        report.is_closed = 1
                        report.closed_date = timezone.now()

                        logger.info(
                            f"【月報確定・締め完了】上長: {log_user_id(user.user_id)} -> 社員: {target_user_id}, "
                            f"対象月: {report.target_month}"
                        )
                        messages.success(request, f"{report.target_month}分 月報を【確定】しました。")

                    else:
                        report.status = 'REJECTED'
                        report.is_closed = 0

                        logger.info(
                            f"【月報差し戻し】上長: {log_user_id(user.user_id)} -> 社員: {target_user_id}, "
                            f"対象月: {report.target_month}"
                        )
                        messages.warning(request, f"{report.target_month}分 月報を【差し戻し】しました。")

                    report.approval_comment = comment
                    report.update_user = approver_name
                    report.save(using=using_db)

            except MonthlyReport.DoesNotExist:
                logger.error(
                    f"【月報処理エラー】指定された月報データが見つかりません。"
                    f"レポートID: {report_id}, 処理者: {log_user_id(user.user_id)}"
                )
                messages.error(request, "指定された月報データが見つかりませんでした。")
            except Exception as e:
                logger.error(
                    f"【月報処理システムエラー】レポートID: {report_id} の処理中に予期せぬエラーが発生。"
                    f"原因: {str(e)}",
                    exc_info=True
                )
                messages.error(request, "月報締め処理中にシステムエラーが発生しました。")

        else:
            logger.warning(f"【不正パラメータ】未知のaction_type: {action_type}（処理者: {log_user_id(user.user_id)}）")
            messages.error(request, "不正な操作です。")

        return redirect('attendance:application_approval')


class ExportAttendanceCSVView(AttendanceLoginMixin, View):
    """
    【管理者専用】全社員分の勤怠実績（Attendance）をCSV出力する。

    AdminReportCsvDownloadView（日報CSV、cp932/Shift-JIS出力）とは
    別物で、こちらは「打刻実績そのもの」をUTF-8(BOM付き)で出力する。
    BOM付きUTF-8にしているのは、Excelで開いた際に文字化けしないよう
    にするための対応（cp932ではなくUTF-8を選んでいるのは、
    出力データに絵文字等のcp932非対応文字が含まれる可能性を
    考慮した設計と思われる）。

    権限チェックは `LoginRequiredMixin` のみで `UserPassesTestMixin`
    を使わず、メソッド内で `is_staff` を直接判定し、403を返す方式
    （他の管理者専用ビューとは実装パターンが異なる点に注意）。
    """
    def get(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            logger.warning(
                f"【不正アクセス警告】非管理者がCSVダウンロードを試みました。ユーザーID: {log_user_id(request.user.user_id)}"
            )
            return HttpResponse("Forbidden", status=403)

        target_month_str = request.GET.get('month', timezone.localtime(timezone.now()).strftime('%Y-%m'))

        try:
            parsed_date = datetime.strptime(target_month_str, '%Y-%m')
        except ValueError:
            logger.error(f"【CSV出力エラー】無効な年月フォーマットが指定されました: {target_month_str}")
            return HttpResponse("BadRequest", status=400)

        try:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="attendance_{target_month_str}.csv"'
            response.write(b'\xef\xbb\xbf')  # UTF-8 BOM

            writer = csv.writer(response)
            writer.writerow([
                '対象年月', '勤務日', '社員ID(Email)', '社員名',
                '出勤日時', '退勤日時', '休憩時間', '実労働時間', '残業時間'
            ])

            attendances = Attendance.objects.using(using_db).filter(
                work_date__year=parsed_date.year,
                work_date__month=parsed_date.month,
                delete_flg=0
            ).order_by('work_date', 'user_id')

            # N+1問題対策：att.user への都度アクセスを避け、事前にuser_mapを作成する
            user_ids = {att.user_id for att in attendances if att.user_id}
            user_map = {u.user_id: u for u in User.objects.filter(user_id__in=user_ids)}

            count = 0
            for att in attendances:
                clock_in_str = (
                    timezone.localtime(att.clock_in).strftime('%Y-%m-%d %H:%M:%S') if att.clock_in else '-'
                )
                clock_out_str = (
                    timezone.localtime(att.clock_out).strftime('%Y-%m-%d %H:%M:%S') if att.clock_out else '-'
                )
                user_obj = user_map.get(att.user_id)
                user_name = user_obj.user_name if user_obj else '不明なユーザー'

                writer.writerow([
                    target_month_str,
                    att.work_date.strftime('%Y-%m-%d'),
                    att.user_id,
                    user_name,
                    clock_in_str,
                    clock_out_str,
                    format_td_for_csv(att.break_hours),
                    format_td_for_csv(att.actual_work_hours),
                    format_td_for_csv(att.overtime_hours)
                ])
                count += 1

            logger.info(
                f"【CSV出力成功】出力者: {log_user_id(request.user.user_id)}, "
                f"対象月: {target_month_str}, 出力件数: {count}件"
            )
            return response
        except Exception as e:
            logger.error(f"【CSV出力失敗】原因: {str(e)}", exc_info=True)
            return HttpResponse(f"【CSV出力失敗】", status=500)
            # return HttpResponse("ServerError", status=500)


# =====================================================================
# 8. 有給残日数管理（管理者専用）
# =====================================================================
class LeaveBalanceManageView(AttendanceLoginMixin, View):
    """
    【管理者専用】社員ごとの有給付与日数を年度単位で設定・確認する画面。

    GET: 対象年度（GETパラメータ fiscal_year、未指定時は当年度）の
         全社員の有給残日数一覧を表示。
    POST: 指定社員・年度の付与日数・取得済み日数を登録または更新。
          取得済み日数（used_days）は通常システムが自動管理するが、
          手動補正が必要な場合に管理者が直接入力できる。
    """

    def _check_admin(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            logger.warning(
                f"【不正アクセス】非管理者が有給残日数管理画面にアクセス。ユーザー: {log_user_id(request.user.user_id)}"
            )
            messages.error(request, "管理者権限がありません。")
            return False
        return True

    def get(self, request, *args, **kwargs):
        if not self._check_admin(request):
            return redirect('attendance:dashboard')

        fiscal_year_str = request.GET.get('fiscal_year') or str(get_fiscal_year())
        try:
            fiscal_year = int(fiscal_year_str)
        except (ValueError, TypeError):
            fiscal_year = get_fiscal_year()

        try:
            all_users = User.objects.filter(is_active=True, delete_flg=0).order_by('user_name')
            balances = LeaveBalance.objects.using(using_db).filter(fiscal_year=fiscal_year)
            balance_map = {b.user_id: b for b in balances}

            user_balance_list = [
                {
                    'user': u,
                    'balance': balance_map.get(u.user_id),
                }
                for u in all_users
            ]
        except Exception as e:
            logger.error(f"【有給管理読込エラー】{str(e)}", exc_info=True)
            messages.error(request, "データの取得中にエラーが発生しました。")
            user_balance_list = []

        context = {
            'fiscal_year': fiscal_year,
            'prev_year': fiscal_year - 1,
            'next_year': fiscal_year + 1,
            'user_balance_list': user_balance_list,
        }
        return render(request, 'attendance/leave_balance.html', context)

    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        if not self._check_admin(request):
            return redirect('attendance:dashboard')

        target_user_id  = request.POST.get('user_id', '').strip()
        fiscal_year_str = request.POST.get('fiscal_year', '').strip()
        granted_str     = request.POST.get('granted_days', '').strip()
        used_str        = request.POST.get('used_days', '0').strip() or '0'
        redirect_url    = f"{request.path}?fiscal_year={fiscal_year_str}"

        try:
            fiscal_year = int(fiscal_year_str)
        except (ValueError, TypeError):
            messages.error(request, "年度の指定が不正です。")
            return redirect('attendance:leave_balance_manage')

        try:
            granted_days = Decimal(granted_str)
            used_days    = Decimal(used_str)
            if granted_days < 0 or used_days < 0:
                raise ValueError
        except Exception:
            messages.error(request, "日数の値が不正です（0以上の数値を入力してください）。")
            return redirect(redirect_url)

        target_user = User.objects.filter(user_id=target_user_id, is_active=True).first()
        if not target_user:
            messages.error(request, "指定されたユーザーが見つかりません。")
            return redirect(redirect_url)

        editor = request.user.user_name or request.user.user_id
        try:
            balance, created = LeaveBalance.objects.using(using_db).get_or_create(
                user_id=target_user_id,
                fiscal_year=fiscal_year,
                defaults={
                    'granted_days': granted_days,
                    'used_days': used_days,
                    'create_user': editor,
                    'update_user': editor,
                }
            )
            if not created:
                balance.granted_days = granted_days
                balance.used_days    = used_days
                balance.update_user  = editor
                balance.save(using=using_db)

            action = "登録" if created else "更新"
            logger.info(
                f"【有給残日数{action}】管理者: {log_user_id(request.user.user_id)} → "
                f"社員: {target_user_id}, {fiscal_year}年度, "
                f"付与: {granted_days}日, 取得済: {used_days}日"
            )
            messages.success(
                request,
                f"{target_user.user_name} さんの {fiscal_year}年度 有給残日数を{action}しました。"
            )
        except Exception as e:
            logger.error(f"【有給残日数更新エラー】{str(e)}", exc_info=True)
            messages.error(request, "更新中にエラーが発生しました。")

        return redirect(redirect_url)

