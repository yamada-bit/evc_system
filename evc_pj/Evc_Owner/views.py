import os
import datetime
import logging
import shutil
# import json
# from django.utils import timezone
# from django.utils.timezone import make_aware

from django.shortcuts import render, resolve_url, redirect
from django.views.generic import FormView,UpdateView,ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.conf import settings
from django.urls import reverse,reverse_lazy
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from sequences import get_next_value

from users.models import EvcUser,SysOwner,MtFolder,TtEvidence,MtPartner,HtEvidence
# from users.models import EvcUser,SysOwner,MtFolder,TtEvidence,MtPartner,HtEvidence,MtOwnerUser
from commons.utils import ut_get_hash,ut_get_localdate,ut_get_client_ip

from Evc_Owner.forms import (
    EvcOwnerForm,EvcUpdateOwnerForm,OwnerListForm,
    # SelectableUserListForm
)
# from Evc_App.forms import EvcSelectOwnerForm

from Evc_App.sv_file import (make_dir, sv_get_owner_ryaku_name)

logger = logging.getLogger(__name__)

# 契約会社登録画面
class EvcEditOwnerView(LoginRequiredMixin, FormView):
    model = SysOwner
    form_class = EvcOwnerForm
    template_name = 'Evc_Owner/FE_EditOwner.html'
    #更新後のリダイレクト先
    # success_url = reverse_lazy('Evc_Owner:edit_owner')

    # venv\Lib\site-packages\django\contrib\auth\mixins.py
    # LoginRequiredMixin
    # def dispatch(self, request, *args, **kwargs):
    #     if not request.user.is_authenticated:
    #         return self.handle_no_permission()
    #     if request.user.user_authority != 'スーパーバイザ' and request.user.user_authority != 'グループ管理者':
    #         return self.handle_no_permission()
    #     return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('Evc_Owner:edit_owner')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '契約会社登録'
        context['process_name'] = '登録する'
        # owner_id = self.request.session.get('owner_id')
        # owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        # context['owner_ryaku_name'] = owner_ryaku_name
        return context

    def form_valid(self, form):
        """
        UpdateViewのメソッドをOverride
        Validationに問題がなければ実行される
        formオブジェクトにユーザの入力値が格納されている
        """
        ownerform = form.save(commit=False)
        # owner_id = ownerform.owner_id
        owner_id = '0'  # 新規登録
        ownerobj = SysOwner.objects.filter(owner_id=owner_id).first()
        login_user_id = self.request.user.user_id
        # 新規登録のみ
        kubun = '新規'  # form.cleaned_data.get('kubun')
        user_id = ownerform.charge_email
        user_name = ownerform.charge_name
        user_id_hash = ut_get_hash(user_id)
        # owner_id + '_root' で契約会社のルートフォルダをEVC_ROOTの下に作成
        evc_dir = getattr(settings, 'EVC_ROOT') #.lower()
        categorys = form.cleaned_data.get('categorys')
        # selectable_users = form.cleaned_data.get('selectable_users')

        # userobj = EvcUser.objects.filter(user_id=user_id).first()
        # if userobj:
            # if kubun == '新規':
            #     if userobj.owner_id != owner_id:
            #         messages.error(self.request, '既にユーザが存在します')
            #         return super().form_invalid(form)

        if ownerobj:
            logger.debug(f'{ut_get_client_ip(self.request)} '
                        f'EvcEditOwnerView SysOwner レコードあり {owner_id=}')
            if kubun == '新規':
                messages.error(self.request, '既に契約会社IDが存在します')
                return super().form_invalid(form)
            ownerform.create_date = ut_get_localdate(ownerobj.create_date)
            ownerform.create_user = ownerobj.create_user
            root_folder = os.path.join(evc_dir, owner_id + '_root').replace(os.sep,'/')
        else:
            logger.debug(f'{ut_get_client_ip(self.request)} '
                        f'EvcEditOwnerView SysOwner レコード無し {owner_id=}')
            if kubun == '変更':
                messages.error(self.request, '契約会社が存在しません')
                return super().form_invalid(form)
            owner_id = get_new_owner_id()
            ownerform.owner_id = owner_id
            root_folder = os.path.join(evc_dir, owner_id + '_root').replace(os.sep,'/')
            ownerform.root_folder = root_folder
            ownerform.create_date = datetime.datetime.now()
            ownerform.create_user = login_user_id

        # if kubun == '削除':
        #     if user_exists:
        #         userobj.delete()
        #         messages.success(self.request, 'データを削除しました。')
        try:
            # ownerform.owner_id  = form.cleaned_data.get('owner_id')
            ownerform.update_date = datetime.datetime.now()
            ownerform.update_user = login_user_id
            ownerform.save()
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcEditOwnerView 契約会社を登録しました。 {owner_id=}')
            if not os.path.isdir(root_folder):
                make_dir(root_folder)
            # カテゴリをフォルダ管理マスタに登録
            sv_add_folder(login_user_id, owner_id, root_folder, categorys)
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcEditOwnerView カテゴリを追加しました。 {owner_id=}')
            # 契約会社ユーザマスタに登録
            # sv_add_owner_user(login_user_id, owner_id, selectable_users)

            # グループ管理者をユーザマスタ登録
            pw = sv_create_groupadmin(login_user_id, user_id, user_name, owner_id)
            if pw:
                if pw == 'exist' or pw == 'update':
                    messages.success(self.request, f'契約会社を登録しました。{user_id}')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOwnerView 担当者を更新しました。{user_id_hash=}')
                else:
                    messages.success(self.request, f'担当者を登録しました。{user_id}:{pw}')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOwnerView 担当者を登録しました。 {user_id_hash=}')
            else:
                messages.error(self.request, '担当者登録に失敗しました。')
                logger.error(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOwnerView 担当者登録に失敗しました。 {user_id_hash=}')
        except Exception:
            messages.error(self.request, '契約会社登録に失敗しました。')
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOwnerView exception {owner_id=}')

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, '契約会社登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcEditOwnerView 契約会社登録に失敗しました {err}')

        return super().form_invalid(form)
