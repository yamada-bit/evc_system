# import os
# import datetime
# import calendar
# import csv
import logging

# from io import TextIOWrapper
# from operator import attrgetter
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse

# from django.utils import timezone
# from django.utils.timezone import make_aware
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, ListView

from commons.utils import ut_get_client_ip, ut_get_localdate, ut_get_timezone_now
from Evc_App.sv_file import sv_get_owner_ryaku_name
from Evc_App.views import OwnerTestMixin
from Evc_Management.forms import EvcCategoryForm, EvcCategoryListForm
from users.models import MtFolder

logger = logging.getLogger(__name__)

# カテゴリ一覧
class EvcCategoryListView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_Management/FE_CategoryList.html'
    model = MtFolder
    ordering = ['-display_order','folder_id']
    paginate_by = 10 # ページネーション 分割数

    def get_queryset(self):
        queryset = super().get_queryset()
        owner_id = self.request.session.get('owner_id')
        # owner_id = get_owner_id(self.request.user.user_id)
        queryset = queryset.filter(owner_id=owner_id)
        form = EvcCategoryListForm(self.request.GET or None)
        self.form = form
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcCategoryListView 検索条件で絞り込み')

        lists = self.set_category_lists(queryset)
        return lists

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form
        context['process_title'] = 'カテゴリ一覧'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        # context['page_size'] = self.paginate_by
        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        # path_lists = [sv_helpurl(), 'CategoryList_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        return context

    # HTMLのテーブルに設定するデータを取得
    def set_category_lists(self, queryset):
        lists = []
        for item in queryset:
            if item.use_flg == 1:
                use_flg = 'true'
            else:
               use_flg = ''

            data = {
                'folder_id': item.folder_id or '',
                'category_name': item.category_name or '',
                'notes': item.notes or '',
                'display_order': item.display_order,
                'use_flg': use_flg
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
# カテゴリ登録で検索ボタンクリックでカテゴリダイアログを表示するリスト
def get_category_list(request):
    logger.info(f'{ut_get_client_ip(request)} '
                'カテゴリ検索ボタンクリック')
    user_id = request.user.user_id
    # owner_id = get_owner_id(user_id)
    owner_id = request.session.get('owner_id')
    folders = MtFolder.objects.filter(owner_id=owner_id).exclude(use_flg=0).order_by('-display_order')
    category_list = [{'id': folder.folder_id, 'name': folder.category_name} for folder in folders]
    return JsonResponse({'category_list': category_list})

# カテゴリCSVダウンロードリクエスト
# def export_category_csv(request):
#     # print(request.GET)
#     category_list = MtFolder.objects.all().order_by('folder_id')
#     # リクエストに応じて絞り込み
#     owner_id = request.session.get('owner_id')
#     if not owner_id:
#         logger.info('export_category_csv owner_id is None')
#     # オーナーIDで絞り込み
#     queryset = category_list.filter(owner_id=owner_id)
#     # CSVを作成する
#     response = sv_response_category(queryset)
#     return response

# 同一カテゴリ名のチェック
def check_category_name(owner_id, folder_id, category_name):
    folderobjs = MtFolder.objects.filter(owner_id=owner_id,category_name=category_name).exclude(use_flg=0)
    for data in folderobjs:
        if folder_id != data.folder_id:
            logger.debug(f'MtFolder 同一カテゴリ名あり {data.folder_id}:{category_name}')
            return False
    return True

# カテゴリ登録(/変更/削除)画面
class EvcCategoryEditView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_Management/FE_CategoryEdit.html'
    form_class = EvcCategoryForm

    def get_success_url(self):
        return reverse('Evc_Management:category_list')
        # return reverse('Evc_Management:category_edit', kwargs={'folder_id': self.kwargs['folder_id']})

    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        return kwgs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        folder_id = self.kwargs.get('folder_id')
        context['form_name'] = 'category'
        context['process_title'] = 'カテゴリ登録'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        context['kubun'] = 'new'
        # path_lists = [sv_helpurl(), 'Category_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        if folder_id == '0':
            return context
        try:
            folderobj =  MtFolder.objects.get(folder_id=folder_id)
            context['kubun'] = 'change'
        except MtFolder.DoesNotExist:
            return context

        if 'form' not in kwargs:
            default_data = self.get_folder_info(folderobj)
            form = EvcCategoryForm(initial = default_data)
            context['form'] = form
        return context

    def form_valid(self, form):
        user_id = self.request.user.user_id
        # owner_id = get_owner_id(user_id)
        owner_id = self.request.session.get('owner_id')

        # kubun = self.request.POST['kubun']
        kubun = form.cleaned_data.get('kubuns')
        if kubun == 'new':
            folder_id = '0'
        else:
            folder_id = self.kwargs.get('folder_id')
            if not folder_id or folder_id == '0':
                messages.error(self.request, 'カテゴリが選択されていません。')
                return super().form_invalid(form)
        category_name = form.cleaned_data.get('category_name')
        check = check_category_name(owner_id, folder_id, category_name)
        if not check:
            messages.error(self.request, '同じカテゴリ名が存在します。区別出来るようにして下さい。')
            return super().form_invalid(form)
        if kubun == 'new' or kubun == 'change': # 登録
            notes = form.cleaned_data.get('notes')
            display_order = form.cleaned_data.get('display_order')
            data = {
                'folder_id': folder_id,
                'category_name': category_name,
                'owner_id': owner_id,
                'use_flg': 1,
                'notes': notes,
                'display_order': display_order,
            }
            if kubun == 'new':
                folder_id = sv_save_folder(data, owner_id, user_id, 'new')
                if folder_id:
                    messages.success(self.request, 'カテゴリデータを登録しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcCategoryEditView カテゴリデータを登録しました。 {folder_id=}')
                    return redirect('Evc_Management:category_edit', folder_id)
                else:
                    messages.error(self.request, 'データ登録に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                'EvcCategoryEditView データ登録に失敗しました')
            else:
                folder_id = sv_save_folder(data, owner_id, user_id, 'change')
                if folder_id:
                    messages.success(self.request, 'カテゴリデータを更新しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcCategoryEditView カテゴリデータを更新しました {folder_id=}')
                else:
                    messages.error(self.request, 'データ更新に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                'EvcCategoryEditView データ更新に失敗しました')
        elif kubun == 'delete':   # 削除
            folder_id = self.kwargs.get('folder_id')
            if sv_delete_folder(folder_id, user_id):
                messages.success(self.request, 'カテゴリデータを削除しました')
                # return redirect('Evc_Management:partner', '0')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcCategoryEditView カテゴリデータを削除しました {folder_id=}')
                return redirect('Evc_Management:category_list')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                            'EvcCategoryEditView データ削除に失敗しました')

        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcCategoryEditView データ登録に失敗しました {err}')
        return super().form_invalid(form)
    # フォーム表示のためにカテゴリ情報を取得
    def get_folder_info(self, folderobj):
        kubun = 'change'
        default_data = {
            'kubuns': kubun,
            'category_name': folderobj.category_name,
            'notes': folderobj.notes,
            'display_order': folderobj.display_order,
        }
        return default_data

# # カテゴリCSVファイルダウンロード
# def download_category_csv(request):
#     category_list = MtFolder.objects.all().order_by('folder_id')
#     # リクエストに応じて絞り込み
#     owner_id = request.session.get('owner_id')
#     if not owner_id:
#         logger.info('export_category_csv owner_id is None')
#     # オーナーIDで絞り込み
#     queryset = category_list.filter(owner_id=owner_id)

#     # CSVを作成する
#     response = sv_response_category(queryset)

#     return response
# 新規partner_id取得
def get_new_folder_id(owner_id):
    # d = ut_get_localtoday().strftime('%y%m%d')
    # id = d + '0001'
    prefix = owner_id
    try:
        pre_obj = MtFolder.objects.filter(owner_id=owner_id).order_by('-folder_id').first()
        if pre_obj:
            pre_id = pre_obj.folder_id
            num = int(pre_id[-3:]) + 1
        else:
            num = 1
    except Exception:   # ValueError
        num = 1
    id = 'AUTO_00000'
    if num < 99999:
        id = prefix + f'_{num:03d}'
    else:
        num = 1
        while num < 100000:
            id = prefix + f'_{num:3d}'
            exists = MtFolder.objects.filter(folder_id=id).exists()
            if not exists:
                break
            num += 1
    logger.debug(f'new folder_id {id}')
    return id

# カテゴリデータ登録
def sv_save_folder(data, owner_id, user_id, kubun):
    if kubun == 'new':
        folder_id = get_new_folder_id(owner_id)
        create_date = ut_get_timezone_now()
        create_user = user_id
        update_date = create_date
        update_user = user_id
    else:
        folder_id = data.get('folder_id')
        try:
            folder_obj = MtFolder.objects.get(folder_id=folder_id)
        except MtFolder.DoesNotExist:
            logger.exception(f'MtFolder DoesNotExist {folder_id=}')
        # raise ValueError('カテゴリデータ登録　取得エラー ' + folder_id)
            return False
        create_date = ut_get_localdate(folder_obj.create_date)
        create_user = folder_obj.create_user
        update_date = ut_get_timezone_now()
        update_user = user_id
    use_flg = data.get('use_flg')
    display_order = data.get('display_order')
    obj = MtFolder(
        folder_id=folder_id,
        category_name = data.get('category_name'),
        owner_id = data.get('owner_id'),
        notes = data.get('notes'),
        folder_name = '',
        folder_path = '',
        display_order = display_order,
        use_flg = use_flg or 0,
        create_date=create_date,
        create_user=create_user,
        update_user=update_user,
        update_date=update_date,
    )
    try:
        obj.save()
        logger.info(f'MtFolder save {folder_id} : {obj.category_name}')
        return folder_id
    except Exception:
        logger.exception(f'MtFolder save exception {folder_id} : {obj.category_name}')
    return False

# カテゴリデータ削除
def sv_delete_folder(folder_id, user_id):
    try:
        folder_obj = MtFolder.objects.get(folder_id=folder_id)
    except MtFolder.DoesNotExist:
        logger.exception(f'MtFolder DoesNotExist {folder_id=}')
        # raise ValueError('カテゴリデータ削除　取得エラー ' + partner_id)
        return False
    folder_obj.create_date = ut_get_localdate(folder_obj.create_date)
    folder_obj.update_user = user_id
    folder_obj.update_date = ut_get_timezone_now()
    folder_obj.use_flg = Decimal(0)

    try:
        folder_obj.save()
        logger.info(f'MtFolder delete {folder_id} : {folder_obj.category_name}')
        return folder_id
    except Exception:
        logger.exception(f'MtFolder delete exception {folder_id} : {folder_obj.category_name}')
    return False
