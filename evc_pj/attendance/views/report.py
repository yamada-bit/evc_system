"""
日報・月報ビュー。

DailyReportSubmitView  : 日報の登録・編集（GET で表示、POST で保存）
DailyReportDeleteView  : 日報の論理削除（POST 専用）
MonthlyReportView      : 月次カレンダー形式の一覧表示 + 月報提出（GET / POST）

月報提出（MonthlyReportView.post）は当月の打刻・日報・申請に対する
「確定ロック」の起点になる。提出後は他ビューのロックガードが機能し始めるため、
このファイルの変更は必ず関連するロック箇所（punch.py / application.py）と
合わせてレビューすること。
"""
import calendar
import logging
from datetime import date, datetime, timedelta

import jpholiday
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from ..models import Attendance, DailyReport, MonthlyReport, WorkApplication
from ..utils.log_utils import log_user_id
from ._base import AttendanceLoginMixin, MonthLockMixin, LOCKED_STATUSES, format_duration, is_month_locked, using_db

logger = logging.getLogger(__name__)


class DailyReportSubmitView(MonthLockMixin, AttendanceLoginMixin, View):
    month_lock_redirect = 'attendance:monthly_report'
    """
    日報の登録・編集画面（GET）と保存処理（POST）。

    【業務ルール】
    - 1人1日1レコード。既存の日報があれば編集、なければ新規作成（upsert 的な動作）。
    - その日の Attendance が存在すれば日報に紐付けるが、
      Attendance がなくても日報単体の登録は可能
      （客先常駐でシステム打刻を使わない社員の運用などを想定）。
    - 対象月の月報が提出済み / 確定済みの場合は登録・編集ともに不可。

    【GET / POST の日付受け渡し方法の違い】
    GET  : クエリパラメータ ?date=YYYY-MM-DD
    POST : フォームの hidden フィールド target_date
    保存後のリダイレクトも GET 形式（?date=...）に揃えている。
    テンプレートのフォーム実装を変更する場合はこの非対称性に注意すること。
    """

    def get(self, request, *args, **kwargs):
        user = request.user
        date_str = request.GET.get('date')

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localtime(timezone.now()).date()
        except ValueError:
            logger.warning(f"【入力不正】date_str のフォーマット不正: {date_str} ユーザー: {log_user_id(user.user_id)}")
            messages.warning(request, "日付の指定が不正なため、本日の日報を表示します。")
            target_date = timezone.localtime(timezone.now()).date()

        try:
            report = DailyReport.objects.using(using_db).filter(
                user_id=user.user_id, report_date=target_date
            ).first()
            # ロック状態をテンプレートに渡してフォームを非活性化するためのフラグ
            # request を渡すことで同一リクエスト内での重複クエリを防ぐ
            target_month_str = target_date.strftime('%Y-%m')
            is_locked = is_month_locked(user.user_id, target_month_str, request=request)
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
            'is_locked': is_locked,
        }
        return render(request, 'attendance/report.html', context)

    # 💡 get_or_create の挙動と確定済チェックのデータ整合性を担保するため POST 全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        user = request.user
        date_str = request.POST.get('target_date')

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localtime(timezone.now()).date()
        except ValueError:
            logger.warning(f"【入力不正】target_date のフォーマット不正: {date_str} ユーザー: {log_user_id(user.user_id)}")
            messages.warning(request, "日付の指定が不正なため、本日の日付で処理します。")
            target_date = timezone.localtime(timezone.now()).date()

        # 🔒 【月次ロック 2/4】MonthLockMixin.month_lock_response() に集約
        target_month_str = target_date.strftime('%Y-%m')
        if resp := self.month_lock_response(request, target_month_str):
            logger.warning(
                f"[REPORT][BLOCKED] 提出済月報への日報操作試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            return resp

        work_location   = request.POST.get('work_location')
        location_detail = request.POST.get('location_detail', '').strip() or None
        task_summary    = request.POST.get('task_summary')
        comment         = request.POST.get('comment')

        try:
            # select_for_update で行ロックを取得し、二重送信による重複作成を防止する
            report = DailyReport.objects.using(using_db).select_for_update().filter(
                user_id=user.user_id, report_date=target_date
            ).first()
            created = False

            if not report:
                creator_name = user.user_name or user.user_id
                # Attendance があれば紐付け、なければ None のまま（単体での日報登録を許容）
                attendance = Attendance.objects.using(using_db).filter(
                    user_id=user.user_id, work_date=target_date
                ).first()
                # 論理削除済みレコードを再利用する。
                # OneToOneField(attendance) の unique 制約は partial ではないため、
                # delete_flg=1 のレコードが同一 attendance_id を保持したまま残っていると
                # 新規 INSERT 時に tr_daily_report_attendance_id_key 違反が発生する。
                deleted_report = DailyReport.all_objects.using(using_db).select_for_update().filter(
                    user_id=user.user_id, report_date=target_date, delete_flg=1
                ).first()
                if deleted_report:
                    report = deleted_report
                    report.delete_flg = 0
                    report.attendance = attendance
                else:
                    report = DailyReport(
                        user_id=user.user_id,
                        report_date=target_date,
                        attendance=attendance,
                        create_user=creator_name,
                    )
                created = True

            report.task_summary    = task_summary
            report.comment         = comment
            report.work_location   = work_location
            report.location_detail = location_detail
            report.update_user = user.user_name or user.user_id
            report.save(using=using_db)

            action_label = "登録" if created else "更新"
            logger.info(f"【日報保存成功】ユーザー: {log_user_id(user.user_id)}, 日付: {target_date}, 処理: {action_label}")
            messages.success(request, f"{target_date.strftime('%m/%d')} の日報を{action_label}しました。")

        except Exception as e:
            logger.error(f"【日報保存エラー】ユーザー: {log_user_id(user.user_id)} - {str(e)}", exc_info=True)
            messages.error(request, "日報の保存に失敗しました。")

        return redirect(f"{reverse_lazy('attendance:daily_report_submit')}?date={target_date.strftime('%Y-%m-%d')}")


class DailyReportDeleteView(MonthLockMixin, AttendanceLoginMixin, View):
    month_lock_redirect = 'attendance:monthly_report'
    """
    日報の論理削除（POST 専用、独立した表示画面は持たない）。

    【業務ルール】
    - 自分の日報のみ削除可能（user_id=user.user_id でフィルタするため、
      report_id を直接 POST されても他人の日報は削除できない）。
    - 対象月の月報が提出済み / 確定済みの場合は削除不可。
    - 物理削除ではなく delete_flg=1 にセットする論理削除。
    """

    # 💡 削除処理と確定済チェックのデータ整合性を守るため、POST 全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        report_id = request.POST.get('report_id')
        user = request.user

        # report_id が未指定の場合は早期検知して終了（フォーム改ざん対策も兼ねる）
        if not report_id:
            logger.warning(f"【不正削除検知】report_id 未指定。ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "削除対象が指定されていません。")
            return redirect('attendance:monthly_report')

        try:
            # user_id を条件に含めることで、他人の日報 ID を直接 POST された場合も取得できずに終了する
            report = DailyReport.objects.using(using_db).select_for_update().filter(
                id=report_id, user_id=user.user_id
            ).first()
        except (ValueError, ValidationError):
            logger.warning(f"【不正削除検知】report_id が不正な形式です: {report_id} ユーザー: {log_user_id(user.user_id)}")
            messages.error(request, "削除対象の指定が不正です。")
            return redirect('attendance:monthly_report')

        if not report:
            logger.warning(f"【不正削除検知】存在しないか他人の日報削除。ユーザー: {log_user_id(user.user_id)}, ID: {report_id}")
            messages.error(request, "対象の日報が見つからないか、権限がありません。")
            return redirect('attendance:monthly_report')

        # 🔒 【月次ロック 3/4】MonthLockMixin.month_lock_response() に集約
        target_month_str = report.report_date.strftime('%Y-%m')
        if resp := self.month_lock_response(request, target_month_str):
            logger.warning(
                f"[REPORT][BLOCKED] 確定済月の日報削除試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
            )
            return resp

        try:
            target_date_str = report.report_date.strftime('%Y-%m-%d')
            # 物理削除ではなく論理削除フラグを立てる（データ復元・監査ログのため）
            report.delete_flg = 1
            report.update_user = user.user_name or user.user_id
            report.save(using=using_db, update_fields=['delete_flg', 'update_user', 'update_date'])
            logger.info(f"【日報削除成功】ユーザー: {log_user_id(user.user_id)}, 日付: {target_date_str}")
            messages.success(request, f"{target_date_str} の日報を削除しました。")
        except Exception as e:
            logger.error(f"【日報削除エラー】ユーザー: {log_user_id(user.user_id)} - {str(e)}", exc_info=True)
            messages.error(request, "日報の削除中にエラーが発生しました。")

        return redirect('attendance:monthly_report')


class MonthlyReportView(AttendanceLoginMixin, TemplateView):
    """
    月次カレンダー形式の勤務一覧表示（GET）と月報提出（POST）。

    【GET: 表示内容】
    対象月（GETパラメータ month='YYYY-MM'、未指定時は当月）の
    日別データを1行にまとめて返す:
      - 出退勤時刻、実労働 / 残業 / 休憩時間（表示用フォーマット済み）
      - 祝日判定（jpholiday ライブラリ使用）
      - その日の日報の有無・概要
      - その日に紐づく申請のステータス・種別
      - 月報自体のステータス（未提出 / 提出済 / 確定 / 差し戻し）

    【POST: 月報提出（action_type='submit_monthly_report'）】
    対象月の Attendance を集計し、MonthlyReport レコードを
    作成または更新して status='SUBMITTED' にする。
    これにより当月の Attendance / DailyReport / WorkApplication の
    新規登録・編集・削除が各ビューのロックガードでブロックされる。

    【⚠️ 月報提出は「再提出可能」】
    get_or_create 実装のため、一度 SUBMITTED になった月報でも
    再度 POST すれば再集計・再提出できる。
    ただし APPROVED（確定済）への再提出は明示的にブロックしている。
    差し戻し（REJECTED）後の再提出もこの同じ POST 処理を通る。
    """
    template_name = 'attendance/monthly_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        target_month_str = self.request.GET.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')

        # 年月パース（ここで失敗すると以降の全処理が止まるため、個別にハンドリング）
        try:
            parsed_date = datetime.strptime(target_month_str, '%Y-%m')
        except ValueError:
            logger.warning(
                f"【パラメータ不正】month 指定が不正: {target_month_str} ユーザー: {log_user_id(user.user_id)}"
            )
            messages.warning(self.request, "年月の指定が不正なため、当月のデータを表示します。")
            target_month_str = timezone.localtime(timezone.now()).strftime('%Y-%m')
            parsed_date = datetime.strptime(target_month_str, '%Y-%m')

        year, month = parsed_date.year, parsed_date.month
        # 月またぎ処理: 1月の前月は前年12月、12月の翌月は翌年1月
        prev_month = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        context['prev_month_str'] = prev_month.strftime('%Y-%m')
        context['next_month_str'] = next_month.strftime('%Y-%m')
        context['target_month'] = target_month_str
        context['target_year'] = year
        context['target_month_int'] = month

        # 月内データの展開（DB アクセス起因のエラーはここでまとめてキャッチ）
        try:
            _, num_days = calendar.monthrange(year, month)

            # .only() で必要なフィールドだけ取得し DB 負荷を最適化する（values() より型安全）
            attendances = Attendance.objects.using(using_db).filter(
                user_id=user.user_id, work_date__year=year, work_date__month=month
            ).only('work_date', 'clock_in', 'clock_out', 'actual_work_hours', 'overtime_hours', 'break_hours', 'work_type')
            attendance_dict = {att.work_date: att for att in attendances}

            # 日報マッピング（日付をキーに O(1) 参照）
            reports = DailyReport.objects.using(using_db).filter(
                user_id=user.user_id, report_date__year=year, report_date__month=month
            )
            report_dict = {r.report_date: r for r in reports}

            # 申請状況マッピング（1日に複数申請種別がある場合もすべて格納するため dict of list）
            # apply_type でソートして同日複数申請時の表示順を固定する
            applications = WorkApplication.objects.using(using_db).filter(
                user_id=user.user_id, target_date__year=year, target_date__month=month
            ).order_by('target_date', 'apply_type')
            application_dict: dict[date, list] = {}
            for app in applications:
                application_dict.setdefault(app.target_date, []).append(app)

            # 月報のステータス確認（未提出の場合は UNSUBMITTED として扱う）
            monthly_report = MonthlyReport.objects.using(using_db).filter(
                user_id=user.user_id, target_month=target_month_str
            ).first()
            context['monthly_report_status'] = monthly_report.status if monthly_report else 'UNSUBMITTED'
            context['monthly_report_comment'] = monthly_report.approval_comment if monthly_report else ''

            # 1日〜月末までをスイープして画面の行データを生成
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
                # 日報の紐付け（その日の日報があれば概要を渡す）
                rep = report_dict.get(loop_date)
                day_data['has_report'] = rep is not None
                day_data['report_summary'] = rep.task_summary if rep else ''
                # 申請の紐付け（1日に複数申請種別がある場合もすべて渡す）
                day_data['applications'] = application_dict.get(loop_date, [])

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

    # 💡 月次集計から get_or_create による保存までを一貫して守るため、POST 全体をトランザクション化
    @transaction.atomic(using=using_db)
    def post(self, request, *args, **kwargs):
        """月報の確定提出を受け付ける POST ロジック。"""
        user = request.user
        action_type = request.POST.get('action_type')
        target_month_str = request.POST.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')

        if action_type == 'submit_monthly_report':
            try:
                parsed_date = datetime.strptime(target_month_str, '%Y-%m')
            except ValueError:
                logger.warning(
                    f"【パラメータ不正】月報提出時の month 指定が不正: {target_month_str} ユーザー: {log_user_id(user.user_id)}"
                )
                messages.error(request, "年月の指定が不正なため、月報を提出できませんでした。")
                return redirect(f"{request.path}?month={target_month_str}")

            # 管理者が確定（APPROVED）した月報を社員が再提出で上書きできないよう保護する
            existing = MonthlyReport.objects.using(using_db).filter(
                user_id=user.user_id, target_month=target_month_str
            ).first()
            # SUBMITTED は再提出可能。APPROVED のみ社員からの上書きを禁止する。
            if existing and existing.status == 'APPROVED':
                logger.warning(
                    f"[MONTHLY][BLOCKED] 承認済み月報への再提出試行 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
                )
                messages.error(request, f"【操作拒否】{target_month_str}分の月報は既に確定承認済みのため、再提出できません。")
                return redirect(f"{request.path}?month={target_month_str}")

            try:
                # list() で先に全件取得し、count() と集計ループで2回クエリを発行しないようにする
                attendances = list(Attendance.objects.using(using_db).filter(
                    user_id=user.user_id,
                    work_date__year=parsed_date.year,
                    work_date__month=parsed_date.month,
                ))

                # 月報に集計値として保存するサマリーを計算
                total_days = sum(1 for att in attendances if att.clock_in)
                total_work = timedelta(0)
                total_overtime = timedelta(0)
                for att in attendances:
                    if att.actual_work_hours:
                        total_work += att.actual_work_hours
                    if att.overtime_hours:
                        total_overtime += att.overtime_hours

                creator_name = user.user_name or user.user_id

                # 初回提出は get_or_create で新規作成、差し戻し後の再提出は既存レコードを更新
                # delete_flg=0 を条件に含め、論理削除済みレコードを取得しないようにする
                # セーブポイントで囲むことで、二重POSTによる IntegrityError を外側のトランザクションを
                # 壊さずにキャッチできる（PostgreSQL では例外後に同一トランザクションを継続できないため）
                try:
                    with transaction.atomic(using=using_db):
                        monthly_report, created = MonthlyReport.objects.using(using_db).get_or_create(
                            user_id=user.user_id,
                            target_month=target_month_str,
                            delete_flg=0,
                            defaults={
                                'total_work_days': total_days,
                                'total_work_hours': total_work,
                                'total_overtime_hours': total_overtime,
                                'status': 'SUBMITTED',
                                'create_user': creator_name,
                                'update_user': creator_name,
                            }
                        )
                except IntegrityError:
                    logger.warning(
                        f"[MONTHLY][DUPLICATE] 月報の二重送信を検知 - ユーザー: {log_user_id(user.user_id)}, 対象月: {target_month_str}"
                    )
                    messages.error(request, "既に提出済みです。")
                    return redirect(f"{request.path}?month={target_month_str}")

                if not created:
                    # 既存レコード（REJECTED 等）の場合は集計値とステータスを再セット
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

        # 未知の action_type は必ずハンドリングして応答を返す
        # （Djangoのビューでレスポンスを返さない分岐があると500エラーになるため）
        logger.warning(f"【不正パラメータ】未知の action_type: {action_type}（ユーザー: {log_user_id(user.user_id)}）")
        messages.error(request, "不正な操作です。")
        return redirect(f"{request.path}?month={target_month_str}")
