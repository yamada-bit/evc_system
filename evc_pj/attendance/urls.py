# attendance/urls.py
from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    AdminReportCsvDownloadView,
    AdminReportListView,
    ApplicationApprovalView,
    AttendanceLoginView,
    AttendancePunchView,
    DailyReportDeleteView,
    DailyReportSubmitView,
    DashboardView,
    ExportAttendanceCSVView,
    LeaveBalanceManageView,
    MonthlyReportView,
    WorkApplicationView,
)

# アプリケーションの名前空間を設定（テンプレート内でのURL指定に便利です）
app_name = 'attendance'

urlpatterns = [
    # アプリのトップアクセス（/attendance/）をログインにする
    path('', AttendanceLoginView.as_view(), name='alogin'),
    # アプリのトップアクセス（/attendance/）をダッシュボードにする
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    # 打刻画面 兼 打刻処理アクション
    path('punch/', AttendancePunchView.as_view(), name='attendance_punch'),
    # 日報画面 兼 日報登録・更新アクション
    path('report/', DailyReportSubmitView.as_view(), name='daily_report_submit'),
    # 月報画面のURLを追加
    path('monthly/', MonthlyReportView.as_view(), name='monthly_report'),
    # 各種申請画面のURLを追加
    path('application/', WorkApplicationView.as_view(), name='work_application'),
    # 管理者用：承認画面のURLを追加
    path('approval/', ApplicationApprovalView.as_view(), name='application_approval'),

    path('approval/export-csv/', ExportAttendanceCSVView.as_view(), name='export_attendance_csv'),

    # 2. 管理者日報確認 ＆ CSV出力
    path('admin/reports/', AdminReportListView.as_view(), name='admin_report_list'),
    path('admin/reports/csv/', AdminReportCsvDownloadView.as_view(), name='admin_report_csv'),

    # 4. 日報削除
    path('report/delete/', DailyReportDeleteView.as_view(), name='daily_report_delete'),
    # ログアウト（attendance ログイン画面へリダイレクト）
    path('logout/', LogoutView.as_view(next_page='attendance:alogin'), name='attendance_logout'),
    # 管理者用：有給残日数管理
    path('admin/leave-balance/', LeaveBalanceManageView.as_view(), name='leave_balance_manage'),
]
