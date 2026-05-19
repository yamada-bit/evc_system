# Create your views here.
import os
import datetime
import calendar
import logging
# import json
import re   # 正規表現操作
# import calendar
# import csv,urllib
# import psycopg

# from django.utils import timezone
# from django.utils.timezone import make_aware

from django.shortcuts import redirect
from django.views.generic import FormView,ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
# from django.conf import settings
from django.urls import reverse,reverse_lazy
# from django.http import HttpResponse
from django.core.paginator import Paginator,EmptyPage,PageNotAnInteger

# from django.shortcuts import render, resolve_url, redirect
# from django.views.generic import CreateView, DeleteView

# from django.http import FileResponse, Http404
# from django.shortcuts import get_object_or_404

# from django.core.exceptions import PermissionDenied
from typing import cast
# クラス 'AnonymousUser' の属性 'user_id' にアクセスできません
# 属性 'user_id' が不明ですPylancereportAttributeAccessIssueの対処のためcast
# Pythonの型ヒント（Type Hint）用の関数で型安全性や読みやすさの向上が目的。
# 実行時の処理は何もしない。静的解析ツールやIDE向け
from users.models import EvcUser

# from .models import SharedFile
# from .forms import FileUploadForm

from Fms_fileshare.models import TtSharedFile
from commons.utils import ut_get_client_ip,ut_get_localtime,ut_get_localtoday

from Fms_fileshare.forms import FileUploadForm,FileListForm,FileEditForm

# from Evc_App.sv_json import sv_load_jsonfile,sv_json2textdatas,sv_datas2json
from Evc_App.sv_file import (sv_file2url,sv_handle_uploaded_file,
    get_imgfolder_upload,make_upload_dir,make_json_dir,
    sv_get_owner_ryaku_name,sv_get_category_list
)
from Fms_fileshare.svf_shared import (svf_create_sharedfile,svf_get_shared_rootfolder,svf_get_shared_imagepath,
                                     svf_make_shared_dir,svf_physical_delete_sharedfile,svf_update_sharedfile)

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']
IMAGE_EXTENTIONS = ['.jpg','.jpeg','.png']

logger = logging.getLogger(__name__)

# 共有ファイルアップロード(ファイル保存)
class FmsFileUploadView(LoginRequiredMixin, FormView):
    template_name = 'Fms_fileshare/Fms_FileUpload.html'
    form_class = FileUploadForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_form()
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context = {
            'form': form,
            'process_title': 'ファイル保存',
            'owner_ryaku_name': owner_ryaku_name
        }
        return context
    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        return kwgs

    def form_valid(self, form):
        logger.debug(f'{ut_get_client_ip(self.request)} '
                    f'FmsFileUploadView {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')

        files = self.request.FILES.getlist('file')
        request_user = cast(EvcUser, self.request.user)
        user_id = request_user.user_id
        # user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id')
        rootfolder = svf_get_shared_rootfolder()   # ルートフォルダを取得
        if not rootfolder:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'FmsFileUploadView upload rootfolder error')
            messages.error(self.request, '保存フォルダが正しく設定されていません。')
            return self.render_to_response(self.get_context_data(form=form))
        make_upload_dir(rootfolder)     # アップロードファイル格納のためのフォルダ作成
        img_upload_dir = get_imgfolder_upload(rootfolder)   # アップロード画像ファイル格納フォルダ
        if not img_upload_dir:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        f'FmsFileUploadView upload imgfolder error {rootfolder=}')
            messages.error(self.request, 'アップロードフォルダが正しく設定されていません。')
            return self.render_to_response(self.get_context_data(form=form))

        svf_make_shared_dir(rootfolder) # 共有ファイルを保存するフォルダ作成
        make_json_dir(rootfolder)   # jsonファイルを保存するフォルダ作成
        shared_type =  form.cleaned_data.get('shared_types')  # page/file

        uploadfiles = []
        for f in files:
            basename, extension = os.path.splitext(f.name)
            # ex = os.path.splitext(f.name)
            # extension = ex[1] # 拡張子を取得
            if extension.lower() in VALID_EXTENSIONS:
                # basename = ex[0]
                now = ut_get_localtime()
                time = now.strftime('_%Y%m%d-%H%M%S%f')
                name = basename + time + extension  # ファイル名の重複をさけるため時刻追加
                # アップロードされたファイルをハンドルする
                path = sv_handle_uploaded_file(f, name, rootfolder)
                if path:
                    uploadfiles.append({'name':f.name, 'path':path, 'shared_type':shared_type})
                    # id = sv_save_upload_entry(user_id, owner_id, basename)
                    # uploadfile = UploadFile(id, f.name, path, 0)
                    # uploadfiles.append(uploadfile)
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'FmsFileUploadView uploadfiles {f.name} -> {path}')
        # 共有ファイル情報登録を実行--->
        lists, error_lists = svf_create_sharedfile(uploadfiles, user_id, owner_id)

        cnt = len(error_lists)
        if cnt != 0:
            # 共有ファイル情報登録できないファイルがあった場合
            msgerror = '\n'.join(error_lists)
            messages.error(self.request, f'{msgerror}はパスワードまたは、処理できないファイルです。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'FmsFileUploadView error files {msgerror}')
        else:
            cnt = len(lists)
            if cnt == 0:
                messages.error(self.request, 'アップロードに失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             'FmsFileUploadView アップロードに失敗しました')
            else:
                messages.success(self.request, 'アップロードに成功しました。')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'FmsFileUploadView {cnt}件 アップロードに成功しました。')
        # <---
        return self.render_to_response(self.get_context_data(form=form))
        # return redirect('Fms_Ocrform:entry_list')
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'FmsFileUploadView アップロードに失敗しました {err}')
        return super().form_invalid(form)