# 新規owner_id取得
def get_new_owner_id():
    # d = datetime.date.today().strftime('%y%m%d')
    # id = d + '0001'
    now = datetime.datetime.now()
    str_date = now.strftime('%y%m')

    prefix = 'OWNER'
    prefix = 'SO' + str_date

    try:
        num = get_next_value('owner')
    except Exception:   # ValueError
        pre_obj = SysOwner.objects.filter(owner_id__contains=prefix).order_by('-owner_id').first()
        if pre_obj:
            pre_id = pre_obj.owner_id
            num = int(pre_id[-4:]) + 1
        else:
            num = 1
    id = 'SO00000000'
    if num < 9999:
        id = prefix + '{:04d}'.format(num)
    else:
        num = 1
        while num < 10000:
            id = prefix + '{:04d}'.format(num)
            exists = SysOwner.objects.filter(owner_id=id).exists()
            if not exists:
                break
            num += 1
    logger.debug(f'new owner_id={id}')
    return id
# カテゴリをフォルダ管理マスタに登録
def sv_add_folder(login_user_id, owner_id, root_folder, categorys):
    category_list = []
    if categorys:
        list = categorys.replace('\r\n', '\n').split('\n')
        for category in list:
            if category:
                category_list.append([category,'',category])
    if not category_list:
        category_list = [
        ['契約書','keiyaku','契約書'],
        ['注文書','chuumon','注文書'],
        ['注文請書','chuumon','注文請書'],
        ['請求書','seikyuu','請求書'],
        ['領収書','ryoushuu','領収書'],
        ['納品書','nouhin','納品書'],
        ['見積書','mitsumori','見積書'],
        ['見積依頼書','mitsumori','見積依頼書'],
        ['検収書','kenshuu','検収書'],
        ['発注書','hattyuu','発注書'],
        ['その他','other','その他']]
    create_date = datetime.datetime.now() 
    count = len(category_list)
    for i in range(1, count + 1):
        id = owner_id + '_{:03d}'.format(i)  # 契約会社ID+連番（3桁）
        # folder_path = os.path.join(root_folder, category_list[i - 1][2]).replace(os.sep,'/')

        obj = MtFolder(
            folder_id = id,
            owner_id = owner_id,
            category_name = category_list[i - 1][0],
            folder_name = category_list[i - 1][1],
            folder_path = '',
            use_flg = 1,
            notes = '',
            display_order = 0,
            create_user = login_user_id,
            create_date = create_date,
            update_user = login_user_id,
            update_date = create_date,
        )
        try:
            obj.save()
            logger.info(f'MtFolder save folder_id={id}')
        except Exception:
            logger.exception(f'MtFolder save exception folder_id={id}')
    return count
