"""
管理者専用ビュー（日報一覧・日報CSV・有給残日数管理）。

ファイル名を admin.py にしていないのは、同パッケージの attendance/admin.py
（Django 管理サイト登録ファイル）との混同を避けるため management.py としている。

AdminReportListView       : 全社員の日報一覧（月 / 社員でフィルタ可）
AdminReportCsvDownloadView: 日報データの CSV 出力（Shift-JIS / cp932）
LeaveBalanceManageView    : 社員ごとの有給付与日数の設定・確認

【AdminReportCsvDownloadView の文字コードについて】
社内の Excel 運用に合わせて Shift-JIS（cp932）で出力している。
`response.charset = 'cp932'` を明示しないと、Django の HttpResponse は
実際には UTF-8 でエンコードしてしまう点に注意
（content_type の charset 指定だけでは効かない Django 特有の挙動）。

cp932 非対応文字（絵文字等）が含まれる行は UnicodeEncodeError が発生するため、
行ごとに個別の try-except で捕捉し、errors='replace' で代替文字変換して
再書き込みすることで CSV 全体の出力失敗を防いでいる。
"""
import calendar
import csv
import logging
import urllib.parse
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

import jpholiday

from ..models import Attendance, DailyReport, LeaveBalance
from ..utils.db_utils import build_user_map
from ..utils.log_utils import log_user_id
from ._base import (
    AttendanceAccessMixin,
    AttendanceLoginMixin,
    csv_safe,
    get_fiscal_year,
    using_db,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class AdminReportListView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View):
    """
    【管理者専用】全社員の日報一覧画面。

    対象月（month）・対象社員（user_id）でフィルタ可能。
    test_func() で is_staff または is_superuser のみアクセスを許可。

    【マルチDB 対策】
    DailyReport は kmsdatabase にあるが、User は別 DB にある。
    ORM の JOIN は異なる DB 間では使えないため、
    user_id のリストで User を一括取得し、Python の辞書（user_map）で
    レポートオブジェクトに動的属性として紐付ける（assigned_user）。
    """

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        logger.warning(
            f"【不正アクセス警告】非管理者が管理者専用一覧にアクセスを試みました。"
            f"ユーザーID: {getattr(self.request.user, 'user_id', 'AnonymousUser')}"
        )
        return super().handle_no_permission()

    def get(self, request, *args, **kwargs):
        month_str = request.GET.get('month') or timezone.localtime(timezone.now()).strftime('%Y-%m')
        try:
            target_date = datetime.strptime(month_str, '%Y-%m')
            year, month = target_date.year, target_date.month
        except ValueError:
            logger.warning(f"【パラメータ不正】一覧表示用 month 指定が不正: {month_str}")
            now_local = timezone.localtime(timezone.now())
            year, month = now_local.year, now_local.month
            month_str = now_local.strftime('%Y-%m')

        reports = []
        try:
            queryset = DailyReport.objects.using(using_db).filter(
                report_date__year=year, report_date__month=month
            )

            selected_user_id = request.GET.get('user_id')
            if selected_user_id:
                queryset = queryset.filter(user_id=selected_user_id)

            ordered_qs = queryset.order_by('-report_date', '-id')
            paginator = Paginator(ordered_qs, 50)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)

            # 別 DB のユーザー情報をインメモリで結合（N+1 問題を回避するため一括取得）
            if page_obj.object_list:
                user_map = build_user_map(r.user_id for r in page_obj.object_list if r.user_id)
                for report in page_obj.object_list:
                    # テンプレートで report.assigned_user.user_name のようにアクセスできるよう動的属性に紐付ける
                    report.assigned_user = user_map.get(report.user_id)

        except Exception as e:
            logger.error(f"【読込エラー】管理者用日報一覧の取得失敗 - {str(e)}", exc_info=True)
            messages.error(request, "日報一覧の取得中にエラーが発生しました。")
            page_obj = None

        context = {
            'reports': page_obj,
            'page_obj': page_obj,
            'target_month': month_str,
            'selected_user_id': request.GET.get('user_id'),
        }
        try:
            context['staff_list'] = User.objects.filter(is_active=True, delete_flg=0).order_by('user_name')
        except Exception as e:
            logger.error(f"【読込エラー】社員一覧の取得失敗 - {str(e)}", exc_info=True)
            context['staff_list'] = []

        return render(request, 'attendance/admin_report_list.html', context)


