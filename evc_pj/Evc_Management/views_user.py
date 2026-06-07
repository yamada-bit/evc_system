# import os
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect

# from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse

# from django.utils.timezone import make_aware
# from django.shortcuts import render, resolve_url, redirect
from django.views.generic import FormView, ListView

from commons.utils import (
    ut_get_client_ip,
    ut_get_hash,
    ut_get_localdate,
    ut_get_timezone_now,
)
from Evc_App.sv_file import (
    sv_can_add_adminuser,
    sv_can_add_user,
    sv_get_owner_ryaku_name,
)
from Evc_App.views import OwnerTestMixin
from Evc_Management.forms import EvcUserForm, EvcUserListForm
from users.models import EvcUser

logger = logging.getLogger(__name__)

#ユーザ登録(/変更/削除)画面
class EvcUserView(LoginRequiredMixin, OwnerTestMixin, FormView):
    model = EvcUser
    form_class = EvcUserForm
    template_name = 'Evc_Management/FE_User.html'
    #更新後のリダイレクト先
    # success_url = reverse_lazy('accounts:update')

    def get_success_url(self):
        # user_id = self.kwargs.get('user_id')
        # return reverse('Evc_Management:user', kwargs=dict(user_id=user_id))
        return reverse('Evc_Management:user_list')
        # return resolve_url('user_detail', pk=self.request.user.pk)
    # def get_template_names(self):
    #     # ユーザーのロールやその他の条件に基づいてテンプレートを選択
    #     user = self.request.user
    #     if user.user_authority == "一般":
    #     # extendsと最後の<script></script>だけを変更
    #     # 以外はFE_User.htmlに同じ
    #         return ['Evc_Management/FE_User_Guest.html']
    #     return [self.template_name]  # デフォルトのテンプレートにフォールバック

    # def get_object(self, queryset=None):
    #     return EvcUser.objects.get(user_id=self.request.user.user_id)

    # def get_initial(self):
    #     initial = super().get_initial()
    #     try:
    #         obj_user = EvcUser.objects.get(pk = self.request.user.user_id)
    #         name = obj_user.owner_id
    #         delete_flg = obj_user.delete_flg
    #         note = obj_user.notes
    #     except EvcUser.DoesNotExist:
    #         name = ''
    #         delete_flg = 0
    #         note = ''
    #     initial['notes_area'] = note
    #     initial['kbn'] = delete_flg
    #     return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs.get('user_id')
        # try:
        #     obj_user = EvcUser.objects.get(pk = self.request.user.user_id)
        #     owner_id = obj_user.owner_id
        # except EvcUser.DoesNotExist:
        #     owner_id = ''
        # extra = {'owner_id': owner_id}
        # # コンテキスト情報のキーを追加
        # context.update(extra)
        context['process_title'] = 'ユーザ登録'
        context['process_name'] = '登録'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        # path_lists = [sv_helpurl(), 'User_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        userobj = None
        if user_id != '0':
            try:
                userobj =  EvcUser.objects.get(user_id=user_id)
            except EvcUser.DoesNotExist:
                user_id = '0'
        default_data = self.get_user_info(userobj)
        if 'form' not in kwargs:
            form = EvcUserForm(initial = default_data, update=True if user_id != '0' else None)
            context['form'] = form
        if user_id == '0':
            context['process_name'] = '登録'
            context['kubun'] = '新規'
        else:
            context['process_name'] = '更新'
            if userobj and userobj.delete_flg == 1:
                context['kubun'] = '削除'
            else:
                context['kubun'] = '変更'
        return context

    def form_valid(self, form):
        """
        Validationに問題がなければ実行される
        formオブジェクトにユーザの入力値が格納されている
        """
        owner_id = self.request.session.get('owner_id')
        userform = form.save(commit=False)
        userobj = EvcUser.objects.filter(user_id=userform.user_id).first()
        kubun = form.cleaned_data.get('kubun')
        user_id_hash = ut_get_hash(userform.user_id)
        if userobj:
            logger.debug(f'{ut_get_client_ip(self.request)} '
                        f'EvcUserView EvcUser レコードあり {user_id_hash=}')
            if kubun == '新規':
                messages.error(self.request, '既にユーザが存在します')
                return super().form_invalid(form)
            # try:
            #     create_utc = make_aware(userobj.create_date, timezone=datetime.timezone.utc)
            #     userform.create_date = timezone.localtime(create_utc)
            # except Exception:
            #     userform.create_date = ut_get_timezone_now()
            userform.create_date = ut_get_localdate(userobj.create_date)
            userform.create_user = userobj.create_user
        else:
            logger.debug(f'{ut_get_client_ip(self.request)} '
                        f'EvcUserView EvcUser レコード無し {user_id_hash=}')
            if kubun == '変更':
                messages.error(self.request, 'ユーザが存在しません')
                return super().form_invalid(form)
            user_authority = form.cleaned_data.get('user_authority')
            if user_authority == '管理者':
                # 管理者ユーザ数をチェックする
                adduser = sv_can_add_adminuser(owner_id)
                if not adduser:
                    messages.error(self.request, '管理者ユーザを追加できません。管理者が既に２ユーザ登録されています。')
                    return super().form_invalid(form)
            # ユーザ数をチェックする
            adduser = sv_can_add_user(owner_id)
            if not adduser:
                messages.error(self.request, 'ユーザを追加できません。利用者数の追加を申請してください。')
                return super().form_invalid(form)
            userform.create_date = ut_get_timezone_now()
            userform.create_user = self.request.user.user_id

        if kubun == '削除' and not userobj:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        f'EvcUserView 削除データなし {user_id_hash=}')
        else:
            try:
                userform.owner_id = self.request.session.get('owner_id')
                # userform.owner_id = get_owner_id(self.request.user.user_id)
                if kubun == '新規':
                    new_password = form.cleaned_data.get('password1')
                    userform.set_password(new_password)    # パスワード設定
                if userobj:
                    userform.password = userobj.password
                    # Django設定のデータ
                    userform.last_login = userobj.last_login
                    userform.is_superuser = userobj.is_superuser
                    userform.is_staff = userobj.is_staff
                    # userform.is_active = userobj.is_active
                    userform.date_joined = userobj.date_joined
                if kubun == '削除':
                    userform.is_active = False
                    userform.delete_flg = 1
                else:
                    userform.is_active = True
                    userform.delete_flg = 0
                # 削除ユーザは削除のままで
                if userobj and userobj.delete_flg == 1:
                    userform.is_active = False
                    userform.delete_flg = 1
                    # # 削除ユーザを変更する場合はユーザ数をチェックする
                    # if kubun == '変更':
                    #     adduser = sv_can_add_user(owner_id)
                    #     if not adduser:
                    #         messages.error(self.request, 'ユーザ数が不足しています。変更できません')
                    #         return super().form_invalid(form)

                userform.update_date = ut_get_timezone_now()
                userform.update_user = self.request.user.user_id
                userform.save()
                if kubun == '削除':
                    messages.success(self.request, 'データを削除しました。')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcUserView データを削除しました。 {user_id_hash=}')
                else:
                    messages.success(self.request, 'データを登録しました。')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcUserView データを登録しました。 {user_id_hash=}')
            except Exception:
                messages.success(self.request, 'データ登録に失敗しました。')
                logger.exception(f'{ut_get_client_ip(self.request)} '
                                f'EvcUserView exception {user_id_hash=}')

        # SysOwnerから値を取得する際owner_nameが設定されるのでowner_idに
        # owner = form.cleaned_data.get('owner_cd')
        # userform.owner_id = owner.owner_id
        # DB格納時にModel objectになる時の対応
        # userform.owner_id = self.request.POST.get('owner_cd')

        # new_password = form.cleaned_data.get('password1')
        # user = authenticate(
        #     user_id=self.request.user.user_id,
        #     password=new_password,)
        # if user is not None:
        #     pass
        # else:
        #     #パスワードが変更されている場合
        #     user = EvcUser.objects.get(user_id=self.request.user.user_id)
        #     user.set_password(new_password)
        #     user.save()     # パスワード変更で内部的にログアウトされる
        #     user = authenticate(
        #         user_id=user.user_id,
        #         password=new_password,)
        #     if user is not None:
        #         login(self.request, user)   # 変更したパスワードで内部的にログイン
        #     else:
        #         raise RuntimeError('認証エラー')

        # return super().form_valid(form)   #ログアウトされる
        # return redirect('accounts:update')
        # user_id = form.cleaned_data.get('user_id')
        # url = reverse('Evc_Management:user', kwargs=dict(user_id=user_id))
        # return HttpResponseRedirect(url)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcUserView データ登録に失敗しました {err}')
        return super().form_invalid(form)
    # フォーム表示のために情報を取得
    def get_user_info(self, userobj):
        if userobj:
            default_data = {
                'kubun': '変更' if userobj.delete_flg == 0 else '削除',
                'user_id': userobj.user_id,
                'user_authority': userobj.user_authority,
                'user_name': userobj.user_name,
                'notes': userobj.notes,
                # 'delete_flg': userobj.delete_flg,
            }
        else:
            default_data = {
                'kubun': '新規',
                'user_id': '',
                'user_authority': '一般',
                'user_name': '',
                'notes': '',
                # 'delete_flg': 0,
            }
        return default_data