"""
# PostgreSQLデータベースに共有ファイル情報テーブルを作成
def create_sharedfile_tabel():
    # データベースに接続
    conn = psycopg.connect(
        "dbname=kms_db user=postgres password=postgres host=localhost port=5432")
    # カーソルを作成
    cur = conn.cursor()

    # テーブル作成SQLを実行
    query = 'CREATE TABLE IF NOT EXISTS public."tt_sharedfile" ( \
        shared_id character varying(20) not null,\
        shared_name character varying(50),\
        owner_id character varying(10),\
        file_name character varying(50),\
        file_path character varying(100),\
        processed_ym character varying(6),\
        create_user character varying(30),\
        create_date timestamp(6) without time zone,\
        update_user character varying(30),\
        update_date timestamp(6) without time zone,\
        primary key (shared_id)\
    );'

    cur.execute(query)
    # コミットして変更を反映
    conn.commit()
    # クローズ
    cur.close()
    conn.close()
def delete_sharedfile():
    svf_physical_delete_all()

"""
# 共有ファイル情報一覧表示
class FmsFileListView(LoginRequiredMixin, ListView):
    template_name = 'Fms_fileshare/Fms_FileList.html'
    model = TtSharedFile
    ordering = '-shared_id'
    paginate_by = 10 # ページネーション 分割数

    # def get_queryset(self, **kwargs):
    #     queryset = super().get_queryset(**kwargs) # TtEntry.objects.all() と同じ結果
    #     # GETリクエストパラメータにkeywordがあれば、それでフィルタする
    #     keyword = self.request.GET.get('keyword')
    #     if keyword is not None:
    #         queryset = queryset.filter(title__contains=keyword)
    #         messages.success(self.request, '「{}」の検索結果'.format(keyword))
    #     queryset = queryset.order_by('-shared_id')
    #     return queryset
    def get_queryset(self):
        # queryset = super().get_queryset().order_by(F('processed_date').desc(nulls_last=True))
        queryset = super().get_queryset()
        owner_id = self.request.session.get('owner_id')
        if not owner_id:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'FmsFileListView session owner_id is None')

        today = ut_get_localtoday()
        # last_day = calendar.monthrange(today.year, today.month)[1]
        # begin_of_month = datetime.date(today.year, today.month, 1)
        # end_of_month = datetime.date(today.year, today.month, last_day)
        begin_of_month = today
        end_of_month = today

        # yearmonth = today.strftime('%Y-%m')
        # request.GET 型でリクエスト　QueryDict型で初期化
        if self.request.GET:
            form = FileListForm(self.request.GET)
        else:
            initial_data = {
                'uploader' : '',
                'process_date1' : begin_of_month,
                'process_date2' : end_of_month,
            }
            form = FileListForm(None, initial=initial_data)
        # ChoiceFieldに選択肢の設定
        form.fields['category'].choices = get_category_choices(owner_id)
        form.fields['uploader_cd'].choices = get_uploader_list(owner_id)
        self.form = form 

        if form.is_valid():
            # バリデーションを実行しデータが有効
            shared_id = self.request.GET.get('shared_id')
            act = self.request.GET.get('act')   # 削除ボタンがクリックされたら'del'が設定されている
            if shared_id and act == 'del':
                try:
                    # sharedfile_obj =  TtSharedFile.objects.get(shared_id=shared_id,delete_flg=0)
                    # request_user = cast(EvcUser, self.request.user)
                    # user_id = request_user.user_id
                    # # user_id = self.request.user.user_id
                    # 共有ファイル情報削除/ファイル削除 
                    # name = svf_delete_sharedfile(shared_id, None, None, None, user_id)
                    name = svf_physical_delete_sharedfile(shared_id)
                    if name:
                        basename = os.path.splitext(name)[0]
                        messages.success(self.request, basename + '： を削除しました')
                        logger.info(f'{ut_get_client_ip(self.request)} '
                                    f'FmsFileListView {shared_id}:{basename} を削除しました')
                    else:
                        messages.error(self.request, 'データ削除に失敗しました')
                        logger.error(f'{ut_get_client_ip(self.request)} '
                                        f'FmsFileListView データ削除に失敗しました {shared_id}')
                except TtSharedFile.DoesNotExist:
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                    f'FmsFileListView DoesNotExist データ削除に失敗しました {shared_id}')
            form_month = form.cleaned_data.get('shared_month')
            form_category = form.cleaned_data.get('category', '')
            form_shared_name = form.cleaned_data.get('shared_name', '')
            form_shared_type = form.cleaned_data.get('shared_type', '0')
            form_file_name = form.cleaned_data.get('file_name', '')
            form_uploader = form.cleaned_data.get('uploader', '')
            date_from = form.cleaned_data.get('process_date1')
            date_to = form.cleaned_data.get('process_date2')
            search_data = {
                'shared_month': form_month,
                'category': form_category,
                'shared_name': form_shared_name,
                'shared_type': form_shared_type,
                'file_name': form_file_name,
                'uploader' : form_uploader,
                'process_date1' : date_from,
                'process_date2' : date_to,
            }
        else:
            search_data = {
                'process_date1' : begin_of_month,
                'process_date2' : end_of_month,
            }
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'FmsFileListView')
        # オーナーIDでで絞り込み
        queryset = queryset.filter(owner_id=owner_id,delete_flg=0)
        # user_authority = sv_get_user_authority(user_id)
        # if user_authority == '一般':
        #     queryset = queryset.filter(create_user=user_id) # ログインユーザ
        # 検索条件で絞り込み
        if search_data:
            queryset = filter_file(queryset, search_data, owner_id)
        # テーブル表示内容を取得
        lists = self.set_file_lists(queryset)

        # 検索条件編集からの戻りのurlをセッションデータに
        list_url = self.request.get_full_path()   #build_absolute_uri()
        list_url = re.sub('page=[0-9]+', 'page=1', list_url)
        list_url = re.sub('shared_id=[0-9]+_[0-9]+', 'shared_id=', list_url)
        list_url = re.sub('act=del', 'act=', list_url)
        self.request.session['list_url'] = list_url
        return lists
            
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form

        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10

        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)

        context['process_title'] = '共有ファイル一覧'
        context['owner_ryaku_name'] = owner_ryaku_name

        return context
    # HTMLのテーブルに設定するデータを取得
    def set_file_lists(self, queryset):
        lists = []
        item_no = 1
        for item in queryset:
            try:
                shared_date = item.shared_date.strftime('%Y/%m/%d')
            except Exception:
                shared_date = ''
            # if item.processed_ym:
            #     dtm = item.processed_ym[:4] + '/ ' + item.processed_ym[4:]
            # else:
            #     dtm = ''
            try:
                dt = item.create_date.strftime('%Y/%m/%d')
            except Exception:
                dt = ''
            match item.shared_type:
                case 1:
                    shared_type = '重要'
                case 2:
                    shared_type = '通知（会社）'
                case 3:
                    shared_type = '共有（一般）'
                case _:
                    shared_type = ''
            userobj = EvcUser.objects.filter(user_id=item.create_user).first()
            user_name = userobj.user_name if userobj else ''

            filepath = item.file_path
            url = sv_file2url(filepath)
            data = {
                'item_no': str(item_no),
                'shared_name': item.shared_name,
                'file_name': os.path.splitext(item.file_name)[0],
                # 'processed_ym': dtm,
                'shared_type': shared_type,
                'shared_date': shared_date,
                'create_date': dt,
                'notes': item.notes,
                'user_name': user_name,
                'shared_id': item.shared_id,
                'pdffile': url,
            }
            lists.append(data)
            item_no += 1
        return lists
    # ページネーション分割数
    def get_paginate_by(self, queryset):
        paginate_by = super().get_paginate_by(queryset)
        page_size = self.request.GET.get('page_size')
        if page_size:
            paginate_by = int(page_size)
        return paginate_by
