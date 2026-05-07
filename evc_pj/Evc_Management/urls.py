from django.urls import path, include

from . import views
from . import views_user
from . import views_partner
from . import views_accg
from . import views_category
from . import views_summary

app_name = 'Evc_Management' 
urlpatterns = [
    path('user/<user_id>',views_user.EvcUserView.as_view(),name='user'),
    path('user_guest/<user_id>',views_user.EvcUserGuestView.as_view(),name='user_guest'),
    path('user_list/',views_user.EvcUserListView.as_view(),name='user_list'),
    path('evi_history_list/',views.EvcEviHistoryListView.as_view(),name='evi_history_list'),
    path('sconshow/<r_evi_id>/<mode>',views.EvcSConShowView.as_view(),name='sconshow'),
    path('export_history_csv/', views.export_history_csv, name='export_history_csv'),
    path('partner_list/',views_partner.EvcPartnerListView.as_view(),name='partner_list'),
    path('export_partner_csv/', views_partner.export_partner_csv, name='export_partner_csv'),
    path('partner/<partner_id>',views_partner.EvcPartnerView.as_view(),name='partner'),
    path('partner_save/',views_partner.EvcPartnerSaveView.as_view(),name='partner_save'),
    path('download_partner_csv/', views_partner.download_partner_csv, name='download_partner_csv'),
    path('get_partner_list/', views_partner.get_partner_list, name='get_partner_list'),
    path('use_google/', views.EvcUseGoogleView.as_view(), name='use_google'),
    path('account/',views_accg.EvcAccountSaveView.as_view(),name='account'),    # 科目登録
    path('category_list/',views_category.EvcCategoryListView.as_view(),name='category_list'),
    path('category_edit/<folder_id>',views_category.EvcCategoryEditView.as_view(),name='category_edit'),
    path('get_category_list/', views_category.get_category_list, name='get_category_list'),
    path('evidence_summary/',views_summary.EvcEviSummaryView.as_view(),name='evidence_summary'),
    path('evidence_inquiry/<trade_month>/<folder_id>',views_summary.EvcEviInquiryView.as_view(),name='evidence_inquiry'),
]