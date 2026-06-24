from django.contrib import admin

from .models import Attendance, DailyReport, LeaveBalance, MonthlyReport, WorkApplication


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'work_date', 'work_type', 'clock_in', 'clock_out', 'actual_work_hours', 'overtime_hours', 'delete_flg')
    list_filter = ('work_type', 'delete_flg', 'work_date')
    search_fields = ('user_id',)
    date_hierarchy = 'work_date'
    ordering = ('-work_date', 'user_id')
    readonly_fields = ('actual_work_hours', 'overtime_hours', 'break_hours', 'create_date', 'update_date')

    def get_queryset(self, request):
        return super().get_queryset(request).using('kmsdatabase')

    def save_model(self, request, obj, form, change):
        obj.save(using='kmsdatabase')

    def delete_model(self, request, obj):
        obj.delete_flg = 1
        obj.save(using='kmsdatabase', update_fields=['delete_flg', 'update_date'])

    def delete_queryset(self, request, queryset):
        queryset.using('kmsdatabase').update(delete_flg=1)


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'report_date', 'work_location', 'delete_flg', 'update_date')
    list_filter = ('work_location', 'delete_flg', 'report_date')
    search_fields = ('user_id', 'task_summary')
    date_hierarchy = 'report_date'
    ordering = ('-report_date', 'user_id')
    readonly_fields = ('create_date', 'update_date')

    def get_queryset(self, request):
        return super().get_queryset(request).using('kmsdatabase')

    def save_model(self, request, obj, form, change):
        obj.save(using='kmsdatabase')

    def delete_model(self, request, obj):
        obj.delete_flg = 1
        obj.save(using='kmsdatabase', update_fields=['delete_flg', 'update_date'])

    def delete_queryset(self, request, queryset):
        queryset.using('kmsdatabase').update(delete_flg=1)


@admin.register(WorkApplication)
class WorkApplicationAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'target_date', 'apply_type', 'status', 'approver_id', 'approval_date', 'delete_flg')
    list_filter = ('apply_type', 'status', 'delete_flg', 'target_date')
    search_fields = ('user_id', 'reason')
    date_hierarchy = 'target_date'
    ordering = ('-target_date', 'user_id')
    readonly_fields = ('create_date', 'update_date', 'approval_date')

    def get_queryset(self, request):
        return super().get_queryset(request).using('kmsdatabase')

    def save_model(self, request, obj, form, change):
        obj.save(using='kmsdatabase')

    def delete_model(self, request, obj):
        obj.delete_flg = 1
        obj.save(using='kmsdatabase', update_fields=['delete_flg', 'update_date'])

    def delete_queryset(self, request, queryset):
        queryset.using('kmsdatabase').update(delete_flg=1)


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'target_month', 'status', 'total_work_days', 'total_work_hours', 'total_overtime_hours', 'is_closed', 'delete_flg')
    list_filter = ('status', 'is_closed', 'delete_flg', 'target_month')
    search_fields = ('user_id',)
    ordering = ('-target_month', 'user_id')
    readonly_fields = ('create_date', 'update_date', 'closed_date')

    def get_queryset(self, request):
        return super().get_queryset(request).using('kmsdatabase')

    def save_model(self, request, obj, form, change):
        obj.save(using='kmsdatabase')

    def delete_model(self, request, obj):
        obj.delete_flg = 1
        obj.save(using='kmsdatabase', update_fields=['delete_flg', 'update_date'])

    def delete_queryset(self, request, queryset):
        queryset.using('kmsdatabase').update(delete_flg=1)


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'fiscal_year', 'granted_days', 'used_days', 'remaining_days', 'update_date')
    list_filter = ('fiscal_year',)
    search_fields = ('user_id',)
    ordering = ('-fiscal_year', 'user_id')
    readonly_fields = ('remaining_days', 'create_date', 'update_date')

    def get_queryset(self, request):
        return super().get_queryset(request).using('kmsdatabase')

    def save_model(self, request, obj, form, change):
        obj.save(using='kmsdatabase')

    def delete_model(self, request, obj):
        obj.delete(using='kmsdatabase')

    def delete_queryset(self, request, queryset):
        queryset.using('kmsdatabase').delete()