# ユーザマスタ登録
def sv_create_groupadmin(login_user_id, user_id, user_name, owner_id):
    userobj = EvcUser.objects.filter(user_id=user_id).first()
    user_id_hash = ut_get_hash(user_id)
    if userobj:
        # 既存の場合、ユーザ権限のみ変更
        logger.debug(f'EvcEditOwnerView EvcUser レコードあり {user_id_hash=}')
        if userobj.user_authority != 'スーパーバイザ' and userobj.user_authority != 'グループ管理者':
            userobj.user_authority = 'グループ管理者'
            try:
                userobj.save()
                logger.info(f'EvcUser update user_authority {user_id_hash=}')
                new_password = 'update'
            except Exception:
                logger.exception(f'EvcUser update user_authority exception {user_id_hash=}')
                return False
        else:
            new_password = 'exist'
    else:
        logger.debug(f'EvcEditOwnerView EvcUser レコードなし {user_id_hash=}')
        try:
            create_date = datetime.datetime.now()
            idx = user_id.find('@')
            if 0 < idx:
                d = datetime.date.today().strftime('%m%d')
                # パスワード: ＠の前の文字列 + 作成月日
                new_password = user_id[:idx] + d
                # new_password = user_id[:idx]
            else:
                new_password = 'password1'
            # new_password = ut_get_random_password_string(8)

            obj = EvcUser(
                user_id = user_id,
                user_name = user_name,
                password = '',
                user_authority = 'グループ管理者',
                owner_id = owner_id,
                is_active = True,
                delete_flg = 0,
                notes = '',#new_password,
                create_user = login_user_id,
                create_date = create_date,
                update_user = login_user_id,
                update_date = create_date,
            )
            obj.set_password(new_password)
            obj.save()
            logger.info(f'EvcUser save: {user_id_hash=}')
        except Exception:
            logger.exception(f'EvcUser save exception {user_id_hash=}')
            return False
    return new_password
# # 契約会社ユーザマスタに登録
# def sv_add_owner_user(login_user_id, owner_id, selectable_users):
#     user_list = []
#     if selectable_users:
#         list = selectable_users.replace('\r\n', '\n').split('\n')
#         for user in list:
#             if user:
#                 user_list.append([user,'',user])
#     create_date = datetime.datetime.now() 
#     count = len(user_list)
#     for i in range(1, count + 1):
#         # id = owner_id + '_{:03d}'.format(i)  # 契約会社ID+連番（3桁）
#         # folder_path = os.path.join(root_folder, category_list[i - 1][2]).replace(os.sep,'/')

#         obj = MtOwnerUser(
#             owner_id = owner_id,
#             user_id = user_list[i - 1][0],
#             notes = '',
#             create_user = login_user_id,
#             create_date = create_date,
#             update_user = login_user_id,
#             update_date = create_date,
#         )
#         try:
#             obj.save()
#             logger.info(f'MtOwnerUser save')
#         except Exception:
#             logger.exception(f'MtOwnerUser save exception')
#     return count

