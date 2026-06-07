from django.urls import path

from . import views, views_report

app_name = 'Kms_Calendar'           # 名前空間の設定
# {% url 'Kms_Calendar:google_calendar' %}   名前空間を指定
urlpatterns = [
    path('google-auth/', views.google_auth, name='google_auth'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
    path('google_logout/', views.google_logout, name='google_logout'),
    path('calendar_model/', views.GoogleCalendarModelView.as_view(), name='calendar_model'),
    path('calendar_model/<int:year>/<int:month>/', views.GoogleCalendarModelView.as_view(), name='calendar_model_ym'),
    path('calendar/', views.GoogleCalendarView.as_view(), name='google_calendar'),
    path('calendar/<int:year>/<int:month>/', views.GoogleCalendarView.as_view(), name='google_calendar_ym'),
    # path('upload/', views.upload_csv_and_register, name='upload'),
    path('export_calendar/<int:year>/<int:month>/', views.export_calendar_model_to_excel, name='export_calendar'),
    path('export_work_schedule/<int:year>/<int:month>/', views.export_work_schedule_to_excel, name='export_work_schedule'),
    path('upload_report/',views_report.KmsUploadReportView.as_view(),name='upload_report'),
    path('report_list/',views_report.KmsReportListView.as_view(),name='report_list'),
    path('edit_report/<report_id>/',views_report.KmsEditReportView.as_view(),name='edit_report'),
]
