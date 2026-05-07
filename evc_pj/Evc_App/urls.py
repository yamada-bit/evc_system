from django.urls import path, include
from . import views
from . import views_evidence

app_name = 'Evc_App'
urlpatterns = [
    # path('', views.index.as_view(), name='index'),
    # path('pdf_upload',views.PdfUpload.as_view(),name='pdf_upload'),
    path('select_owner/', views.EvcSelectOwnerView.as_view(), name='select_owner'),
    path('upload',views.EvcUploadView.as_view(),name='upload'), 
    path('upload_area/<int:image_no>',views.EvcUploadAreaView.as_view(),name='upload_area'), 
    path('upload_cropimage',views.EvcUploadCropimageView.as_view(),name='upload_cropimage'), 
    # path('upload_complete',views.UploadComplete.as_view(),name='upload_complete'),    
    path('evidence_list/',views_evidence.EvcEviListView.as_view(),name='evidence_list'),
    path('get_duplicate_info/', views_evidence.get_duplicate_info, name='get_duplicate_info'),
    path('sconcreate/<evi_id>',views_evidence.EvcSConCreateView.as_view(),name='sconcreate'),
    path('export_evi_csv/', views_evidence.export_evidence_csv, name='export_evi_csv'),
    path('pdf_merge/<evi_id>', views_evidence.PdfMergeView.as_view(), name='pdf_merge'),

 ]