class AdminReportCsvDownloadView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View):
    """
    【管理者限定】全社の日報データを Shift-JIS（cp932）CSV で出力する。

    【cp932 出力の注意点】
    `response.charset = 'cp932'` を明示する必要がある。
    content_type の charset 指定だけでは Django の HttpResponse は
    UTF-8 でエンコードしてしまうため効果がない（Django 固有の挙動）。

    【cp932 非対応文字の行ごとフォールバック処理】
    絵文字などの cp932 非対応文字が日報本文に含まれていた場合、
    通常の writerow() で UnicodeEncodeError が発生する。
    該当行のみ `errors='replace'` で代替文字に変換して再書き込みすることで、
    1行のエラーで CSV 全体の出力が失敗しないようにしている。
    """

    def test_func(self):
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

        try:
            target_date = datetime.strptime(month_str, '%Y-%m')
        except ValueError:
            logger.warning(f"【CSV出力エラー】無効な年月フォーマットが指定されました: {month_str}")
            messages.error(request, "年月の指定が不正です。")
            return redirect('attendance:admin_report_list')

        try:
            queryset = DailyReport.objects.using(using_db).filter(
                report_date__year=target_date.year, report_date__month=target_date.month
            )
            if selected_user_id:
                queryset = queryset.filter(user_id=selected_user_id)

            reports = list(queryset.order_by('report_date'))

            response = HttpResponse(content_type='text/csv')
            # content_type だけでなく response.charset も明示的に設定する
            # （HttpResponse の実エンコード処理は response.charset を参照するため）
            response.charset = 'cp932'
            filename = f"daily_reports_{month_str}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            writer = csv.writer(response)
            writer.writerow(['日付', '社員ID', '氏名', '勤務場所', '業務内容', '所感・連絡事項'])

            if reports:
                user_map = build_user_map(r.user_id for r in reports if r.user_id)

                for r in reports:
                    user_obj = user_map.get(r.user_id)
                    user_name = user_obj.user_name if user_obj else "所属不明"
                    # 改行を含む文字列をセル内に格納すると CSV が壊れるため、スペースに置換する
                    safe_summary = (r.task_summary or '').replace('\r\n', ' ').replace('\n', ' ')
                    safe_comment = (r.comment or '').replace('\r\n', ' ').replace('\n', ' ')
                    work_location_display = (
                        r.get_work_location_display() if hasattr(r, 'get_work_location_display')
                        else (r.work_location or '未指定')
                    )
                    # 数式インジェクション対策: ユーザー由来の全セルをサニタイズする
                    row = [
                        r.report_date.strftime('%Y/%m/%d'),
                        csv_safe(r.user_id or ''),
                        csv_safe(user_name),
                        csv_safe(work_location_display),
                        csv_safe(safe_summary),
                        csv_safe(safe_comment),
                    ]
                    try:
                        # response.charset が cp932 のため、ここでは事前エンコードせず素の文字列を渡す
                        writer.writerow(row)
                    except UnicodeEncodeError:
                        # cp932 非対応文字（絵文字など）が含まれる行のみ代替文字に変換して再書き込み
                        logger.warning(
                            f"【CSV文字化け回避】社員ID:{r.user_id} 日付:{r.report_date} "
                            f"の内容に cp932 非対応文字を検知したため代替文字で出力します。"
                        )
                        writer.writerow([
                            v.encode('cp932', errors='replace').decode('cp932') for v in row
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


class LeaveBalanceManageView(AttendanceAccessMixin, AttendanceLoginMixin, UserPassesTestMixin, View):
    """
    【管理者専用】社員ごとの有給付与日数を年度単位で設定・確認する画面。

    GET: 対象年度（GETパラメータ fiscal_year、未指定時は当年度）の
         全社員の有給残日数一覧を表示する。

    POST: 指定社員・年度の付与日数・取得済み日数を登録または更新する。
          取得済み日数（used_days）は通常、申請承認時にシステムが自動管理するが、
          手動補正が必要な場合に管理者が直接入力できる。
    """

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        logger.warning(
            f"【不正アクセス警告】非管理者が有給残日数管理画面にアクセスを試みました。"
            f"ユーザーID: {getattr(self.request.user, 'user_id', 'AnonymousUser')}"
        )
        return super().handle_no_permission()

    def get(self, request, *args, **kwargs):

        fiscal_year_str = request.GET.get('fiscal_year') or str(get_fiscal_year())
        try:
            fiscal_year = int(fiscal_year_str)
        except (ValueError, TypeError):
            fiscal_year = get_fiscal_year()

        try:
            all_users = User.objects.filter(is_active=True, delete_flg=0).order_by('user_name')
            balances = LeaveBalance.objects.using(using_db).filter(fiscal_year=fiscal_year)
            balance_map = {b.user_id: b for b in balances}

            # 全社員リストと有給残日数を紐付けた表示用リストを作成
            # LeaveBalance が未登録の社員も一覧には表示する（balance=None で区別）
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

        target_user = User.objects.filter(user_id=target_user_id, is_active=True, delete_flg=0).first()
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
                    'delete_flg': 0,
                    'create_user': editor,
                    'update_user': editor,
                }
            )
            if not created:
                balance.granted_days = granted_days
                balance.used_days    = used_days
                balance.delete_flg   = 0
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