#契約会社(/変更/削除)画面
class EvcUpdateOwnerView(LoginRequiredMixin, UpdateView):
    model = SysOwner
    form_class = EvcUpdateOwnerForm
    template_name = 'Evc_Owner/FE_UpdateOwner.html'
    # fields = ('owner_name', 'owner_ryaku_name', 'charge_name', 'charge_email','tel_no', 'notes')
    # template_name_suffix = '_update_owner'
    # success_url = reverse_lazy('list')
    def get_success_url(self):
        return reverse('Evc_Owner:update_owner', kwargs={'pk': self.kwargs['pk'] })
    # def get_form_kwargs(self):
    #     kwargs = super().get_form_kwargs()
    #     owner_id = self.kwargs.get('pk')
    #     kwargs['initial'] = {'selectable_users': get_selectable_user(owner_id)}  # CharFieldの初期値を設定
    #     return kwargs
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '契約会社更新'
        context['process_name'] = '更新'
        return context

    def form_valid(self, form):
        if 'btn_delete' in self.request.POST:
            act = 'delete'
        else:
            act = 'upload'
        login_user_id = self.request.user.user_id
        owner_id = self.kwargs.get('pk')
        if act == 'delete':   # 削除
            if owner_id:
                #  契約会社削除/ファイル削除 
                name = sv_delete_owner(owner_id)
            else:
                name = False
            if name:
                messages.success(self.request, f'{name} を削除しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcUpdateOwnerView {name} を削除しました {owner_id=}')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                           'EvcUpdateOwnerView データ削除に失敗しました')

            return redirect('Evc_Owner:owner_list')
        else:
            ownerform = form.save(commit=False)
            ownerform.save()
            # delete_owner_user(owner_id)
            # selectable_users = form.cleaned_data.get('selectable_users')
            # sv_add_owner_user(user_id, owner_id, selectable_users)

            # グループ管理者をユーザマスタ登録
            user_id = ownerform.charge_email
            user_name = ownerform.charge_name
            user_id_hash = ut_get_hash(user_id)

            pw = sv_create_groupadmin(login_user_id, user_id, user_name, owner_id)
            if pw:
                if pw == 'exist' or pw == 'update':
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOwnerView 担当者を更新しました。{user_id_hash=}')
                else:
                    messages.success(self.request, f'担当者を登録しました。{user_id}:{pw}')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOwnerView 担当者を登録しました。 {user_id_hash=}')
            else:
                logger.error(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOwnerView 担当者登録に失敗しました。 {user_id_hash=}')
            messages.info(self.request, '更新しました！')
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcUpdateOwnerView SysOwner を更新しました {owner_id=}')
            return HttpResponseRedirect(self.get_success_url())
    def form_invalid(self, form):
        messages.error(self.request, 'データ更新に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcUpdateOwnerView データ更新に失敗しました {err}')
        return super().form_invalid(form)
# def get_selectable_user(owner_id):
#     objs = MtOwnerUser.objects.filter(owner_id=owner_id)
#     user_list = []
#     for item in objs:
#         user_list.append(item.user_id)
#     return '\n'.join(user_list)

# データ削除
def sv_delete_owner(owner_id):
    try:
        owner_obj = SysOwner.objects.get(owner_id=owner_id)
    except SysOwner.DoesNotExist:
        logger.exception(f'SysOwner DoesNotExist {owner_id=}')
        # raise ValueError('契約会社データ削除　取得エラー ' + partner_id)
        return False
    if owner_obj:
        name = owner_obj.owner_name
        dir = owner_obj.root_folder
        try:
            owner_obj.delete()
            logger.info(f'契約会社を削除しました {owner_id=} {name=}')
            delete_user(owner_id)
            delete_category(owner_id)
            delete_evidence(owner_id)
            delete_partner(owner_id)
            delete_folder(dir)
            # delete_owner_user(owner_id)
        except Exception:
            logger.exception(f'sv_delete_owner exception {owner_id=} {name=}')
            name = False
    else:
        name = False
    return name
# ユーザマスタ削除
def delete_user(owner_id):
    try:
        EvcUser.objects.filter(owner_id=owner_id).delete()
        logger.info(f'ユーザ削除 {owner_id=}')
    except Exception:
        logger.exception(f'EvcUser delete exception {owner_id=}')
# フォルダ管理マスタからカテゴリを削除
def delete_category(owner_id):
    try:
        MtFolder.objects.filter(owner_id=owner_id).delete()
        logger.info(f'フォルダ削除 {owner_id=}')
    except Exception:
        logger.exception(f'MtFolder delete exception {owner_id=}')
# エビデンスを削除
def delete_evidence(owner_id):
    try:
        TtEvidence.objects.filter(owner_id=owner_id).delete()
        logger.info(f'エビデンス削除 {owner_id=}')
    except Exception:
        logger.exception(f'TtEvidence delete exception {owner_id=}')
# エビデンス履歴を削除
def delete_htevidence(owner_id):
    try:
        HtEvidence.objects.filter(owner_id=owner_id).delete()
        logger.info(f'エビデンス履歴削除 {owner_id=}')
    except Exception:
        logger.exception(f'HtEvidence delete exception {owner_id=}')
# 取引先を削除
def delete_partner(owner_id):
    try:
        MtPartner.objects.filter(owner_id=owner_id).delete()
        logger.info(f'取引先削除 {owner_id=}')
    except Exception:
        logger.exception(f'MtPartner delete exception {owner_id=}')

def delete_folder(dir):
    if dir:
        try:
            if os.path.isdir(dir):
                shutil.rmtree(dir)
                logger.info(f'ルートフォルダ削除 {dir=}')
        except Exception:   # ValueError
            logger.exception(f'ルートフォルダ削除 exception {dir=}')
# def delete_owner_user(owner_id):
#     try:
#         MtOwnerUser.objects.filter(owner_id=owner_id).delete()
#     except Exception:   # ValueError
#         logger.exception(f'契約会社対応ユーザ削除 exception {owner_id=}')
# 契約会社一覧
class EvcOwnerListView(LoginRequiredMixin, ListView):
    template_name = 'Evc_Owner/FE_OwnerList.html'
    model = SysOwner
    ordering = 'owner_id'
    paginate_by = 10 # ページネーション 分割数

    def get_queryset(self):
        queryset = super().get_queryset()
        form = OwnerListForm(self.request.GET or None)
        self.form = form 

        if form.is_valid():
            # 検索条件で絞り込み
            # 契約会社を入力
            owner = form.cleaned_data.get('owner')
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcOwnerListView 検索条件で絞り込み {owner=}')
            if owner:
                try:
                    owners = SysOwner.objects.filter(owner_name__contains=owner)
                    list = []
                    for data in owners:
                        list.append(data.owner_id)
                    queryset = queryset.filter(owner_id__in=list)
                except Exception:
                    logger.exception(f'{ut_get_client_ip(self.request)} '
                                    f'EvcOwnerListView SysOwner exception {owner=}')
        else:
            logger.info(f'{ut_get_client_ip(self.request)} '
                        'EvcOwnerListView initial display')
        # 一覧表示内容を取得
        lists = self.set_owner_lists(queryset)
        return lists
            
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form
        context['process_title'] = '契約会社一覧'
        # context['page_size'] = self.paginate_by
        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        return context

    # HTMLのテーブルに設定するデータを取得
    def set_owner_lists(self, queryset):
        lists = []
        for item in queryset:
            data = {
                'owner_id': item.owner_id or '',
                'owner_name': item.owner_name or '',
                'owner_ryaku_name': item.owner_ryaku_name or '',
                'charge_name': item.charge_name or '',
                'charge_email': item.charge_email or '',
                'tel_no': item.tel_no or '',
                'root_folder': item.root_folder or '',
                'notes': item.notes or '',
                'users_number': item.users_number,
            }
            lists.append(data)
        return lists
    # ページネーション分割数
    def get_paginate_by(self, queryset):
        paginate_by = super().get_paginate_by(queryset)
        page_size = self.request.GET.get('page_size')
        if page_size:
            paginate_by = int(page_size)
        return paginate_by
# 契約会社登録で検索ボタンクリックで取引先一覧ダイアログを表示するリスト
def get_owner_list(request):
    name = request.GET.get('owner_name')
    logger.info(f'{ut_get_client_ip(request)} '
                f'契約会社検索ボタンクリック {name=}')
    user_id = request.user.user_id
    owners = SysOwner.objects.filter(owner_name__contains=name).exclude(delete_flg=1)
    owner_list = [{'id': owner.owner_id, 'name': owner.owner_name} for owner in owners]
    return JsonResponse({'owner_list': owner_list})
"""
# 契約会社選択ユーザ一覧
class EvcSelectableUserListView(LoginRequiredMixin, ListView):
    template_name = 'Evc_Owner/FE_SelectableUserList.html'
    model = MtOwnerUser
    ordering = ['owner_id','user_id']
    # paginate_by = 10 # ページネーション 分割数

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        if self.request.method == 'POST':
            # request.POST : requestの情報を辞書型のデータで取得
            form = SelectableUserListForm(self.request.POST or None)
            # 初期値エラーになるためPOSTデータは未使用
            # form = SelectableUserListForm(None)
            owner_id = self.request.POST.get('owner')
        else:
            form = SelectableUserListForm(None)
        form.fields['owner'].choices = self.get_owner_choices()
        form.fields['owner'].initial = owner_id
        self.form = form 
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcSelectableUserListView')

        # 検索条件で絞り込み
        if owner_id:
            try:
                queryset = queryset.filter(owner_id=owner_id)
            except Exception:
                logger.exception(f'{ut_get_client_ip(self.request)} '
                                'EvcSelectableUserListView exception')
        # 一覧表示内容を取得
        lists = self.set_user_lists(queryset)
        return lists
            
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form
        context['process_title'] = '契約会社選択ユーザ一覧'
        # context['page_size'] = self.paginate_by
        page_size = self.request.POST.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        # path_lists = [sv_helpurl(), 'PartnerList_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        return context
    def post(self, request, *args, **kwargs):
        act = self.request.POST.get('submit_action')
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'EvcSelectableUserListView {act=}')

        if act == 'commit':   # 更新
            owner_id = self.request.POST.get('owner')
            json_str = self.request.POST.get('object_list_json')
            if json_str and owner_id:
                rtn = self.save_user(json_str, owner_id)
                if rtn:
                    messages.success(self.request, 'データを登録しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                'EvcSelectableUserListView データを登録しました ')
                else:
                    messages.error(self.request, 'データ登録に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                'EvcSelectableUserListView データ登録に失敗しました')
            else:
                messages.error(self.request, '登録データがありません')
                logger.error(f'{ut_get_client_ip(self.request)} '
                            'EvcSelectableUserListView 登録データがありません ')
        # elif act == 'cancel':
        #     owner_id = self.request.POST.get('owner')
        #     return redirect('accounts:user_edit', owner_id)

        return self.get(request, *args, **kwargs)

    # ユーザ選択リストの設定
    def get_owner_choices(self):
        choices = []
        try:
            objs = SysOwner.objects.all()
            if objs:
                for obj in objs:
                    choices.append((obj.owner_id, obj.owner_name))
                        # choices.append((obj.user_id, obj.user_name))
        except Exception as e:
            logger.exception('EvcSelectableUserListView SysOwner exception')
        return choices

    # HTMLのテーブルに設定するデータを取得
    def set_user_lists(self, queryset):
        lists = []
        for item in queryset:
            data = {
                'owner_id': item.owner_id or '',
                'user_id': item.user_id or '',
                # 'folder_name': item.folder_name or '',
                # 'folder_path': item.folder_path or '',
            }
            lists.append(data)
        if not lists:
            data = {
                'owner_id': '',
                'user_id': '',
                # 'folder_name': '',
                # 'folder_path': '',
            }
            lists.append(data)
        return lists
    def save_user(self, user_json, owner_id):
        lists, id_list = self. get_user_list(user_json)
        rtn = False
        if lists:
            self.delete_users(owner_id, id_list)
            for user in lists:
                rtn = self.add_user(owner_id, user)
        return rtn
    # 編集内容をテキスト情報にマージ
    def get_user_list(self, users_json):
        try:
            lists = []
            id_list = []
            items = json.loads(users_json)
            for item in items:
                user_id = item.get('user_id')
                # folder_path = item.get('folder_path')
                if user_id:
                    data = {
                        'user_id': user_id,
                        # 'folder_path': folder_path
                    }
                    lists.append(data)
                    id_list.append(user_id)
        except Exception:
            logger.exception('EvcSelectableUserListView jsontext exception')
        return lists, id_list
    def delete_users(self, owner_id, id_list):
        try:
            # TtFolder.objects.filter(user_id=user_id).delete()
            MtOwnerUser.objects.filter(owner_id=owner_id).exclude(user_id__in=id_list).delete()
        except Exception:
            logger.exception('EvcSelectableUserListView MtOwnerUser exception')

    def add_user(self, owner_id, user):
        rtn = False
        try:
            user_id = user.get('user_id')
            # folder_path = folder.get('folder_path')
            obj, created = MtOwnerUser.objects.get_or_create(owner_id=owner_id,
                user_id=user_id)
            if obj:
                # obj.folder_path = folder_path
                login_user = self.request.user.user_id
                if created:
                    obj.create_user = login_user
                    obj.create_date = datetime.datetime.now()
                obj.update_user = login_user
                obj.update_date = datetime.datetime.now()
                obj.save()
                rtn = True
        except Exception:
            logger.exception('EvcSelectableUserListView MtOwnerUser exception')
        return rtn    
"""