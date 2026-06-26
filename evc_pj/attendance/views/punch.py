"""
打刻ビュー（出勤 / 退勤 / 休憩開始 / 休憩終了）。

1日1レコードの Attendance モデルへ打刻時刻を書き込む。
実労働時間・残業時間の計算は Attendance.save() 内で自動実行されるため、
このビューでは計算ロジックを持たない。
"""
import logging
from datetime import timedelta

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from django.utils import timezone
from django.views import View

from ..models import Attendance
from ..utils.log_utils import log_user_id
from ._base import AttendanceLoginMixin, MonthLockMixin, using_db

logger = logging.getLogger(__name__)


class AttendancePunchView(MonthLockMixin, AttendanceLoginMixin, View):
    month_lock_redirect = 'attendance:attendance_punch'
    """
    打刻画面（出勤 / 退勤 / 休憩開始 / 休憩終了）。

    【業務ルール】
    - 1人1日1レコード。打刻順序は 出勤 → (休憩開始 → 休憩終了)* → 退勤 の順を守る。
      順序を無視した打刻（例: 出勤前に退勤）はガード条件で弾かれ、保存されない。
    - 当月の月報が提出済み（SUBMITTED）または確定済み（APPROVED）の場合は
      打刻を一切ブロックする（給与計算の基礎データを確定後に変更させないため）。

    【実労働時間・残業時間の計算タイミング】
    打刻保存（attendance.save()）のたびに Attendance モデルの save() 内で
    実労働時間・残業時間が自動再計算される。計算ロジックを変更する場合は
    models.py の Attendance.save() を参照すること。
    """

    def get(self, request, *args, **kwargs):
        user = request.user
        today = timezone.localtime(timezone.now()).date()
        try:
            attendance = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date=today
            ).first()
        except Exception as e:
            logger.error(
                f"【読込エラー】打刻画面表示用データ取得失敗 - ユーザー: {log_user_id(user.user_id)} - {str(e)}",
                exc_info=True
            )
            messages.error(request, "本日の打刻データの取得に失敗しました。")
            attendance = None
        return render(request, 'attendance/punch.html', {'attendance': attendance})

    # 💡 データの多重送信や瞬時の競合から計算ロジックを守るため、POST 全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        user = request.user
        now_datetime = timezone.localtime(timezone.now())
        today = now_datetime.date()
        punch_type = request.POST.get('punch_type')
        target_month_str = today.strftime('%Y-%m')

        # 🔒 【月次ロック 1/4】MonthLockMixin.month_lock_response() に集約
        if resp := self.month_lock_response(request, target_month_str):
            logger.warning(
                f"[PUNCH][BLOCKED] 提出済月報への打刻試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            return resp

        # 未知の punch_type は早期リターン（不正パラメータ・フォーム改ざん対策）
        valid_punch_types = {'clock_in', 'clock_out', 'break_start', 'break_end'}
        if punch_type not in valid_punch_types:
            logger.warning(f"【不正パラメータ】未知の打刻種別: {punch_type}（ユーザー: {log_user_id(user.user_id)}）")
            messages.error(request, "不正なリクエストです。")
            return redirect('attendance:attendance_punch')

        logger.info(f"【打刻リクエスト】ユーザー: {log_user_id(user.user_id)}, アクション: {punch_type}")

        try:
            # select_for_update で行ロックを取得し、連打・競合状態（race condition）を防止する
            attendance = Attendance.objects.using(using_db).select_for_update().filter(
                user_id=user.user_id, work_date=today
            ).first()
            # 日跨ぎ夜勤対応: 当日レコードが存在せず出勤以外の打刻の場合は、
            # 前日の未退勤レコード（出勤済み・退勤未記録）を検索して処理対象とする
            if not attendance and punch_type != 'clock_in':
                yesterday = today - timedelta(days=1)
                attendance = Attendance.objects.using(using_db).select_for_update().filter(
                    user_id=user.user_id, work_date=yesterday,
                    clock_in__isnull=False, clock_out__isnull=True
                ).first()
            if not attendance:
                # 当日レコードが未作成（初回出勤）の場合はここで新規生成
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
                # valid_punch_types チェック後のフォールバック（理論上到達しないが安全網として残す）
                logger.warning(f"【不正パラメータ】未知の打刻種別: {punch_type}（ユーザー: {log_user_id(user.user_id)}）")
                messages.error(request, "不正なリクエストです。")
                return redirect('attendance:attendance_punch')

            attendance.update_user = user.user_name or user.user_id
            # save() により Attendance モデル内の自動計算ロジックが実行される
            # ネストした atomic により SAVEPOINT を発行し、初回出勤の連打による
            # 重複挿入（IntegrityError）をアウタートランザクションに影響させずキャッチする
            try:
                with transaction.atomic(using=using_db):
                    attendance.save(using=using_db)
            except IntegrityError:
                logger.warning(
                    f"【二重打刻防止】初回出勤の重複挿入をブロック - ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "既に打刻済みです。画面を更新してご確認ください。")
                return redirect('attendance:attendance_punch')
            logger.info(f"【打刻成功】ユーザー: {log_user_id(user.user_id)}, 確定種別: {punch_type}")
            messages.success(request, success_message)

        except Exception as e:
            transaction.set_rollback(True, using=using_db)
            logger.critical(
                f"【打刻システム障害】ユーザー: {log_user_id(user.user_id)}, 種別: {punch_type} - {str(e)}",
                exc_info=True
            )
            messages.error(request, "サーバーエラーにより打刻を保存できませんでした。")

        return redirect('attendance:attendance_punch')