#ユーザ登録(/変更/削除)画面
class EvcUserGuestView(EvcUserView):
    template_name = 'Evc_Management/FE_User_Guest.html'
    def get_success_url(self):
        user_id = self.kwargs.get('user_id')
        return reverse('Evc_Management:user_guest', kwargs=dict(user_id=user_id))
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = 'ユーザ情報'
        return context
    def form_valid(self, form):
        """
        Validationに問題がなければ実行される
        formオブジェクトにユーザの入力値が格納されている
        """
        owner_id = self.request.session.get('owner_id')
        userform = form.save(commit=False)
        userobj = EvcUser.objects.filter(user_id=userform.user_id).first()
        user_id_hash = ut_get_hash(userform.user_id)
        if userobj:
            logger.debug(f'{ut_get_client_ip(self.request)} '
                        f'EvcUserView EvcUser レコードあり {user_id_hash=}')
            userform.create_date = ut_get_localdate(userobj.create_date)
            userform.create_user = userobj.create_user
        else:
            logger.debug(f'{ut_get_client_ip(self.request)} '
                        f'EvcUserView EvcUser レコード無し {user_id_hash=}')
            messages.error(self.request, 'ユーザが存在しません')
            return super().form_invalid(form)
        try:
            userform.owner_id = userobj.owner_id
            # userform.owner_id = get_owner_id(self.request.user.user_id)
            userform.password = userobj.password
            userform.user_authority = userobj.user_authority
            # Django設定のデータ
            userform.last_login = userobj.last_login
            userform.is_superuser = userobj.is_superuser
            userform.is_staff = userobj.is_staff
            # userform.is_active = userobj.is_active
            userform.date_joined = userobj.date_joined

            userform.update_date = ut_get_timezone_now()
            userform.update_user = self.request.user.user_id
            userform.save()
            messages.success(self.request, 'データを登録しました。')
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcUserView データを登録しました。 {user_id_hash=}')
        except Exception:
            messages.success(self.request, 'データ登録に失敗しました。')
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            f'EvcUserView exception {user_id_hash=}')

        return HttpResponseRedirect(self.get_success_url())

