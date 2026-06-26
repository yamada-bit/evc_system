from django.conf import settings
from django.contrib import admin
from django.utils import timezone

from .models import Attendance, DailyReport, LeaveBalance, MonthlyReport, WorkApplication

using_db: str = settings.ATTENDANCE_DB


class AttendanceModelAdmin(admin.ModelAdmin):
    """
    勤怠アプリ共通の管理サイト基底クラス。

    全モデルに共通する以下の処理を集約している:
    - get_queryset: kmsdatabase を使用
    - save_model:   kmsdatabase に保存
    - delete_model: 物理削除ではなく論理削除（delete_flg=1）
    - delete_queryset: 一括論理削除
    """

    def get_queryset(self, request):
        return super().get_queryset(request).using(using_db)

    def save_model(self, request, obj, form, change):
        obj.save(using=using_db)

    def delete_model(self, request, obj):
        editor = getattr(request.user, 'user_name', None) or getattr(request.user, 'user_id', None)
        obj.delete_flg = 1
        obj.update_user = editor
        obj.save(using=using_db, update_fields=['delete_flg', 'update_user', 'update_date'])

    def delete_queryset(self, request, queryset):
        editor = getattr(request.user, 'user_name', None) or getattr(request.user, 'user_id', None)
        queryset.using(using_db).update(delete_flg=1, update_user=editor, update_date=timezone.now())


@admin.register(Attendance)
class AttendanceAdmin(AttendanceModelAdmin):
    list_display = ('user_id', 'work_date', 'work_type', 'clock_in', 'clock_out', 'actual_work_hours', 'overtime_hours', 'delete_flg')
    list_filter = ('work_type', 'delete_flg', 'work_date')
    search_fields = ('user_id',)
    date_hierarchy = 'work_date'
    ordering = ('-work_date', 'user_id')
    readonly_fields = ('actual_work_hours', 'overtime_hours', 'break_hours', 'create_date', 'update_date')


@admin.register(DailyReport)
class DailyReportAdmin(AttendanceModelAdmin):
    list_display = ('user_id', 'report_date', 'work_location', 'delete_flg', 'update_date')
    list_filter = ('work_location', 'delete_flg', 'report_date')
    search_fields = ('user_id', 'task_summary')
    date_hierarchy = 'report_date'
    ordering = ('-report_date', 'user_id')
    readonly_fields = ('create_date', 'update_date')


@admin.register(WorkApplication)
class WorkApplicationAdmin(AttendanceModelAdmin):
    list_display = ('user_id', 'target_date', 'apply_type', 'status', 'approver_id', 'approval_date', 'delete_flg')
    list_filter = ('apply_type', 'status', 'delete_flg', 'target_date')
    search_fields = ('user_id', 'reason')
    date_hierarchy = 'target_date'
    ordering = ('-target_date', 'user_id')
    readonly_fields = ('create_date', 'update_date', 'approval_date')


@admin.register(MonthlyReport)
class MonthlyReportAdmin(AttendanceModelAdmin):
    list_display = ('user_id', 'target_month', 'status', 'total_work_days', 'total_work_hours', 'total_overtime_hours', 'delete_flg')
    list_filter = ('status', 'delete_flg', 'target_month')
    search_fields = ('user_id',)
    ordering = ('-target_month', 'user_id')
    readonly_fields = ('create_date', 'update_date')


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(AttendanceModelAdmin):
    list_display = ('user_id', 'fiscal_year', 'granted_days', 'used_days', 'remaining_days', 'delete_flg', 'update_date')
    list_filter = ('fiscal_year', 'delete_flg')
    search_fields = ('user_id',)
    ordering = ('-fiscal_year', 'user_id')
    readonly_fields = ('remaining_days', 'create_date', 'update_date')