# ---------------------------------------------------------------------------
# 勤務表プレビュー（本人用）
# ---------------------------------------------------------------------------

class SchedulePreviewView(AttendanceLoginMixin, View):
    """
    指定年月の勤務表プレビューを表示する。
    日報の「外出先・場所」「業務内容」を含めた1か月分の一覧を表示し、
    Excel ダウンロードへの導線を提供する。
    """

    def get(self, request, year: int, month: int):
        user = request.user

        try:
            _, num_days = calendar.monthrange(year, month)
        except Exception:
            messages.error(request, "年月の指定が不正です。")
            return redirect('attendance:monthly_report')

        prev_month = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
        next_month = date(year + 1,  1, 1) if month == 12 else date(year, month + 1, 1)

        try:
            attendances = (
                Attendance.objects.using(using_db)
                .filter(user_id=user.user_id, work_date__year=year, work_date__month=month)
                .only('work_date', 'work_type', 'clock_in', 'clock_out',
                      'actual_work_hours', 'overtime_hours')
            )
            att_map = {a.work_date: a for a in attendances}

            reports = (
                DailyReport.objects.using(using_db)
                .filter(user_id=user.user_id, report_date__year=year, report_date__month=month)
                .only('report_date', 'task_summary', 'location_detail')
            )
            rep_map = {r.report_date: r for r in reports}

            WEEKDAY_JA = ['月', '火', '水', '木', '金', '土', '日']
            days = []
            for d in range(1, num_days + 1):
                loop_date = date(year, month, d)
                att = att_map.get(loop_date)
                rep = rep_map.get(loop_date)
                wd = loop_date.weekday()   # 0=月 … 6=日
                is_holiday = jpholiday.is_holiday(loop_date)
                is_sunday  = wd == 6
                days.append({
                    'work_date':       loop_date,
                    'weekday':         WEEKDAY_JA[wd],
                    'is_sunday':       is_sunday,
                    'is_saturday':     wd == 5,
                    'is_holiday':      is_holiday,
                    'is_red':          is_holiday or is_sunday,
                    'work_type':       att.get_work_type_display() if att else '',
                    'clock_in':        att.clock_in  if att else None,
                    'clock_out':       att.clock_out if att else None,
                    'actual_work_hours': att.actual_work_hours if att else None,
                    'overtime_hours':  att.overtime_hours  if att else None,
                    'location_detail': rep.location_detail if rep else '',
                    'task_summary':    rep.task_summary    if rep else '',
                })
        except Exception as e:
            logger.error(f"【プレビューエラー】{log_user_id(user.user_id)} {year}/{month} - {e}", exc_info=True)
            messages.error(request, "データの取得中にエラーが発生しました。")
            days = []

        context = {
            'year':  year,
            'month': month,
            'target_month_str': f'{year}-{month:02d}',
            'prev_year':  prev_month.year,
            'prev_month': prev_month.month,
            'next_year':  next_month.year,
            'next_month': next_month.month,
            'days':  days,
            'user_name': user.user_name or user.user_id,
        }
        return render(request, 'attendance/schedule_preview.html', context)


# ---------------------------------------------------------------------------
# 勤務表 Excel ダウンロード（本人用）
# ---------------------------------------------------------------------------

class ExportAttendanceExcelView(AttendanceLoginMixin, View):
    """
    ログインユーザー自身の指定月の勤務表 Excel をダウンロードする。

    テンプレートファイル:
      settings.ATTENDANCE_EXCEL_TEMPLATE_DIR/勤務表テンプレート_{year}.xlsx
      ※ 1〜3月は前年度テンプレートを使用
    """

    def get(self, request, year: int, month: int):
        from ..services.excel_export import export_attendance_excel
        user = request.user
        user_name = user.user_name or user.user_id

        try:
            output = export_attendance_excel(user.user_id, year, month, user_name)
        except Exception:
            logger.exception(
                f'【勤務表Excel生成エラー】ユーザー: {log_user_id(user.user_id)} {year}/{month:02d}'
            )
            messages.error(request, '勤務表の生成中にエラーが発生しました。管理者に連絡してください。')
            return redirect('attendance:monthly_report')

        if output is None:
            messages.error(
                request,
                f'{year}年度の勤務表テンプレートが見つかりません。管理者に連絡してください。'
            )
            return redirect('attendance:monthly_report')

        filename = f'勤務表_{user_name}_{year}{month:02d}.xlsx'
        encoded_filename = urllib.parse.quote(filename)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
        logger.info(f'【勤務表Excel出力】ユーザー: {log_user_id(user.user_id)} {year}/{month:02d}')
        return response
