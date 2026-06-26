"""
申請承認・月報確定ビュー（管理者専用）と勤怠 CSV エクスポートビュー。

ApplicationApprovalView : 申請一覧・月報提出一覧の表示（GET）と承認/却下（POST）
ExportAttendanceCSVView : 打刻実績の CSV 出力（UTF-8 BOM 付き）

【⚠️ 申請承認時の Attendance 更新パターンについて】
申請種別によって「通常の save() 経由」と「QuerySet.update() 経由」を使い分けている。

- CORRECTION（打刻修正）: clock_in / clock_out を書き換えた上で
  Attendance.save() の自動計算ロジックに乗せて実労働時間・残業時間を再計算させる。
  → attendance.save() を使う。

- OVERTIME（残業）/ PAID_LEAVE・COMP_LEAVE（有給・代休）:
  「申請された値」をそのまま確定させたいため、save() の自動計算で上書きされないよう
  QuerySet.update() を使って save() をバイパスして直接書き込む。
  → Attendance.objects.filter(pk=...).update(...) を使う。

このルールを無視して安易に attendance.save() に統一してしまうと、
残業申請・有休申請の承認結果が打刻ベースの再計算で消えてしまう
（過去に実際に発生したバグ。詳細は models.py のコメント参照）。
"""
import csv
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from ..models import Attendance, LeaveBalance, MonthlyReport, WorkApplication
from ..utils.db_utils import build_user_map
from ..utils.log_utils import log_user_id
from ..utils.notify_utils import notify_application_result, notify_monthly_report_result
from ._base import (
    AttendanceAccessMixin,
    AttendanceLoginMixin,
    csv_safe,
    is_month_locked,
    LEAVE_COST,
    format_duration,
    get_fiscal_year,
    using_db,
)

logger = logging.getLogger(__name__)


def _get_or_create_attendance(application, approver_name):
    """
    対象申請に紐づく Attendance を取得または新規作成する。
    select_for_update で行ロックを取得し、並行処理での二重作成を防ぐ。
    delete_flg=0 を条件に含め、論理削除済みレコードへの書き込みを防ぐ。
    """
    return Attendance.objects.using(using_db).select_for_update().get_or_create(
        user_id=application.user_id,
        work_date=application.target_date,
        delete_flg=0,
        defaults={'create_user': approver_name},
    )