# カテゴリ選択リストの設定
def get_category_choices(owner_id):
    choices = []
    choices.append(('0','カテゴリを選択'))
    lists = sv_get_category_list(owner_id)
    for list in lists:
        choices.append((list, list))
    return choices
def get_uploader_list(owner_id):
    uploaders = []
    lists = EvcUser.objects.filter(owner_id=owner_id).values('user_id', 'user_name').exclude(delete_flg=1).order_by('user_name')
    for item in lists:
        uploaders.append((item.get('user_id'), item.get('user_name')))

    return uploaders

# 検索条件で絞り込み
def filter_file(queryset, serach_data, owner_id):
    # shared_month = serach_data.get('shared_month', '')
    # category = serach_data.get('category', '')
    shared_name = serach_data.get('shared_name', '')
    shared_type = serach_data.get('shared_type', '0')
    try:
        shared_type = int(shared_type)
    except ValueError:
        shared_type = 0
    file_name = serach_data.get('file_name', '')
    uploader = serach_data.get('uploader', '')
    date_from = serach_data.get('process_date1')
    date_to = serach_data.get('process_date2')

    # 処理年月: yyyy/mm yyyy-mm
    # if shared_month:
    #     try:
    #         dt = shared_month.replace('/', '').replace('-', '')
    #         if 6 < len(dt):
    #             dt = dt[:6]
    #         # bom = datetime.datetime.strptime(dt + '01','%Y%m%d')
    #         # eom = bom.replace(day=calendar.monthrange(bom.year, bom.month)[1])
    #         date_from = dt
    #         date_to = dt
    #         if date_from and date_to:
    #             queryset = queryset.filter(processed_ym__range=[date_from, date_to]).order_by('processed_ym')
    #         elif date_from:
    #             queryset = queryset.filter(processed_ym__gte=date_from).order_by('processed_ym')
    #         elif date_to:
    #             queryset = queryset.filter(processed_ym__lte=date_to).order_by('processed_ym')
    #     except Exception:
    #         pass
        
    # 共有名
    if shared_name:
        queryset = queryset.filter(shared_name__contains=shared_name)
    # 共有区分
    if shared_type != 0:
        queryset = queryset.filter(shared_type=shared_type)
    # ファイル名
    if file_name:
        queryset = queryset.filter(file_name__contains=file_name)
    # 登録者
    if uploader:
        try:
            uploaders = EvcUser.objects.filter(owner_id=owner_id,user_name__contains=uploader)
            list = []
            for data in uploaders:
                list.append(data.user_id)
            queryset = queryset.filter(create_user__in=list)
            # partner_id = MtPartner.objects.get(partner_name=partner).partner_id
            # queryset = queryset.filter(partner_id=partner_id)
        except Exception:
            logger.exception(f'EvcUser exception {uploader=}')
    if date_from and date_to:
        queryset = queryset.filter(shared_date__range=[date_from, date_to])#.order_by('shared_date')
    elif date_from:
        queryset = queryset.filter(shared_date__gte=date_from)#.order_by('shared_date')
    elif date_to:
        queryset = queryset.filter(shared_date__lte=date_to)#.order_by('shared_date')

    return queryset