# ユーザ一覧
class EvcUserListView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_Management/FE_UserList.html'
    model = EvcUser
    paginate_by = 10 # ページネーション 分割数

    # def get(self, request, **kwargs):
    #     # アクティブユーザーでなければログインページ
    #     if request.user.user_authority != '管理者':
    #         return redirect('/accounts/login/?next=%s' % request.path)
    #     return super().get(request)
    def get_queryset(self):
        form = EvcUserListForm(self.request.GET or None)
        self.form = form
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcUserListView 検索条件で絞り込み')
        return EvcUser.objects.exclude(user_authority= 'スーパーバイザ').exclude(user_authority= 'グループ管理者').exclude(is_superuser=True).order_by('user_id')
        # return EvcUser.objects.exclude(delete_flg=1).exclude(user_authority= 'スーパーバイザ').exclude(user_authority= 'グループ管理者').exclude(is_superuser=True).order_by('user_id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form
        context['process_title'] = 'ユーザ一覧'
        # context['page_size'] = self.paginate_by
        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        return context

    # ページネーション分割数
    def get_paginate_by(self, queryset):
        paginate_by = super().get_paginate_by(queryset)
        page_size = self.request.GET.get('page_size')
        if page_size:
            paginate_by = int(page_size)
        return paginate_by
