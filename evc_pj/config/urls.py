"""Evc_Pj URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include

from django.conf.urls.static import static # media/img画像表示
from django.conf import settings           # media/img画像表示

from accounts.views import EvcLoginView
from Evc_App.views import health
# admin.site.site_title = 'タイトルタグ' 
# admin.site.site_header = 'サンプルアプリケーション' 
# admin.site.index_title = 'メニュー'
admin.site.site_url = '/admin'

urlpatterns = [
    # path('', include('accounts.urls')),
    path('',EvcLoginView.as_view(),name='login'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('Evc_App/', include('Evc_App.urls')),
    path('Evc_Management/', include('Evc_Management.urls')),
    path('Evc_Owner/', include('Evc_Owner.urls')),
    path('Fms_Ocrform/', include('Fms_Ocrform.urls')),
    path('Fms_fileshare/', include('Fms_fileshare.urls')),
    path("health/", health),

    # path('detail/<pk>/', UserDetailView.as_view(), name='user_detail'),
    # path('edit/', UserEditView.as_view(), name='user_edit'),
] # + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # media/img画像表示
# urlpatterns += static(settings.EVC_URL, document_root=settings.EVC_ROOT) # media/img画像表示
# urlpatterns += static(settings.EVC_HELP_URL, document_root=settings.EVC_HELP_DIR)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # media/img画像表示
    urlpatterns += static(settings.EVC_URL, document_root=settings.EVC_ROOT) # media/img画像表示
    urlpatterns += static(settings.EVC_HELP_URL, document_root=settings.EVC_HELP_DIR)

# if settings.DEBUG_TOOLBAR:
#     import debug_toolbar  # 追加

#     urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]

if settings.USE_GOOGLE_CALENDAR:
    urlpatterns += [path('calendar/', include('Kms_Calendar.urls'))]
    urlpatterns += [path('kintai/', include('Kms_Attendance.urls'))]
