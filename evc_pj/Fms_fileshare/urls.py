from django.urls import path

from . import views

app_name = 'Fms_fileshare'
urlpatterns = [
    # path('upload/', views.FileUploadView.as_view(), name='upload'),
    # path('list', views.FileListView.as_view(), name='list'),
    # path('view/<int:pk>/', views.file_view, name='view'),
    # path("delete/<int:pk>/", views.FileDeleteView.as_view(), name="file_delete"),
    path('file_upload/',views.FmsFileUploadView.as_view(),name='file_upload'),
    path('file_list/',views.FmsFileListView.as_view(),name='file_list'),
    path('file_edit/<shared_id>/',views.FmsFileEditView.as_view(),name='file_edit'),
]