# 共有ファイル情報編集
class FmsFileEditView(LoginRequiredMixin, FormView):
    template_name = 'Fms_fileshare/Fms_FileEdit.html'
    form_class = FileEditForm

    def get_success_url(self):
        return reverse('Fms_fileshare:file_edit', kwargs={'shared_id': self.kwargs['shared_id']})
   
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shared_id = self.kwargs.get('shared_id')
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context.update({
            'form_name': 'fileedit',
            'process_title': '共有ファイル情報編集',
            'shared_id': shared_id,
            'owner_ryaku_name': owner_ryaku_name,
            })
        try:
            sharedfile_obj =  TtSharedFile.objects.get(shared_id=shared_id)
        except TtSharedFile.DoesNotExist:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            f'FmsFileEditView TtSharedFile DoesNotExist {shared_id=}')
            return context
        if 'form' not in kwargs:
            # if sharedfile_obj.processed_ym:
            #     shared_month = sharedfile_obj.processed_ym[:4] + '-' + sharedfile_obj.processed_ym[4:]
            # else:
            #     shared_month = ''
            default_data = {
                'shared_id': sharedfile_obj.shared_id,
                'shared_name': sharedfile_obj.shared_name,
                'shared_type': sharedfile_obj.shared_type,
                'shared_date': sharedfile_obj.shared_date,
                'notes': sharedfile_obj.notes
            }
            form = FileEditForm(initial = default_data)
            context['form'] = form

        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'FmsFileEditView {shared_id=}')

        # image_no = self.kwargs.get('image_no') or 1
        try:
            # 表示するファイルのurl
            filepath = sharedfile_obj.file_path
            url = sv_file2url(filepath)
            images =  svf_get_shared_imagepath(sharedfile_obj)
            if 0 < len(images):
                imgurl = sv_file2url(images[0])
            else:
                imgurl = ''
            # imgurls = []
            # for idx, imgfile in enumerate(images):
            #     imgurls.append(sv_file2url(imgfile))
            ext = os.path.splitext(os.path.basename(filepath))[1] if filepath else ''
            if ext.lower() == '.pdf':
                context.update({                # context.update({}) 複数の値を一度に更新する場合
                    'src_pdffile': True,
                    'pdffile': url,
                })
            else:
                context['src_pdffile'] = False  # context[]= 単一のキーを更新するシンプルなケース
            context.update({
                'file_name': sharedfile_obj.file_name,
                'bk_img': imgurl,
                'page_count': len(images)
            })

            # 前頁・次頁対応ページング
            # page_cnt = 1
            # ext = os.path.splitext(os.path.basename(filepath))[1] if filepath else ''
            # if ext.lower() == '.pdf':
            #     cnt = sv_get_pdfpages(filepath)
            #     if cnt and 0 < cnt:
            #         page_cnt = cnt
            # imageno_list = list(range(1, page_cnt + 1))
     
            # page_obj = self.get_page_obj(imageno_list, image_no)
            # context['page_obj'] = page_obj
            # if page_obj.has_next():
            #     context['next_image_no'] = imageno_list[page_obj.next_page_number() - 1]
            # if page_obj.has_previous():
            #     context['previous_image_no'] = imageno_list[page_obj.previous_page_number() - 1]
        except Exception:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            'FmsFileEditView exception')
        return context

    def form_valid(self, form):
        act = self.request.POST.get('submit_action')
 
        # owner_id = self.request.session.get('owner_id')
        # image_no = self.kwargs.get('image_no') or 1
        shared_id = form.cleaned_data.get('shared_id')

        if act == 'update':   # 更新
            # user_id = self.request.user.user_id
            return super().form_valid(form)
        elif act == 'commit':   # 登録
            request_user = cast(EvcUser, self.request.user)
            user_id = request_user.user_id
            # user_id = self.request.user.user_id
            shared_name = form.cleaned_data.get('shared_name')
            shared_date = form.cleaned_data.get('shared_date')
            # if shared_date:
            #     processed_ym = shared_date.replace('/', '').replace('-', '')
            # else:
            #     processed_ym = ''
            notes = form.cleaned_data.get('notes')
            shared_type =  form.cleaned_data.get('shared_type') 

            #  共有ファイル情報データ更新
            id = svf_update_sharedfile(shared_id, shared_name, shared_type, shared_date, notes, user_id)
            if id:
                messages.success(self.request, 'データを更新しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'FmsFileEditView データを更新しました {shared_id=}')
            else:
                messages.error(self.request, 'データ更新に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'FmsFileEditView データ更新に失敗しました {shared_id=}')
            return super().form_valid(form)
        elif act == 'cancel':   # 戻る
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            return redirect('Fms_fileshare:file_list')
        elif act == 'delete':   # 削除
            request_user = cast(EvcUser, self.request.user)
            user_id = request_user.user_id
            # user_id = self.request.user.user_id
            shared_name = form.cleaned_data.get('shared_name')
            shared_date = form.cleaned_data.get('shared_date')
            # shared_month = form.cleaned_data.get('shared_month')
            # if shared_month:
            #     processed_ym = shared_month.replace('/', '').replace('-', '')
            # else:
            #     processed_ym = ''
            notes = form.cleaned_data.get('notes')

            # 共有ファイル情報削除/ファイル削除 
            # name = svk_delete_sharedfile(shared_id, shared_name, shared_date, notes, user_id)            
            name = svf_physical_delete_sharedfile(shared_id)
            if name:
                basename = os.path.splitext(name)[0]
                messages.success(self.request, f'{basename} を削除しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'FmsFileEditView {shared_id}:{basename} を削除しました')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'FmsFileEditView データ削除に失敗しました {shared_id}')
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            return redirect('Fms_fileshare:file_list')

        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'FmsFileEditView データ登録に失敗しました {err}')
        return super().form_invalid(form)
    
    # 前頁・次頁対応ページング
    def get_page_obj(self, images, image_no):
        page_no = image_no
        paginator = Paginator(images, 1)
        try:
            page_obj = paginator.page(page_no)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)   
        return page_obj 

"""
class FileUploadView(LoginRequiredMixin, CreateView):
    model = SharedFile
    form_class = FileUploadForm
    template_name = 'Fms_fileshare/FE_SaveEntry.html'
    success_url = '/Fms_fileshare/list'

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        form.instance.original_name = form.cleaned_data['file'].name
        return super().form_valid(form)
# ファイル一覧（自分がアップロードしたもの）
class FileListView(LoginRequiredMixin, ListView):
    model = SharedFile
    template_name = 'Fms_fileshare/FE_EntryList.html'

    def get_queryset(self):
        return SharedFile.objects.filter(uploaded_by=self.request.user)
# ファイル配信 View
def file_view(request, pk):
    if not request.user.is_authenticated:
        raise Http404()

    file_obj = get_object_or_404(
        SharedFile,
        pk=pk,
        uploaded_by=request.user
    )

    return FileResponse(
        file_obj.file.open(),
        as_attachment=False,
        filename=file_obj.original_name
    )

class FileDeleteView(LoginRequiredMixin, DeleteView):
    model = SharedFile
    template_name = "Fms_fileshare/file_confirm_delete.html"
    success_url = reverse_lazy("Fms_fileshare:list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()

        # 権限チェック
        if obj.uploaded_by != request.user and not request.user.is_staff:
            raise PermissionDenied("削除権限がありません")

        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()

        # 実ファイル削除
        if obj.file:
            obj.file.delete(save=False)

        return super().delete(request, *args, **kwargs)
"""