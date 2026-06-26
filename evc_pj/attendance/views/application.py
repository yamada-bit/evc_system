"""
就業申請ビュー（残業 / 有給 / 打刻修正 等）。

WorkApplicationView : 申請一覧の表示（GET）と新規申請の提出（POST）

申請が承認されると Attendance レコードが更新される。
承認処理は ApplicationApprovalView（views/approval.py）が担う。
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from ..models import Attendance, LeaveBalance, WorkApplication
from ..utils.log_utils import log_user_id
from ._base import (
    AttendanceLoginMixin,
    MonthLockMixin,
    LEAVE_COST,
    get_fiscal_year,
    get_pending_leave_days,
    using_db,
)

logger = logging.getLogger(__name__)


class WorkApplicationView(MonthLockMixin, AttendanceLoginMixin, View):
    month_lock_redirect = 'attendance:work_application'
    """
    各種就業申請の入力フォーム表示（GET）と申請提出処理（POST）。

    【申請種別ごとの必須入力項目】
    - OVERTIME（残業申請）:
        requested_overtime_hours（HH:MM 形式）が必須。
        承認されると Attendance.overtime_hours がこの値で上書きされる
        （打刻ベースの自動計算値は使われない）。
    - CORRECTION（打刻修正申請）:
        corrected_clock_in / corrected_clock_out（HH:MM 形式）が必須。
        必要に応じて corrected_break_hours（HH:MM 形式）も指定可。
        承認されると Attendance.clock_in / clock_out が書き換えられ、
        実労働時間・残業時間が打刻ベースで再計算される。
    - PAID_LEAVE / AM_LEAVE / PM_LEAVE / COMP_LEAVE（休暇系）:
        時刻指定不要。reason（申請理由）のみ必須。
        承認されると対象日の Attendance.work_type が変更される。
        全休・代休は出退勤も 0 クリアされる。

    【重複申請防止の二重防御】
    1. ビュー側の事前 exists() チェック: ユーザーに分かりやすいメッセージを出すため。
    2. DB 側の UniqueConstraint（user_id, target_date, apply_type）: 競合状態への最終防御。
       2 の IntegrityError は except IntegrityError でキャッチして適切なメッセージを返す。
    """

    def get(self, request, *args, **kwargs):
        user = request.user
        default_date = request.GET.get('date', '')
        try:
            my_applications = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id
            ).order_by('-target_date', '-create_date')
        except Exception as e:
            logger.error(f"【読込エラー】申請一覧の取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}", exc_info=True)
            messages.error(request, "申請一覧の取得中にエラーが発生しました。")
            my_applications = []

        # 有給残日数（当年度）と承認待ち消費日数を取得して申請フォームに表示する
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

    # 💡 申請重複チェック（exists）からインサートまでをアトミックに保つため、POST 全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        user = request.user
        apply_type = request.POST.get('apply_type')
        target_date_str = request.POST.get('target_date')
        reason = request.POST.get('reason')
        corrected_clock_in_str = request.POST.get('corrected_clock_in') or None
        corrected_clock_out_str = request.POST.get('corrected_clock_out') or None
        corrected_break_hours_str = request.POST.get('corrected_break_hours') or None

        # --- apply_type のホワイトリスト検証（APPLY_TYPE_CHOICES にない値は一律拒否）---
        valid_apply_types = {choice[0] for choice in WorkApplication.APPLY_TYPE_CHOICES}
        if apply_type not in valid_apply_types:
            logger.warning(f"【入力不正】未知の apply_type: {apply_type} ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "申請種別の指定が不正です。")
            return redirect('attendance:work_application')

        # --- target_date のフォーマット検証（不正値をモデル保存前に弾く）---
        try:
            parsed_target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            logger.warning(f"【入力不正】target_date のフォーマット不正: {target_date_str} ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "対象日の形式が不正です。")
            return redirect('attendance:work_application')

        # 🔒 【月次ロック 4/4】MonthLockMixin.month_lock_response() に集約
        target_month_str = parsed_target_date.strftime('%Y-%m')
        if resp := self.month_lock_response(request, target_month_str):
            logger.warning(
                f"[APPLICATION][BLOCKED] 提出済月報への申請試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            return resp

        # --- 有給系申請: 残日数チェック（承認待ちも含めた実質残日数で判定）---
        if apply_type in LEAVE_COST:
            cost = LEAVE_COST[apply_type]
            fiscal_year = get_fiscal_year(parsed_target_date)
            balance = LeaveBalance.objects.using(using_db).select_for_update().filter(
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
            # 承認待ち日数も引いた「実質利用可能日数」で判定する
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

        # --- CORRECTION 申請: 出退勤時刻の必須チェックとフォーマット検証 ---
        if apply_type == 'CORRECTION':
            # 承認時に Attendance を更新するために両フィールドが必須
            if not corrected_clock_in_str or not corrected_clock_out_str:
                logger.warning(
                    f"【入力不正】打刻修正申請に出退勤時刻が未入力 ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "打刻修正申請には修正後の出勤時刻・退勤時刻の両方が必須です。")
                return redirect('attendance:work_application')

            try:
                datetime.strptime(corrected_clock_in_str, '%H:%M')
                datetime.strptime(corrected_clock_out_str, '%H:%M')
            except ValueError:
                logger.warning(
                    f"【入力不正】出退勤修正時刻のフォーマット不正 "
                    f"in:{corrected_clock_in_str} out:{corrected_clock_out_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "修正時刻の形式（HH:MM）が不正です。")
                return redirect('attendance:work_application')

            # 出勤・退勤の前後関係チェック（両値は上記バリデーションで必須を確認済み）
            t_in = datetime.strptime(corrected_clock_in_str, '%H:%M').time()
            t_out = datetime.strptime(corrected_clock_out_str, '%H:%M').time()
            if t_in >= t_out:
                logger.warning(
                    f"【入力不正】修正後の出勤時刻が退勤時刻以降です。ユーザー: {log_user_id(user.user_id)}, "
                    f"in:{corrected_clock_in_str} out:{corrected_clock_out_str}"
                )
                messages.error(request, "修正後の出勤時刻は退勤時刻より前である必要があります。")
                return redirect('attendance:work_application')

        # 💡 【型変換】画面から送られた HH:MM 文字列を DurationField 対応の timedelta 型にキャストする
        corrected_break_hours = None
        if corrected_break_hours_str and apply_type == 'CORRECTION':
            try:
                t = datetime.strptime(corrected_break_hours_str, "%H:%M")
                corrected_break_hours = timedelta(hours=t.hour, minutes=t.minute)
            except ValueError:
                # 不正値を黙って補完するとデータ汚染になるため、エラーとして弾く
                logger.warning(
                    f"【入力不正】休憩時間フォーマット不正: {corrected_break_hours_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "休憩時間の形式（HH:MM）が不正です。")
                return redirect('attendance:work_application')

        # --- OVERTIME 申請: 申請残業時間の検証（承認時にこの値で上書きするため必須）---
        requested_overtime_hours = None
        if apply_type == 'OVERTIME':
            requested_overtime_hours_str = request.POST.get('requested_overtime_hours') or None
            if not requested_overtime_hours_str:
                logger.warning(f"【入力不正】残業申請なのに requested_overtime_hours 未入力 ユーザー: {log_user_id(user.user_id)}")
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
            # exists() チェックとsave()の間に競合状態が起こり得るため、
            # 最終的な防御はモデル側の UniqueConstraint に委ねる。
            # ここでの事前チェックはユーザーへの分かりやすいメッセージ表示のために行う。
            already_exists = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id,
                target_date=parsed_target_date,
                apply_type=apply_type,
            ).exclude(status='REJECTED').exists()

            if already_exists:
                messages.warning(request, "この日付に対する同じ申請はすでに提出されています。")
                return redirect('attendance:work_application')

            # 対象日の既存 Attendance があれば紐付ける（未出勤日の有休申請なども可能）
            related_attendance = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date=parsed_target_date
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
                update_user=creator_name,
            )
            application.save(using=using_db)

            logger.info(f"【申請処理成功】ユーザー: {log_user_id(user.user_id)}, 申請ID: {application.id}")
            messages.success(request, "申請を提出しました。上長の承認をお待ちください。")

        except IntegrityError:
            # DB 側の UniqueConstraint による多重申請防止のフォールバック（競合リクエスト対策）
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