class ApplicationApprovalView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View):
    """
    【管理者専用】各種申請・月報の承認 / 却下を行う画面。

    test_func() で is_staff または is_superuser のみアクセスを許可。
    権限がない場合は AttendanceAccessMixin.handle_no_permission() が呼ばれ、
    attendance/403.html を返す。

    【POST: action_type による分岐】
    A. 'approve' / 'reject':
        WorkApplication（残業 / 休暇 / 打刻修正申請）の承認・却下。
        承認時の Attendance 反映ロジックは申請種別ごとに異なる
        （このファイル冒頭のモジュール docstring も参照）。

    B. 'approve_month' / 'reject_month':
        MonthlyReport（月報）の確定・差し戻し。
        確定（approve_month）: status='APPROVED'
        差し戻し（reject_month）: status='REJECTED'
"""

    def test_func(self):
        # dispatch() の中で自動実行される権限チェック。False なら handle_no_permission() へ進む
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        logger.warning(
            f"【不正アクセス警告】非管理者が管理者承認ページにアクセスを試みました。"
            f"ユーザーID: {getattr(self.request.user, 'user_id', 'AnonymousUser')}"
        )
        return super().handle_no_permission()

    def get(self, request, *args, **kwargs):
        try:
            # 【マルチDB 高速化】別 DB のユーザー情報は Python インメモリ側で結合する
            # list() で先に全件取得し、if/for ループでクエリが複数回評価されるのを防ぐ
            pending_applications = list(WorkApplication.objects.using(using_db).filter(
                status='PENDING'
            ).order_by('target_date'))
            pending_months = list(MonthlyReport.objects.using(using_db).filter(
                status='SUBMITTED'
            ).order_by('target_month', 'user_id'))

            # 両リストの user_id をまとめて1クエリで取得（重複ユーザーの二重フェッチを防ぐ）
            all_user_ids = {a.user_id for a in pending_applications} | {r.user_id for r in pending_months}
            if all_user_ids:
                user_map = build_user_map(iter(all_user_ids))
                for app in pending_applications:
                    app.assigned_user = user_map.get(app.user_id)
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

    # 💡 WorkApplication と Attendance の複数テーブル更新が連動するため、
    #    with transaction.atomic() で各処理ブロックをアトミック化している
    def post(self, request, *args, **kwargs):
        user = request.user
        action_type = request.POST.get('action_type')
        approver_name = getattr(user, 'user_name', None) or getattr(user, 'user_id', None) or 'ADMIN'

        # === A. 各種申請（残業・有給・打刻修正）の承認・却下 ===
        if action_type in ['approve', 'reject']:
            app_id = request.POST.get('application_id')
            comment = request.POST.get('comment', '')

            if not app_id:
                logger.warning(f"【申請処理エラー】application_id 未指定 - 処理者: {log_user_id(user.user_id)}")
                messages.error(request, "対象の申請が指定されていません。")
                return redirect('attendance:application_approval')

            try:
                with transaction.atomic(using=using_db):
                    application = WorkApplication.objects.using(using_db).select_for_update().get(pk=app_id)
                    applicant_id = application.user_id

                    # 🔒【月次ロック】申請対象月が締め済みの場合は承認・却下を拒否する
                    target_month_str = application.target_date.strftime('%Y-%m')
                    if is_month_locked(application.user_id, target_month_str):
                        logger.warning(
                            f"【月次ロック拒否】申請ID:{app_id}, 対象月:{target_month_str}, "
                            f"申請者:{applicant_id}, 操作者:{log_user_id(user.user_id)}"
                        )
                        messages.error(
                            request,
                            "対象月は既に締め処理が完了しているため、申請を操作できません。",
                        )
                        return redirect('attendance:application_approval')

                    if action_type == 'approve':
                        # 二重承認防止: select_for_update で行ロック取得後に再確認する。
                        # PENDING 以外（APPROVED / REJECTED）の申請は処理をスキップして返す。
                        if application.status != 'PENDING':
                            logger.warning(
                                f"【二重承認防止】既に処理済みの申請への承認試行を検知しました。"
                                f"申請ID:{app_id}, ステータス:{application.status}, "
                                f"処理者:{log_user_id(user.user_id)}"
                            )
                            messages.warning(request, "この申請は既に処理済みです。")
                            return redirect('attendance:application_approval')

                        # 承認前の事前整合性チェック（承認した後にデータ不整合が発覚するのを防ぐ）
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

                        if application.apply_type == 'CORRECTION':
                            # CORRECTION は clock_in / clock_out を書き換えて save() の
                            # 自動計算ロジックに委ねる（実労働時間・残業時間の再計算が必要なため）
                            # 申請時に両フィールドの必須バリデーションを済ませているため、
                            # ここでは None チェックは不要
                            #
                            # tzinfo を combine() に直接渡して settings.TIME_ZONE 固定の aware datetime を生成する。
                            # make_aware() 引数なし呼び出しは get_current_timezone()（ミドルウェア依存）を使うため、
                            # punch.py で使う timezone.localtime(now()) と異なるタイムゾーンになり得る。
                            _local_tz = ZoneInfo(settings.TIME_ZONE)
                            dt_in  = datetime.combine(application.target_date, application.corrected_clock_in,  tzinfo=_local_tz)
                            dt_out = datetime.combine(application.target_date, application.corrected_clock_out, tzinfo=_local_tz)

                            attendance, created = _get_or_create_attendance(application, approver_name)

                            before_in = attendance.clock_in
                            before_out = attendance.clock_out

                            attendance.clock_in  = dt_in
                            attendance.clock_out = dt_out

                            # 🔧 修正: timedelta(0)（休憩なし）は falsy なため、
                            # `if application.corrected_break_hours:` だと条件に入らず無視されてしまう。
                            # None かどうかで明示的に判定する。
                            if application.corrected_break_hours is not None:
                                attendance.break_hours = application.corrected_break_hours
                            attendance.work_type = 'NORMAL'
                            attendance.break_start = None
                            attendance.break_end = None
                            # save() を通すことで Attendance.save() 内の自動計算が実行される
                            attendance.save(using=using_db)

                            logger.info(
                                f"【打刻修正反映成功】承認者: {log_user_id(user.user_id)} -> 申請者: {applicant_id}, "
                                f"対象日: {application.target_date}, "
                                f"clock_in: {before_in} → {attendance.clock_in}, "
                                f"clock_out: {before_out} → {attendance.clock_out}, "
                                f"実労働: {attendance.actual_work_hours}"
                            )

                        elif application.apply_type == 'OVERTIME':
                            # OVERTIME は申請された残業時間でそのまま上書きしたいため、
                            # save() の自動計算をバイパスする QuerySet.update() を使う。
                            # attendance.save() を使うと clock_in/clock_out から再計算されて申請値が消える。
                            attendance, created = _get_or_create_attendance(application, approver_name)
                            before_overtime = attendance.overtime_hours
                            Attendance.objects.using(using_db).filter(pk=attendance.pk).update(
                                overtime_hours=application.requested_overtime_hours,
                                update_user=approver_name,
                                update_date=timezone.now(),
                            )
                            logger.info(
                                f"【残業申請承認・反映成功】承認者: {log_user_id(user.user_id)} -> 申請者: {applicant_id}, "
                                f"対象日: {application.target_date}, "
                                f"overtime_hours: {before_overtime} → {application.requested_overtime_hours}"
                            )

                        # ⚠️ 【申請種別追加時の必須対応】新しい apply_type を APPLY_TYPE_CHOICES に追加した場合は、
                        # 必ずここに elif を追加すること。追加しないと下記 else 節でエラー扱いとなり承認が完了しない。
                        elif application.apply_type in ['PAID_LEAVE', 'AM_LEAVE', 'PM_LEAVE', 'COMP_LEAVE']:
                            attendance, created = _get_or_create_attendance(application, approver_name)

                            # apply_type と work_type は同じ値なので直接マッピング
                            new_work_type = application.apply_type  # 'AM_LEAVE', 'PM_LEAVE', 'COMP_LEAVE', 'PAID_LEAVE'

                            update_fields = {
                                'work_type': new_work_type,
                                'update_user': approver_name,
                                'update_date': timezone.now(),
                            }

                            # 🔧 修正: 全休・代休は出退勤を明示的にクリアし、実労働・残業時間を 0 にセットする。
                            # attendance.save() 経由だと自動計算で「打刻データに基づく値」に上書きされてしまうため、
                            # save() をバイパスする QuerySet.update() で明示的に 0 を確定させる。
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

                            # 有給系（PAID_LEAVE / AM_LEAVE / PM_LEAVE）は残日数を消費させる
                            if application.apply_type in LEAVE_COST:
                                cost = LEAVE_COST[application.apply_type]
                                fiscal_year = get_fiscal_year(application.target_date)
                                balance = LeaveBalance.objects.using(using_db).select_for_update().filter(
                                    user_id=application.user_id, fiscal_year=fiscal_year, delete_flg=0
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
                            # Attendance への反映が行われていないため、承認扱いにせず早期終了する
                            logger.error(
                                f"【承認処理漏れ】未対応の申請種別です。Attendance への反映が行われませんでした。"
                                f" 申請ID: {app_id}, 種別: {application.apply_type}"
                                f" → ApplicationApprovalView の approve 分岐に elif を追加してください。"
                            )
                            messages.error(
                                request,
                                "未対応の申請種別のため承認処理を完了できませんでした。システム管理者にご連絡ください。"
                            )
                            return redirect('attendance:application_approval')

                        # Attendance への反映が確定した後にのみステータスを APPROVED にする
                        application.status = 'APPROVED'

                        logger.info(
                            f"【申請承認】承認者: {log_user_id(user.user_id)} -> 申請者: {applicant_id}, "
                            f"申請ID: {app_id}, 種別: {application.apply_type}"
                        )
                        messages.success(request, "申請を承認しました。")

                    else:
                        # reject の場合は Attendance への反映は行わず、ステータスのみ更新
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

                # トランザクション確定後に通知送信（ロールバック時は送られない）
                notify_application_result(
                    applicant_id=applicant_id,
                    apply_type_display=application.get_apply_type_display(),
                    target_date=application.target_date,
                    status=application.status,
                    comment=comment,
                )

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

        # === B. 月報締めの確定・差し戻し ===
        elif action_type in ['approve_month', 'reject_month']:
            report_id = request.POST.get('report_id')
            comment = request.POST.get('comment', '')

            if not report_id:
                logger.warning(f"【月報処理エラー】report_id 未指定 - 処理者: {log_user_id(user.user_id)}")
                messages.error(request, "対象の月報が指定されていません。")
                return redirect('attendance:application_approval')

            try:
                with transaction.atomic(using=using_db):
                    report = MonthlyReport.objects.using(using_db).select_for_update().get(pk=report_id)
                    target_user_id = report.user_id

                    # 二重操作防止: select_for_update で行ロック取得後にステータスを再確認する。
                    # SUBMITTED 以外（APPROVED / REJECTED）は処理をスキップして返す。
                    if report.status != 'SUBMITTED':
                        logger.warning(
                            f"【二重操作防止】提出済み以外の月報への操作試行を検知しました。"
                            f"レポートID:{report_id}, ステータス:{report.status}, "
                            f"処理者:{log_user_id(user.user_id)}"
                        )
                        messages.error(
                            request,
                            "この月報は既に処理済みか、提出されていないため操作できません。",
                        )
                        return redirect('attendance:application_approval')

                    if action_type == 'approve_month':
                        report.status = 'APPROVED'

                        logger.info(
                            f"【月報確定・締め完了】上長: {log_user_id(user.user_id)} -> 社員: {target_user_id}, "
                            f"対象月: {report.target_month}"
                        )
                        messages.success(request, f"{report.target_month}分 月報を【確定】しました。")

                    else:
                        # 差し戻し: REJECTED に戻してロックを解除する（社員が再提出できる状態にする）
                        report.status = 'REJECTED'

                        logger.info(
                            f"【月報差し戻し】上長: {log_user_id(user.user_id)} -> 社員: {target_user_id}, "
                            f"対象月: {report.target_month}"
                        )
                        messages.warning(request, f"{report.target_month}分 月報を【差し戻し】しました。")

                    report.approval_comment = comment
                    report.update_user = approver_name
                    report.save(using=using_db)

                # トランザクション確定後に通知送信（ロールバック時は送られない）
                notify_monthly_report_result(
                    applicant_id=target_user_id,
                    target_month=report.target_month,
                    status=report.status,
                    comment=comment,
                )

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
            # 未知の action_type は必ずハンドリングして応答を返す
            logger.warning(f"【不正パラメータ】未知の action_type: {action_type}（処理者: {log_user_id(user.user_id)}）")
            messages.error(request, "不正な操作です。")

        return redirect('attendance:application_approval')


class ExportAttendanceCSVView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View):
    """
    【管理者専用】全社員分の勤怠実績（Attendance）を CSV 出力する。

    AdminReportCsvDownloadView（日報CSV、cp932/Shift-JIS 出力）とは別物で、
    こちらは「打刻実績そのもの」を UTF-8 BOM 付きで出力する。

    【BOM 付き UTF-8 の理由】
    Excel でそのまま開いた際に文字化けしないよう BOM を先頭に書き込んでいる。
    cp932（Shift-JIS）ではなく UTF-8 を選択しているのは、
    出力データに cp932 非対応文字（絵文字等）が含まれる可能性への対応。
    """

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        logger.warning(
            f"【不正アクセス警告】非管理者が勤怠CSVダウンロードを試みました。"
            f"ユーザーID: {getattr(self.request.user, 'user_id', 'AnonymousUser')}"
        )
        return super().handle_no_permission()

    def get(self, request, *args, **kwargs):
        target_month_str = request.GET.get('month', timezone.localtime(timezone.now()).strftime('%Y-%m'))

        try:
            parsed_date = datetime.strptime(target_month_str, '%Y-%m')
        except ValueError:
            logger.error(f"【CSV出力エラー】無効な年月フォーマットが指定されました: {target_month_str}")
            return HttpResponse("BadRequest", status=400)

        try:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="attendance_{target_month_str}.csv"'
            response.write(b'\xef\xbb\xbf')  # UTF-8 BOM: Excel での文字化け防止

            writer = csv.writer(response)
            writer.writerow([
                '対象年月', '勤務日', '社員ID(Email)', '社員名',
                '出勤日時', '退勤日時', '休憩時間', '実労働時間', '残業時間',
            ])

            # list() で先に全件取得し、user_ids 収集とデータ出力ループで DB を二重評価しない
            attendances = list(Attendance.objects.using(using_db).filter(
                work_date__year=parsed_date.year,
                work_date__month=parsed_date.month,
            ).order_by('work_date', 'user_id'))

            # N+1 問題対策: att.user への都度アクセスを避け、事前に user_map を作成する
            user_map = build_user_map(att.user_id for att in attendances if att.user_id)

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
                    csv_safe(att.user_id or ''),
                    csv_safe(user_name),
                    clock_in_str,
                    clock_out_str,
                    format_duration(att.break_hours, "0:00"),
                    format_duration(att.actual_work_hours, "0:00"),
                    format_duration(att.overtime_hours, "0:00"),
                ])
                count += 1

            logger.info(
                f"【CSV出力成功】出力者: {log_user_id(request.user.user_id)}, "
                f"対象月: {target_month_str}, 出力件数: {count}件"
            )
            return response

        except Exception as e:
            logger.error(f"【CSV出力失敗】原因: {str(e)}", exc_info=True)
            return HttpResponse("【CSV出力失敗】", status=500)
