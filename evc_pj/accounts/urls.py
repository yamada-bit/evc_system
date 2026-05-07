from django.urls import path, include
from django.contrib.auth import views as auth_views

from . import views

app_name = 'accounts'
urlpatterns = [
    # path('', views.index.as_view(), name='index'),
    # path('',views.EvcLoginView.as_view(),name='login'),
    path('login/',views.EvcLoginView.as_view(),name='login'),
    path('logout/',views.EvcLogoutView.as_view(),name='logout'),
    path('redirect_url/', views.EvcRedirectView.as_view(), name='redirect_url'),
    path('mainmenu/', views.EvcMainMenuView.as_view(), name='mainmenu'),
    # path('index/',views.index.as_view(),name='index'),
    # path('create/',views.EvcUserCreateView.as_view(),name='create'),
    # path('update/',views.EvcUserUpdateView.as_view(),name='update'),
    # path('edit/',views.UserEditView.as_view(),name='edit'),
    path('password_change/', views.PasswordChange.as_view(), name='password_change'),
    # path('password_change/done/', views.PasswordChangeDone.as_view(), name='password_change_done'),
    # パスワードリセットのURL
    # django.contrib.authアプリが提供するビューを使って、パスワードリセットに関連するURLを設定
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    # path('password_reset/', views.PasswordReset.as_view(), name='password_reset'), # 追加
    # path('password_reset/done/', views.PasswordResetDone.as_view(), name='password_reset_done'), # 追加
    # path('reset/<uidb64>/<token>/', views.PasswordResetConfirm.as_view(), name='password_reset_confirm'), # 追加
    # path('reset/done/', views.PasswordResetComplete.as_view(), name='password_reset_complete'), # 追加
 ]