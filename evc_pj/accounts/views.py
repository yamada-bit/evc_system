# from email.policy import default
# import datetime
# import os
import logging

# from django.shortcuts import resolve_url, redirect
# from django.contrib.auth import authenticate
# from django.contrib.auth import login
# from django.http import HttpResponseRedirect
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
)
from django.urls import reverse, reverse_lazy

# from django.contrib.auth import logout as auth_logout
# from django.shortcuts import render
# Create your views here.
from django.views.generic import RedirectView, TemplateView

# from django.utils import timezone
# from django.utils.timezone import make_aware
from commons.utils import ut_get_client_ip, ut_get_hash
from Evc_App.sv_file import sv_get_owner_ryaku_name, sv_get_select_owner_list
from users.models import EvcUser

from .forms import EvcLoginForm

logger = logging.getLogger(__name__)

# class index(LoginRequiredMixin, TemplateView):
#     template_name = 'accounts/top.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context["form_name"] = "top"
#         return context

# ログイン画面
# Djangoにはアカウント認証のための標準クラスが存在しているため、標準クラスを承継して認証機能を実装
class EvcLoginView(LoginView):
    template_name = 'accounts/FE_Login.html'
    form_class = EvcLoginForm
    """
    LoginView  で定義されているフォーム
    form_class = AuthenticationForm
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_name'] = 'login'
        # if 'owner_id' in self.request.session:
        #     del self.request.session['owner_id']
        return context

    def form_valid(self, form):
        # セッションに入力データを格納する。
        # self.request.session['form_data'] = self.request.POST
        # # ログイン実行時にセッションデータowner_idをクリア
        # if 'owner_id' in self.request.session:
        #     del self.request.session['owner_id']
        self.request.session.clear()    # セッションをクリア

        # try:
            # user_id = form.cleaned_data.get('username')
            # owner_id = EvcUser.objects.get(user_id=user_id).owner_id
            # owner_ryaku_name = SysOwner.objects.get(owner_id=owner_id).owner_ryaku_name
            # logger.info("EvcLoginView : " + (user_id or 'None'))
        # except Exception:
            # logger.exception('EvcLoginView exception ')
            # owner_ryaku_name = ''
        # self.request.session['owner_ryaku_name'] = owner_ryaku_name

        # ログイン情報のログ出力(ハッシュ値を使ってログ出力)
        user_id = form.cleaned_data.get('username')
        user_id_hash = ut_get_hash(user_id)
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'ログインしました: {user_id_hash=}')
        return super().form_valid(form)
    def form_invalid(self, form):
        err = form.errors.as_text()
        logger.warning(f'{ut_get_client_ip(self.request)} '
                       f'ログインに失敗しました {err}')
        return super().form_invalid(form)
    # def form_invalid(self, form):
    #     user_id = form.cleaned_data.get('username')
    #     if check_email(user_id):
    #         messages.error(self.request, "データ登録に失敗しました")
    #     else:
    #         messages.error(self.request, "メールアドレスが正しくありません")
    #     # return self.render_to_response(self.get_context_data(form=form))
    #     return super().form_invalid(form)

# ログアウト機能の処理
class EvcLogoutView(LogoutView):
    template_name = 'accounts/FE_Login.html'
    # # "Log out via GET requests is deprecated and will be removed in Django "
    # # "5.0. Use POST requests for logging out.",
    # # 5.0 ログアウト操作は通常、POSTメソッドを使用するためGETメソッドでは405エラーが発生
    # http_method_names = ["get", "head", "post", "options"]   # GETメソッドを許可する
    # # RemovedInDjango50Warning.
    # def get(self, request, *args, **kwargs):
    #     auth_logout(request)
    #     redirect_to = resolve_url(settings.LOGOUT_REDIRECT_URL)
    #     if redirect_to != request.get_full_path():
    #         # Redirect to target page once the session has been cleared.
    #         return HttpResponseRedirect(redirect_to)
    #     return super().get(request, *args, **kwargs)
    def get_success_url(self):
        self.request.session.clear()    # セッションをクリア
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'ログアウトしました')
        return reverse('accounts:login')

# ログイン後のメインメニュー画面の処理
class EvcMainMenuView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/FE_Menu.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'メインメニュー表示')
        context['process_title'] = ''
        return context

# ログイン後のリダイレクト 権限でURLを分ける
# venv\Lib\site-packages\django\views\generic\base.py
class EvcRedirectView(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        """
        Return the URL redirect to. Keyword arguments from the URL pattern
        match generating the redirect request are provided as kwargs to this
        method.
        """
        try:
            user_id = self.request.user.user_id
            userobj = EvcUser.objects.get(user_id=user_id)
            owner_list = sv_get_select_owner_list(user_id)
            if (not owner_list or len(owner_list) == 0):
                messages.error(self.request, '契約会社情報が正しくありません')
                url = settings.LOGIN_URL   # ログイン画面に戻す
                logger.error(f'{ut_get_client_ip(self.request)} '
                                '契約会社情報が正しくありません')
            elif 1 < len(owner_list):
                url = '/Evc_App/select_owner'
            else:
                # (owner_id, owner_ryaku_name)
                logger.info(f'EvcRedirectView 契約会社 {owner_list[0][0]}')
                self.request.session['owner_id'] = owner_list[0][0]
                url = '/accounts/mainmenu'
            user_id_hs = ut_get_hash(user_id)
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'リダイレクト {user_id_hs} :{userobj.user_authority}: {url=}')
        except Exception:
            messages.error(self.request, 'ログイン情報が正しくありません')
            url = settings.LOGIN_URL   # ログイン画面に戻す
            logger.exception(f'{ut_get_client_ip(self.request)} '
                             'EvcRedirectView exception')
        return url
"""
            if userobj.user_authority == 'スーパーバイザ' or userobj.user_authority == 'グループ管理者':
                owners = sv_get_owner_list(user_id)
                if (not owners or owners.count() == 0):
                    messages.error(self.request, '契約会社情報が正しくありません')
                    url = settings.LOGIN_URL   # ログイン画面に戻す
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                 '契約会社情報が正しくありません')
                elif 1 < owners.count():
                    url = '/Evc_App/select_owner'
                else:
                    logger.info(f'EvcRedirectView 契約会社 {owners[0].owner_id}')
                    self.request.session['owner_id'] = owners[0].owner_id
                    url = '/accounts/mainmenu'
                    # url = '/Evc_App/upload'
            else:
                logger.info(f'EvcRedirectView 契約会社 {userobj.owner_id}')
                self.request.session['owner_id'] = userobj.owner_id
                url = '/accounts/mainmenu'
            user_id_hs = ut_get_hash(user_id)
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'リダイレクト {user_id_hs} :{userobj.user_authority}: {url=}')
"""

# パスワード変更画面
class PasswordChange(LoginRequiredMixin, PasswordChangeView):
    """パスワード変更ビュー"""
    # success_url = reverse_lazy('accounts:password_change_done')
    success_url = reverse_lazy('accounts:login') # 再ログイン
    template_name = 'accounts/password_change.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_name'] = 'password_change'
        owner_id = self.request.session.get('owner_id')
        context['owner_ryaku_name'] = sv_get_owner_ryaku_name(owner_id)
        context['process_title'] = 'パスワード変更'
        # path_lists = [sv_helpurl(), 'password_change_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        return context
    def form_valid(self, form):
        messages.success(self.request, '再ログインしてください。')
        user_id_hash = ut_get_hash(self.request.user.user_id)
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'パスワード変更しました {user_id_hash=}')
        return super().form_valid(form)
    def form_invalid(self, form):
        messages.error(self.request, 'パスワード変更に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'パスワード変更に失敗しました {err}')
        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_invalid(form)

# class PasswordChangeDone(LoginRequiredMixin, PasswordChangeDoneView):
#     """パスワード変更完了"""
#     template_name = 'accounts/password_change_done.html'

#Mixinを使って、自分のプロフィールのみ編集できるようにする
# class OnlyYouMixin(UserPassesTestMixin):
#     raise_exception = True     # set True if raise 403_Forbidden

#     def test_func(self):
#         user = self.request.user
#         return user.pk == self.kwargs['pk'] or user.is_superuser

# class UserDetailView(OnlyYouMixin, DetailView):
#     model = EvcUser
#     template_name = 'accounts/user_detail.html'

# class UserEditView(LoginRequiredMixin, UpdateView):
#     model = EvcUser
#     form_class = UserForm
#     template_name = 'accounts/user_edit.html'
#     #更新後のリダイレクト先
#     success_url = reverse_lazy("accounts:user")

#     # def get_success_url(self):
#     #     return reverse('accounts:user')
#     #     return resolve_url('user_detail', pk=self.request.user.pk)
#     def get_object(self, queryset=None):
#         return EvcUser.objects.get(user_id=self.request.user.user_id)

#     def form_valid(self, form):
#         messages.success(self.request, 'データを登録しました。')
#         return super().form_valid(form)
#     def form_invalid(self, form):
#         messages.error(self.request, "データ登録に失敗しました")
#         return super().form_invalid(form)

# パスワードリセット画面
# class PasswordReset(PasswordResetView):
# パスワードリセット
# class PasswordResetDone(PasswordResetDoneView):
# パスワードリセット
# class PasswordResetConfirm(PasswordResetConfirmView):
# パスワードリセット
# class PasswordResetComplete(PasswordResetCompleteView):

# django.contrib.authアプリが提供するビューを使って、パスワードリセット
# C:\EVCProject\venv\Lib\site-packages\django\contrib\auth\views.py
# djangoが提供するテンプレートを使う
# C:\EVCProject\venv\Lib\site-packages\django\contrib\admin\templates\registration
# C:\EVCProject\Evc_Pj\Template\adminに次の２ファイルをコピーして修正
#   base.html        'ホーム>'メニュー削除
#   base_site.html   タイトル変更

# class PasswordResetView(PasswordContextMixin, FormView):
#     email_template_name = "registration/password_reset_email.html"
#     extra_email_context = None
#     form_class = PasswordResetForm
#     from_email = None
#     html_email_template_name = None
#     subject_template_name = "registration/password_reset_subject.txt"
#     success_url = reverse_lazy("password_reset_done")
#     template_name = "registration/password_reset_form.html"
#     title = _("Password reset")
#     token_generator = default_token_generator
# class PasswordResetDoneView(PasswordContextMixin, TemplateView):
#     template_name = "registration/password_reset_done.html"
#     title = _("Password reset sent")
# class PasswordResetConfirmView(PasswordContextMixin, FormView):
#     form_class = SetPasswordForm
#     post_reset_login = False
#     post_reset_login_backend = None
#     reset_url_token = "set-password"
#     success_url = reverse_lazy("password_reset_complete")
#     template_name = "registration/password_reset_confirm.html"
#     title = _("Enter new password")
#     token_generator = default_token_generator
# class PasswordResetCompleteView(PasswordContextMixin, TemplateView):
#     template_name = "registration/password_reset_complete.html"
#     title = _("Password reset complete")
