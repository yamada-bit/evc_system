"""
Definition of urls for SbKintai.
"""
from django.urls import path

from Kms_Attendance import views, views_report

app_name = 'Kms_Attendance'     # 名前空間の設定
# {% url 'Kms_Attendance:index' %}    名前空間を指定
urlpatterns = [
    # path('', include('Kms_Attendance.urls')),
    path('', views.KLoginView.as_view(), name='klogin'),
    path('index/', views.IndexView.as_view(), name='index'),
    path('result/', views.ResultView.as_view(), name='result'),
    path('add_emp/', views.AddEmp.as_view(), name='add_emp'),
    path('edit_emp/', views.EditEmp.as_view(), name='edit_emp'),
    path('monthly/', views.MonthCalendar.as_view(), name='monthly'),
    path('monthly/<int:year>/<int:month>/<int:mode>/', views.MonthCalendar.as_view(), name='monthly'),
    path('monthly/<int:year>/<int:month>/<int:mode>/<int:counter>/', views.MonthCalendar.as_view(), name='monthly'),
    path('timestamp_stat/<int:year>/<int:month>/<int:day>/<int:mode>/', views.TimeStampStat.as_view(), name='timestamp_stat'),
    path('paid_holiday/<int:year>/<int:mode>/', views_report.PaidHoliday.as_view(), name='paid_holiday'),
    path('paid_holiday_edit/<int:year>/', views_report.PaidHolidayEdit.as_view(), name='paid_holiday_edit'),
    path('daily/', views_report.ReportDaily.as_view(), name='daily'),
    path('daily/<int:year>/<int:month>/', views_report.ReportDaily.as_view(), name='daily'),
    path('daily_edit/<int:year>/<int:month>/<int:day>/', views_report.ReportDailyEdit.as_view(), name='daily_edit'),
    #path('pdf/', views.PdfViewer.as_view(), name='pdf'),         # PDF出力
    path('approval/', views.Approval.as_view(), name='approval'),
    path('approval/<int:year>/<int:month>/<int:day>/', views.Approval.as_view(), name='approval'),
    # path('approval_emp/<int:year>/<int:month>/', views.ApprovalEmp.as_view(), name='approval_emp'),
    # path('approval_stat/<int:year>/<int:month>/<int:day>/<int:mode>/', views.ApprovalStat.as_view(), name='approval_stat'),
    path('request_edit/<int:year>/<int:month>/<int:day>/<int:mode>/', views.RequestEdit.as_view(), name='request_edit'),
    path('request_edit/<int:year>/<int:month>/<int:day>/<int:mode>/<int:counter>/', views.RequestEdit.as_view(), name='request_edit'),
    path('report/', views_report.Report.as_view(), name='report'),
    path('report_getuji/', views_report.ReportGetuji.as_view(), name='report_getuji'),
    path('report_getuji/<int:year>/<int:month>/', views_report.ReportGetuji.as_view(), name='report_getuji'),
    path('csv_export/<int:year>/<int:month>/', views_report.CsvExport, name='csv_export'),
    path('pdf_view/<int:year>/<int:month>/', views_report.PdfView.as_view(), name='pdf_view'),
    path('report_today/', views_report.ReportToday.as_view(), name='report_today'),
    path('report_tukishime/', views_report.ReportTukishime.as_view(), name='report_tukishime'),
    path('report_tukishime/<int:year>/<int:month>/', views_report.ReportTukishime.as_view(), name='report_tukishime'),
    path('report_holiday/', views_report.ReportHoliday.as_view(), name='report_holiday'),
    path('report_holiday/<int:year>/', views_report.ReportHoliday.as_view(), name='report_holiday'),
    path('output_month/', views_report.OutputMonth.as_view(), name='output_month'),
    path('output_day/', views_report.OutputDay.as_view(), name='output_day'),

    # # 詳細画面および更新画面は1レコードを参照するため、pathの第一引数はレコードID(PK)と紐付ける
    # path('', views.CompanyList.as_view(), name='list'),                         #一覧画面
    # path('detail/<int:pk>/',views.CompanyDetail.as_view(),name='detail'),       #詳細画面
    # path('create/',views.CompanyCreateView.as_view(),name='create'),            #新規登録画面(会社)
    # path('create2/',views.CompanyCreateView2.as_view(),name='create2'),         #新規登録画面(従業員)
    # path('update/<int:pk>/',views.CompanyUpdateView.as_view(),name='update'),   #更新画面(会社)
    # path('update2/<int:pk>/',views.CompanyUpdateView2.as_view(),name='update2'),#更新画面(従業員)
    # path('delete/<int:pk>/',views.CompanyDeleteView.as_view(),name='delete'),   #削除画面(会社)
]
