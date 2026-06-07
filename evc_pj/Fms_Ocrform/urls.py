from django.urls import path

from . import views, views_ocrdata

app_name = 'Fms_Ocrform'
urlpatterns = [
    path('upload_ocrform/<int:data_type>/',views.EvcSaveOcrformView.as_view(),name='upload_ocrform'),
    path('ocrform_list/<int:data_type>/',views.EvcOcrformListView.as_view(),name='ocrform_list'),
    path('edit_ocrform/<int:data_type>/<ocrform_id>/<int:image_no>/',views.EvcEditOcrformView.as_view(),name='edit_ocrform'),
    # path('upload_entry/',views_entry.EvcUploadEntryView.as_view(),name='upload_entry'),
    # path('entry_list/',views_entry.EvcEntryListView.as_view(),name='entry_list'),
    # path('edit_entry/<entry_id>/<int:image_no>',views_entry.EvcEditEntryView.as_view(),name='edit_entry'),
    # path('upload_timesheet/',views_timesheet.EvcUploadTimesheetView.as_view(),name='upload_timesheet'),
    # path('timesheet_list/',views_timesheet.EvcTimesheetListView.as_view(),name='timesheet_list'),
    # path('timesheet_edit/<timesheet_id>/',views_timesheet.EvcEditTimesheetView.as_view(),name='timesheet_edit'),
    path('upload_ocrdata/<str:model_name>/',views_ocrdata.EvcUploadOcrDataView.as_view(),name='upload_ocrdata'),
    path('ocrdata_list/<str:model_name>/',views_ocrdata.EvcOcrDataListView.as_view(),name='ocrdata_list'),
    path('ocrdata_edit/<str:model_name>/<ocrdata_id>/<int:image_no>/',views_ocrdata.EvcEditOcrDataView.as_view(),name='ocrdata_edit'),
    path('export_zip/<ocrdata_id>/<int:image_no>/', views_ocrdata.export_zip, name='export_zip'),

 ]
