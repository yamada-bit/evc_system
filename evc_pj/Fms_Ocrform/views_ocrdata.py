import os
import datetime
# import threading
# import base64
import logging
import re   # 正規表現操作
import json

# from django.http import JsonResponse
# from django.http import HttpResponse,Http404
from django.shortcuts import render, redirect
from django.views.generic import FormView,ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
# from django.conf import settings
# from django.utils import timezone
# from django.utils.timezone import make_aware
# from dateutil.relativedelta import relativedelta

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse,reverse_lazy
# from django.http import HttpResponseRedirect
from django.db.models import F  
# from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from django.db.models import Q

from Evc_App.views import OwnerTestMixin
from users.models import EvcUser
from Fms_Ocrform.models import TtOcrform,TtEntry,TtOcrData,TtTimesheet,TtJafyame

from commons.utils import ut_get_localdate,ut_get_client_ip,ut_get_localtime

from Evc_App.sv_file import (
    sv_handle_uploaded_file,make_processed_ym_dir,sv_file2url,
    get_imgfolder_upload,make_upload_dir,make_json_dir,
    sv_get_category_list,
    sv_get_owner_ryaku_name,
)
from Evc_App.sv_get_image_shape import sv_get_pdfpages

from Fms_Ocrform.forms import (EvcUploadEntryForm,EvcOcrDataListForm,EvcEditOcrDataForm,
                               EvcTimesheetListForm,EvcEditTimesheetForm,
                               EvcJafyameListForm,EvcEditJafyameForm,
                               EvcEntryListForm,EvcEditEntryForm)
from Fms_Ocrform.svf_common import (str2int,svf_make_ocrdata_image_dir,
                                    svf_get_ocrdata_rootfolder,svf_get_ocrdata_imagepath,
                                    svf_get_jafyame_imagepath)

from Fms_Ocrform.svf_ocrform import svf_get_area_jsonstr
from Fms_Ocrform.svf_ocrdata import (svf_create_ocrdata,svf_update_shiori,svf_update_ocrdata,
                                    svf_update_timesheet,svf_update_jafyame,svf_update_entry,
                                    svf_delete_ocrdata,
                                    svf_filter_timesheet,svf_filter_jafyame,
                                    svf_create_access_log)
from Fms_Ocrform.svt_tnw import svt_export_zip

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']
IMAGE_EXTENTIONS = ['.jpg','.jpeg','.png']
# UPLOAD_DIR = settings.MEDIA_ROOT.parent.parent.joinpath('media/upload')
# モデルの選択を辞書で管理	
MODEL_CLASSES = {	
    'entry': TtEntry,
    'ocrdata': TtOcrData,	
    'timesheet': TtTimesheet,	
    'jafyame': TtJafyame,	# JAふくおか八女
}	
PROCESS_TITLE = {	
    'entry': '生産履歴票保存',
    'ocrdata': '送り状保存',	
    'timesheet': '勤務表保存',	
    'jafyame': 'JAふくおか八女',	
}	
PROCESS_TITLE_LIST = {	
    'entry': '生産履歴票一覧',
    'ocrdata': '送り状一覧',	
    'timesheet': '勤務表一覧',	
    'jafyame': 'JAふくおか八女一覧',	
}	
PROCESS_TITLE_EDIT = {	
    'entry': '検索条件編集',
    'ocrdata': '検索条件編集',	
    'timesheet': '検索条件編集',	
    'jafyame': '検索条件編集',	
}	

logger = logging.getLogger(__name__)

# Ocr文書ファイルアップロード(ファイル保存)
class EvcUploadOcrDataView(LoginRequiredMixin, FormView):
    template_name = 'Fms_Ocrform/FE_SaveEntry.html'
    form_class = EvcUploadEntryForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.kwargs['model_name']  # URLからモデル名を取得	
        process_title = PROCESS_TITLE.get(model_name)
        form = self.get_form()
        context.update({
            'form': form,
            'process_title': process_title,
            'model_name': model_name
        })
        return context
    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        owner_id = self.request.session.get('owner_id')
        # ChoideFieldの選択肢をパラメタで渡す __init__()
        kwgs['ocrforms'] = self.get_ocrform_choices(owner_id)
        return kwgs

    def form_valid(self, form):
        model_name = self.kwargs['model_name']  # URLからモデル名を取得	
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'EvcUploadOcrDataView {model_name=} {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')

        files = self.request.FILES.getlist('file')
        user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id')
        rootfolder = svf_get_ocrdata_rootfolder(model_name)   # 文書ファイルルートフォルダを取得
        if not rootfolder:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcUploadOcrDataView {model_name=} rootfolder error')
            messages.error(self.request, 'ルートフォルダが正しくありません。')
            return self.render_to_response(self.get_context_data(form=form))
        make_upload_dir(rootfolder)     # アップロードファイル格納のためのフォルダ作成
        img_upload_dir = get_imgfolder_upload(rootfolder)
        if not img_upload_dir:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        f'EvcUploadOcrDataView {model_name=} upload imgfolder error {rootfolder=}')
            messages.error(self.request, 'アップロードフォルダが正しくありません。')
            return self.render_to_response(self.get_context_data(form=form))
        ymdir = make_processed_ym_dir(rootfolder)     # ファイルを保存する年月フォルダ作成
        if not ymdir:
            logger.error('EvcUploadOcrDataView {model_name=} processed_ym_dir error')
            messages.error(self.request, "保存フォルダが正しくありません。")
            return self.render_to_response(self.get_context_data(form=form))
        svf_make_ocrdata_image_dir(rootfolder) # 文書ファイル画像を保存するフォルダ作成
        make_json_dir(rootfolder)       # jsonファイルを保存するフォルダ作成
        ocrform = form.cleaned_data.get('ocrform')
        if ocrform and ocrform != '0':
            ocrform_id = ocrform
        else:
            ocrform_id = ''
        uploadfiles = []
        for f in files:
            # basename, extension = os.path.splitext(f.name)
            ex = os.path.splitext(f.name)
            extension = ex[1] # 拡張子を取得
            if extension.lower() in VALID_EXTENSIONS:
                basename = ex[0]
                now = ut_get_localtime()
                time = now.strftime('_%Y%m%d-%H%M%S%f')
                name = basename + time + extension  # ファイル名の重複をさけるため時刻追加
                # アップロードされたファイルをハンドルする
                path = sv_handle_uploaded_file(f, name, rootfolder)
                if path:
                    uploadfiles.append({
                        'model_name': model_name,
                        'name': f.name,
                        'path': path,
                        'imgpath': '',
                        'ocrform': ocrform_id
                        })
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcUploadOcrDataView {model_name=} uploadfile {f.name} -> {path}')
        # Ocr文書登録を実行--->
        lists, error_lists = svf_create_ocrdata(model_name, uploadfiles, user_id, owner_id)

        cnt = len(error_lists)
        if cnt != 0:
            # 文書登録できないファイルがあった場合
            msgerror = '\n'.join(error_lists)
            messages.error(self.request, f'{msgerror}はパスワードまたは、処理できないファイルです。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'EvcUploadOcrDataView {model_name=} error files {msgerror}')
            # if msgok:
            #     messages.success(self.request, msgok + 'はアップロードに成功しました。')
        else:
            cnt = len(lists)
            if cnt == 0:
                messages.error(self.request, 'アップロードに失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             'EvcUploadOcrDataView {model_name=} アップロードに失敗しました')
            else:
                messages.success(self.request, 'アップロードに成功しました。')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcUploadOcrDataView {model_name=} {cnt}件 アップロードに成功しました。')
        # <---
        return self.render_to_response(self.get_context_data(form=form))
        # return redirect('Fms_Ocrform:entry_list')
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcUploadOcrDataView アップロードに失敗しました {err}')
        return super().form_invalid(form) 
    # フォームの選択肢を取得
    def get_ocrform_choices(self, owner_id):
        choices = []
        choices.append(('0', 'フォームを選択してください。'))
        if owner_id:
            # if data_type == 1:
            #     form_id = 'ofrm_'
            # else:
            #     form_id = 'ocrdata_'
            form_id = 'ofrm_'
            lists = TtOcrform.objects.filter(ocrform_id__contains=form_id).values('ocrform_id','ocrform_name').order_by('ocrform_id')
            # lists = TtOcrform.objects.values('ocrform_id','ocrform_name').order_by('ocrform_id')
            for item in lists:
                choices.append((item.get('ocrform_id'), item.get('ocrform_name')))
        return choices

# ListView ---> 
#   modelで指定したデータベーステーブルからQuerySetを取得する
#   「object_list」という変数にQuerySetを格納する
#   HTMLテンプレートへコンテキストとしてQuerySetを渡す

# Ocr文書一覧表示
class EvcOcrDataListView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Fms_Ocrform/FE_OcrDataList.html'
    model = TtOcrData
    # ordering = '-ocrdata_id'
    paginate_by = 10 # ページネーション 分割数

    def get_template_names(self):
        model_name = self.kwargs.get('model_name')  # URLからモデル名を取得
        if model_name == 'ocrdata':
            template_name = 'Fms_Ocrform/FE_OcrDataList.html'
        elif model_name == 'timesheet':
            template_name = 'Fms_Ocrform/FE_TimesheetList.html'
        elif model_name == 'entry':
            template_name = 'Fms_Ocrform/FE_EntryList.html'
        elif model_name == 'jafyame':   # JAふくおか八女
            template_name = 'Fms_Ocrform/FE_JafyameList.html'
        else:
            template_name = self.template_name

        return [template_name]
    
    def get_queryset(self):
        # queryset = super().get_queryset().order_by(F('processed_date').desc(nulls_last=True))
        # queryset = super().get_queryset()
        model_name = self.kwargs.get('model_name')
        model_class = MODEL_CLASSES.get(model_name)
        if not model_class:
            return []
        queryset = model_class.objects.all().order_by(F('create_date').desc(nulls_last=True))
 
        owner_id = self.request.session.get('owner_id')
        if not owner_id:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcOcrDataListView session owner_id is None')
        if model_name == 'ocrdata':
            # request.GET 型でリクエスト　QueryDict型で初期化
            # request.GETは辞書型であり、リクエスト送信時のデータが格納されている
            form = EvcOcrDataListForm(self.request.GET or None)
        elif model_name == 'timesheet':
            form = EvcTimesheetListForm(self.request.GET or None)
        elif model_name == 'entry':
            # オーナーIDでで絞り込み
            queryset = queryset.filter(owner_id=owner_id)
            queryset = queryset.filter(entry_detail__isnull=False)
            form = EvcEntryListForm(self.request.GET or None)
        elif model_name == 'jafyame':   # JAふくおか八女
            form = EvcJafyameListForm(self.request.GET or None)
        else:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcOcrDataListView model_name error')
            return []
        # # ChoiceFieldに選択肢の設定
        # form.fields['category'].choices = self.get_category_choices(owner_id)
        self.form = form 

        # logger.debug(f'{ut_get_client_ip(self.request)} '
        #             f'EvcOcrDataListView query {self.request.GET.dict()}')
        if form.is_valid():
            # バリデーションを実行しデータが有効
            ocrdata_id = self.request.GET.get('ocrdata_id')
            act = self.request.GET.get('act')   # 削除ボタンがクリックされたらテキスト'del'が設定されている
            user_id = self.request.user.user_id
            if ocrdata_id and act == 'del':
                #  文書情報削除/ファイル削除 
                name = svf_delete_ocrdata(model_name, ocrdata_id, user_id, owner_id)
                if name:
                    basename = os.path.splitext(name)[0]
                    # messages.success(self.request, basename + '： を削除しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcOcrDataListView {model_name=} {ocrdata_id}:{basename} を削除しました')
                else:
                    messages.error(self.request, 'データ削除に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                 f'EvcOcrDataListView データ削除に失敗しました {model_name=} {ocrdata_id}')
            # アクセスログ記録
            #     svf_create_access_log(owner_id, user_id, ocrdata_id, 'del')
            # else:
            # アクセスログ記録
            #     svf_create_access_log(owner_id, user_id, model_name, 'view')
            if model_name == 'timesheet':
                # 検索条件で絞り込み
                queryset = svf_filter_timesheet(self.request, queryset)
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcOcrDataListView 検索条件で絞り込み {model_name=}')
            elif model_name == 'jafyame':   # JAふくおか八女
                # 検索条件で絞り込み
                queryset = svf_filter_jafyame(self.request, queryset)
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcOcrDataListView 検索条件で絞り込み {model_name=}')

            # 検索条件編集からの戻りのurlをセッションデータに
            list_url = self.request.get_full_path()   #build_absolute_uri()
            list_url = re.sub('page=[0-9]+', 'page=1', list_url)
            list_url = re.sub('ocrdata_id=[0-9]+_[0-9]+', 'ocrdata_id=', list_url)
            list_url = re.sub('act=del', 'act=', list_url)
            self.request.session['list_url'] = list_url
        else:
            # セッションデータクリア
            if 'list_url' in self.request.session:
                del self.request.session['list_url']
            logger.info(f'{ut_get_client_ip(self.request)} '
                        'EvcOcrDataListView initial display')
            # アクセスログ記録
            # svf_create_access_log(owner_id, self.request.user.user_id, model_name, 'list')

        # テーブル表示内容を取得
        # 表示ページの一覧の範囲を算出
        page_no = self.request.GET.get('page')
        page_size = self.request.GET.get('page_size')
        if page_size:
            page_size = int(page_size)
        else:
            page_size = 10
        if page_no:
            to_no = int(page_no) * page_size
            from_no = to_no - page_size + 1
        else:
            to_no = page_size
            from_no = to_no - page_size + 1
        lists = self.set_ocrdata_lists(queryset, from_no, to_no)
        if model_name == 'entry':
            # セッション変数を削除
            if 'entry_pages' in self.request.session:
                del self.request.session['entry_pages']
        else:
            # 検索条件編集画面　前頁・次頁対応セッション変数
            # ログアウト時に削除
            if lists:
                ocrdata_lists = []
                for item in lists:
                    # if model_name == 'ocrdata':
                    #     ocrdata_lists.append(item['ocrdata_id'])
                    # elif model_name == 'timesheet':
                    #     ocrdata_lists.append(item['timesheet_id'])
                    ocrdata_lists.append(item['ocrdata_id'])
                self.request.session['ocrdata_lists'] = ocrdata_lists

        return lists
            
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.kwargs.get('model_name')
        # search formを渡す
        context['form'] = self.form

        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10

        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)

        process_title = PROCESS_TITLE_LIST.get(model_name)
        context['process_title'] = process_title
        context['owner_ryaku_name'] = owner_ryaku_name

        return context
    # カテゴリ選択リストの設定
    # def get_category_choices(self, owner_id):
    #     choices = []
    #     choices.append(('0','カテゴリを選択'))
    #     lists = sv_get_category_list(owner_id)
    #     for list in lists:
    #         # if list != '注文請書':
    #         choices.append((list, list))
    #     return choices

    # HTMLのテーブルに表示するデータを取得
    def set_ocrdata_lists(self, queryset, from_no, to_no):
        lists = []
        item_no = 1
        for item in queryset:
            if from_no and to_no:
                if item_no < from_no or to_no < item_no:
                    model_class = type(item)
                    if model_class == TtOcrData:
                        ocrdata_id = item.ocrdata_id
                    elif model_class == TtTimesheet:
                        ocrdata_id = item.timesheet_id
                    elif model_class == TtJafyame:  # JAふくおか八女
                        ocrdata_id = item.jafyame_id
                    elif model_class == TtEntry:
                        ocrdata_id = item.entry_id
                    data = {
                        'ocrdata_id': ocrdata_id,
                        'item_no': str(item_no)
                    }
                    lists.append(data)
                    item_no += 1
                    continue
            # Ocr文書情報を取得
            data = get_ocrdata_list_info(item)

            data['item_no'] = str(item_no)
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
# Ocr文書情報を取得
def get_ocrdata_list_info(ocrdata_obj):
    createday = ut_get_localdate(ocrdata_obj.create_date)
    if createday:
        create_date = createday.strftime('%Y/%m/%d')
    else:
        create_date = ''
    userobj = EvcUser.objects\
        .filter(user_id=ocrdata_obj.create_user)\
        .first()
    if userobj:
        user_name = (userobj.user_name or '')
    else:
        user_name = ''
    model_class = type(ocrdata_obj)
    if model_class == TtOcrData:
        if ocrdata_obj.search_text:
            d = json.loads(ocrdata_obj.search_text)
            tr_no = d.get('tr_no')
            nx_tr_no = d.get('nx_tr_no')
        else:
            tr_no = ''
            nx_tr_no = ''

        data = {
            'pdf_name': ocrdata_obj.pdf_name or '',
            'tr_no': tr_no,
            'nx_tr_no':  nx_tr_no,
            'create_date': create_date,
            'user_name': user_name,
            'ocrdata_id': ocrdata_obj.ocrdata_id,
        }
    elif model_class == TtTimesheet:
        if ocrdata_obj.target_date:
            target_month = ocrdata_obj.target_date.strftime('%Y-%m')
        else:
            target_month = ''
        data = {
            'pdf_name': ocrdata_obj.pdf_name or '',
            'office_name': ocrdata_obj.office_name or '',
            'emp_name':  ocrdata_obj.emp_name or '',
            'emp_id':  ocrdata_obj.emp_id or '',
            'target_month': target_month,
            'create_date': create_date,
            'user_name': user_name,
            'ocrdata_id': ocrdata_obj.timesheet_id,
        }
    elif model_class == TtJafyame:  # JAふくおか八女
        try:
            processed_date = ocrdata_obj.processed_date.strftime('%Y/%m/%d')
        except Exception:
            processed_date = ''

        data = {
            'pdf_name': ocrdata_obj.pdf_name or '',
            'dept': ocrdata_obj.dept or '',
            'section':  ocrdata_obj.section or '',
            'spine':  ocrdata_obj.spine or '',
            'username': ocrdata_obj.username,
            'processed_date': processed_date,
            'create_date': create_date,
            'user_name': user_name,
            'ocrdata_id': ocrdata_obj.jafyame_id,
        }
    elif model_class == TtEntry:
        if ocrdata_obj.processed_ym:
            dt = ocrdata_obj.processed_ym[:4] + '/ ' + ocrdata_obj.processed_ym[4:]
        else:
            dt = ''
        # try:
        #     dt = item.create_date.strftime('%Y/%m')
        # except Exception:
        #     dt = ''
        userobj = EvcUser.objects.filter(user_id=ocrdata_obj.create_user).first()
        user_name = '(' + (userobj.user_name or '') + ')' if userobj else ''
        dt = dt + user_name

        data = {
            'pdf_name': os.path.splitext(ocrdata_obj.pdf_name)[0],
            'processed_ym': dt,
            'result': '',
            'ocrdata_id': ocrdata_obj.entry_id,
        }
    return data
    
# 検索条件編集
class EvcEditOcrDataView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Fms_Ocrform/FE_EditOcrData.html'
    form_class = EvcEditOcrDataForm

    def get_success_url(self):
        return reverse('Fms_Ocrform:ocrdata_edit',
                       kwargs={
                           'model_name': self.kwargs['model_name'],
                           'ocrdata_id': self.kwargs['ocrdata_id'],
                           'image_no': self.kwargs['image_no']
                       }
                      )

    def get_template_names(self):
        model_name = self.kwargs['model_name']  # URLからモデル名を取得	
        if model_name == 'ocrdata':
            template_name = 'Fms_Ocrform/FE_EditOcrData.html'
        elif model_name == 'timesheet':
            template_name = 'Fms_Ocrform/FE_EditTimesheet.html'
        elif model_name == 'entry':
            template_name = 'Fms_Ocrform/FE_EditEntry.html'
        elif model_name == 'jafyame':   # JAふくおか八女
            template_name = 'Fms_Ocrform/FE_EditJafyame.html'
        else:
            template_name = self.template_name

        return [template_name]
    def get_form_class(self):
        '''
        モデルによってフォームを動的に変更する
        '''
        model_name = self.kwargs['model_name']  # URLからモデル名を取得	
        if model_name == 'ocrdata':
            form_class = EvcEditOcrDataForm
        elif model_name == 'timesheet':
            form_class = EvcEditTimesheetForm
        elif model_name == 'entry':
            form_class = EvcEditEntryForm
        elif model_name == 'jafyame':   # JAふくおか八女
            form_class = EvcEditJafyameForm
        else:
            form_class = self.form_class
        return form_class
   
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.kwargs.get('model_name')
        model_class = MODEL_CLASSES.get(model_name)
        if not model_class:
            return context
        ocrdata_id = self.kwargs.get('ocrdata_id')
        process_title = PROCESS_TITLE_EDIT.get(model_name)
        context['process_title'] = process_title
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name

        areas = ''
        image_no = self.kwargs.get('image_no') or 1
        try:
            q_objects = ''
            if model_name == 'ocrdata':
                q_objects = Q(ocrdata_id=ocrdata_id)
            elif model_name == 'timesheet':
                q_objects = Q(timesheet_id=ocrdata_id)
            elif model_name == 'entry':
                q_objects = Q(entry_id=ocrdata_id)
            elif model_name == 'jafyame':   # JAふくおか八女
                q_objects = Q(jafyame_id=ocrdata_id)
            ocrdata_obj = model_class.objects.get(q_objects)
        except model_class.DoesNotExist:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                             f'EvcEditOcrDataView {model_name=} DoesNotExist {ocrdata_id}')
            return context
        try:
            # iframeに表示するファイルのurl
            filepath = ocrdata_obj.file_path
            # filepath = b_pdf.decode('utf-8')
            url = sv_file2url(filepath)
            if model_name == 'jafyame': # JAふくおか八女 部課フォルダ
                imagpath = svf_get_jafyame_imagepath(ocrdata_obj.dept, ocrdata_obj.section, ocrdata_id, image_no)
            else:
                imagpath = svf_get_ocrdata_imagepath(model_name, ocrdata_obj.processed_ym, ocrdata_id, image_no)
            imgurl = sv_file2url(imagpath)

            ext = os.path.splitext(os.path.basename(filepath))[1] if filepath else ''
            if ext.lower() == '.pdf':
                context['src_pdffile'] = True
                context['pdffile'] = url
                context['imgfile'] = imgurl
            else:
                context['src_pdffile'] = False
                # context['imgfile'] = url
                context['imgfile'] = imgurl
            context['pdf_name'] = ocrdata_obj.pdf_name
            if model_name == 'entry':
                # 輪郭枠座標をjson文字列に変換(javascriptで処理)
                areas = svf_get_area_jsonstr(ocrdata_obj.entry_area, image_no)
                context['areas'] = areas
                # アップロードしたファイルの情報をセッション変数で取得
                if 'entry_pages' in self.request.session:
                    entry_pages = self.request.session.get('entry_pages')
                else:
                    entry_pages = self.get_entry_pages(ocrdata_obj)
                if entry_pages:
                    uploadfile = entry_pages[image_no - 1]
                    context['object_list'] = uploadfile.get('text')
        except Exception:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                             f'EvcEditOcrDataView get pdf url exception {ocrdata_obj.pdf_name}')
        # context['fulltext'] = ocrdata_obj.pdf_handbook#fulltext

        # iframe インラインでは1MBくらいまでしか表示されない
        # pdfbase64 = base64.b64encode(ocrdata_obj.evidence_data).decode()
        # context['pdffile'] = 'data:application/pdf;base64,' + pdfbase64
        # 前頁・次頁対応ページング
        if model_name == 'entry':
            page_cnt = 1
            ext = os.path.splitext(os.path.basename(filepath))[1] if filepath else ''
            if ext.lower() == '.pdf':
                cnt = sv_get_pdfpages(filepath)
                if cnt and 0 < cnt:
                    page_cnt = cnt
            imageno_list = list(range(1, page_cnt + 1))
    
            page_obj = self.get_page_obj_entry(imageno_list, image_no)  # ページ遷移
            context['page_obj'] = page_obj
            if page_obj.has_next():
                context['next_image_no'] = imageno_list[page_obj.next_page_number() - 1]
            if page_obj.has_previous():
                context['previous_image_no'] = imageno_list[page_obj.previous_page_number() - 1]
            context['ocrdata_id'] = ocrdata_id
        else:
            if 'ocrdata_lists' in self.request.session:
                ocrdata_lists = self.request.session['ocrdata_lists']
                page_obj = self.get_page_obj(ocrdata_lists, ocrdata_id) # 文書遷移
                context['page_obj'] = page_obj
                if page_obj.has_next():
                    context['next_ocrdata_id'] = ocrdata_lists[page_obj.next_page_number() - 1]
                if page_obj.has_previous():
                    context['previous_ocrdata_id'] = ocrdata_lists[page_obj.previous_page_number() - 1]
        context['image_no'] = image_no  # export_zipのパラメータのため設定(エラー時のリダイレクト)
        if 'form' not in kwargs:
            default_data = get_scon_info(ocrdata_obj)
            if model_name == 'ocrdata':
                form = EvcEditOcrDataForm(initial = default_data)
            elif model_name == 'timesheet':
                form = EvcEditTimesheetForm(initial = default_data)
            elif model_name == 'entry':
                form = EvcEditEntryForm(initial = default_data)
            elif model_name == 'jafyame':   # JAふくおか八女
                form = EvcEditJafyameForm(initial = default_data)
            else:
                form = None
            context['form'] = form
        return context

    def form_valid(self, form):
        #  name='submit_action' を3つのformに定義(idは別)
        act = self.request.POST.get('submit_action')
        model_name = self.kwargs.get('model_name')

        owner_id = self.request.session.get('owner_id')
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'EvcEditOcrDataView {model_name=} {act=}')
        user_id = self.request.user.user_id
        ocrdata_id = form.cleaned_data.get('ocrdata_id')
        image_no = self.kwargs.get('image_no') or 1

        if act == 'commit': # 登録
            category = form.cleaned_data.get('category')
            if category and category != '0':
                category_name = category
            else:
                category_name = ''
            if model_name == 'ocrdata':
                data_dict = {
                    'tr_no': form.cleaned_data.get('tr_no'),
                    'nx_tr_no': form.cleaned_data.get('nx_tr_no'),
                    # 'process_date': form.cleaned_data.get('process_date')
                }
                # Ocr文書情報テーブル更新
                id = svf_update_ocrdata(ocrdata_id, data_dict, user_id)
            elif model_name == 'timesheet':
                target_month = form.cleaned_data.get('target_month')
                if target_month:
                    target_ymd = f'{target_month.replace("/", "").replace("-", "")}01'
                    s_format = '%Y%m%d'
                    target_date = datetime.datetime.strptime(target_ymd, s_format)
                else:
                    target_date = None
                data_dict = {
                    'target_date': target_date,
                    'office_name': form.cleaned_data.get('office_name'),
                    'emp_name': form.cleaned_data.get('emp_name'),
                    'emp_id': form.cleaned_data.get('emp_id'),
                    'process_date': form.cleaned_data.get('process_date')
                }
                # 勤務表情報テーブル更新
                id = svf_update_timesheet(ocrdata_id, data_dict, user_id)
            elif model_name == 'entry':
                json_str = self.request.POST.get('object_list_json')
                if json_str:
                    entry_pages = self.set_entry_pages(json_str, image_no)
                else:
                    entry_pages = []
                # データ更新
                id = svf_update_entry(ocrdata_id, entry_pages, user_id)
            elif model_name == 'jafyame':   # JAふくおか八女
                processed_date = form.cleaned_data.get('processed_date')

                data_dict = {
                    'processed_date': processed_date,
                    'dept': form.cleaned_data.get('dept'),
                    'section': form.cleaned_data.get('section'),
                    'spine': form.cleaned_data.get('spine'),
                    'username': form.cleaned_data.get('username')
                }
                # JAふくおか八女 情報テーブル更新
                id = svf_update_jafyame(ocrdata_id, data_dict, user_id)
            
            if id:
                messages.success(self.request, 'データを登録しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOcrDataView データを登録しました {model_name=} {ocrdata_id}')
            else:
                messages.error(self.request, 'データ登録に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'EvcEditOcrDataView データ登録に失敗しました {model_name=} {ocrdata_id}')
        elif act == 'update':   # テキストデータ更新
            user_id = self.request.user.user_id
            ocrdata_id = form.cleaned_data.get('ocrdata_id')
            if model_name == 'entry':
                pass
            else:
                fulltext = form.cleaned_data.get('fulltext')
                # テキストデータ更新
                id = svf_update_shiori(model_name, ocrdata_id, fulltext, user_id)
                if id:
                    messages.success(self.request, 'テキストデータを更新しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOcrDataView テキストデータを更新しました {model_name=} {ocrdata_id}')
                else:
                    messages.error(self.request, 'データ更新に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOcrDataView データ更新に失敗しました {model_name=} {ocrdata_id}')
        elif act == 'cancel':   # 戻る
            # セッションデータをここで削除してもページ遷移後のlist表示で作成されるのでログアウト時に削除
            # if 'ocrdatalist' in self.request.session:
            #     del self.request.session['ocrdatalist']

            # 検索条件が異なる更新をした場合に戻るとおかしくなる
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            # self.request.session['callfrom'] = 'sconcreate'
            return redirect('Fms_Ocrform:ocrdata_list', model_name=model_name)
        elif act == 'delete':   # 削除
            user_id = self.request.user.user_id
            ocrdata_id = form.cleaned_data.get('ocrdata_id')
            #  文書情報削除/ファイル削除 
            name = svf_delete_ocrdata(model_name, ocrdata_id, user_id, owner_id)
            if name:
                basename = os.path.splitext(name)[0]
                messages.success(self.request, f'{basename} を削除しました')
                # self.request.session['callfrom'] = 'sconcreate'
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOcrDataView {model_name=} {ocrdata_id}:{basename} を削除しました')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'EvcEditOcrDataView データ削除に失敗しました {model_name=} {ocrdata_id}')
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            return redirect('Fms_Ocrform:ocrdata_list', model_name=model_name)
        elif act == 'download' and model_name == 'entry':   # 出力
            user_id = self.request.user.user_id
            ocrdata_id = form.cleaned_data.get('ocrdata_id')
            # fulltext = form.cleaned_data.get('fulltext')
            json_str = self.request.POST.get('object_list_json')
            if json_str:
                entry_pages = self.set_entry_pages(json_str, image_no)
            else:
                entry_pages = []
            # データ更新
            id = svf_update_entry(ocrdata_id, entry_pages, user_id)
            if id:
                # response = svt_export_zip(self.request, entry_id)
                # if response:
                #     messages.success(self.request, 'データを出力しました')
                #     logger.info('EvcSConCreateView データを出力しました ' + entry_id)
                # return response # 画面refreshが必要
                filename = svt_export_zip(self.request, ocrdata_id)
                if filename:
                    messages.success(self.request, 'データを出力しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditEntryView データを出力しました {ocrdata_id} -> {filename}')
                    return super().form_valid(form)
            messages.error(self.request, 'データ出力に失敗しました')
            logger.error(f'{ut_get_client_ip(self.request)} '
                        f'EvcEditEntryView データ出力に失敗しました {ocrdata_id=}')
        elif (act == 'back_btn' or act == 'next_btn') and model_name == 'entry':    # 前頁・次頁対応ページング
            json_str = self.request.POST.get('object_list_json')
            self.set_entry_pages(json_str, image_no)    # セッション変数に編集内容を保存
            ocrdata_id = form.cleaned_data.get('ocrdata_id')
            if act == 'back_btn':
                pageno = image_no - 1 
            else:
                pageno = image_no + 1 
            if 0 < pageno:
                return redirect('Fms_Ocrform:ocrdata_edit',
                                 model_name=model_name,
                                 ocrdata_id=ocrdata_id,
                                 image_no=pageno
                               )

        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcEditOcrDataView データ登録に失敗しました {err}')
        return super().form_invalid(form)
    # セッション変数にデータベースのエントリーの情報を保存
    def get_entry_pages(self, entry):
        path = entry.file_path
        filename = entry.entry_name
        entry_id = entry.entry_id
        entry_pages = []
        page_cnt = 1
        basename_without_ext, ext_name = os.path.splitext(os.path.basename(path))
        if ext_name.lower() == '.pdf':
            cnt = sv_get_pdfpages(path)
            if cnt and 0 < cnt:
                page_cnt = cnt
        for i in range(1, page_cnt + 1):
            model_name = 'entry'
            img = svf_get_ocrdata_imagepath(model_name, entry.processed_ym, entry_id, i)
            # JSONデータをPythonオブジェクト(list型)へ変換
            text = get_jsontext_list(entry.entry_detail, i)
            entry_pages.append({'name':filename, 'path':path, 'imgpath':img, 'text':text})
        self.request.session['entry_pages'] = entry_pages 
        return entry_pages
    # セッション変数に編集内容を保存
    def set_entry_pages(self, json_str, image_no):
        entry_pages = []
        if 'entry_pages' in self.request.session:
            entry_pages = self.request.session.get('entry_pages')
            if entry_pages:
                uploadfile = entry_pages[image_no - 1]
                # JSONデータをPythonオブジェクト(list型)へ変換
                uploadfile['text'] = json.loads(json_str)
                entry_pages[image_no - 1] = uploadfile
                self.request.session['entry_pages'] = entry_pages
        return entry_pages
    # 前頁・次頁対応ページング(文書ID遷移)
    def get_page_obj(self, ocrdata_lists, ocrdata_id):
        page_no = 1
        for idx, evi in enumerate(ocrdata_lists):
            if evi == ocrdata_id:
                page_no = idx + 1
                break
        paginator = Paginator(ocrdata_lists, 1)
        try:
            page_obj = paginator.page(page_no)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)   
        return page_obj 
    # 前頁・次頁対応ページング（ページ遷移）
    def get_page_obj_entry(self, images, image_no):
        page_no = image_no
        paginator = Paginator(images, 1)
        try:
            page_obj = paginator.page(page_no)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)   
        return page_obj 
# フォーム初期表示のために情報を取得
def get_scon_info(ocrdata_obj):
    model_class = type(ocrdata_obj)
    if model_class == TtOcrData:
        if ocrdata_obj.search_text:
            d = json.loads(ocrdata_obj.search_text)
            tr_no = d.get('tr_no')
            nx_tr_no = d.get('nx_tr_no')
        else:
            tr_no = ''
            nx_tr_no = ''

        default_data = {
            'ocrdata_id': ocrdata_obj.ocrdata_id,
            'fulltext': ocrdata_obj.pdf_handbook,
            'tr_no' : tr_no,
            'nx_tr_no' : nx_tr_no,
        }
    elif model_class == TtTimesheet:
        if ocrdata_obj.target_date:
            target_month = ocrdata_obj.target_date.strftime('%Y-%m')
        else:
            target_month = ''

        default_data = {
            'ocrdata_id': ocrdata_obj.timesheet_id,
            'fulltext': ocrdata_obj.pdf_handbook,
            'target_month' : target_month,
            'office_name' : ocrdata_obj.office_name or '',
            'emp_name' : ocrdata_obj.emp_name or '',
            'emp_id' : ocrdata_obj.emp_id or '',
        }
    elif model_class == TtJafyame:  # JAふくおか八女
        if ocrdata_obj.processed_date:
            # processed_date = ocrdata_obj.processed_date.strftime('%Y/%m/%d')
            processed_date = ocrdata_obj.processed_date
        else:
            processed_date = ''

        default_data = {
            'ocrdata_id': ocrdata_obj.jafyame_id,
            'fulltext': ocrdata_obj.pdf_handbook,
            'processed_date' : processed_date,
            'dept' : ocrdata_obj.dept or '',
            'section' : ocrdata_obj.section or '',
            'spine' : ocrdata_obj.spine or '',
            'username' : ocrdata_obj.username or '',
        }
    elif model_class == TtEntry:
        default_data = {
            'ocrdata_id': ocrdata_obj.entry_id,
        }
    else:
        default_data = {}
    return default_data
# データベースのテキスト情報から指定ページのデータをPythonオブジェクト(list型)へ変換
# [{'item_no':'item_no','item_name':'item_name',...},...{}]
def get_jsontext_list(json_text, page_no):
    dicts = []
    # json.loads 関数 JSON 形式の文字列データから、Python オブジェクト(dict, list)を作成 
    object_list = json.loads(json_text) # JSONデータをPythonオブジェクト(list型)へ変換
    if object_list:
        try:
            for pagedata in object_list:
                if pagedata.get('page_no') == str(page_no):
                    list = pagedata.get('page_list')
                    for item in list:
                        area_no = str2int(item.get('area_no'))
                        if 0 < area_no: # 領域が設定されている項目のみ表示
                            data = {
                                'item_no': item.get('item_no'),
                                'item_name': item.get('item_name'),
                                'item_json': item.get('item_json') or '',
                                'item_text': item.get('item_text'),
                                'area_no': item.get('area_no'),
                                'table_id': item.get('table_id'),
                            }
                            dicts.append(data)
        except Exception:
            logger.exception('get_jsontext_list exception ')
    return dicts

# 連携ファイルダウンロードリクエスト
def export_zip(request, ocrdata_id, image_no):
    logger.info(f'{ut_get_client_ip(request)} '
                'zipダウンロード')
    response = svt_export_zip(request, ocrdata_id, True)
    if response:
        return response
    else:
        messages.error(request, 'データ出力に失敗しました')
        logger.error(f'{ut_get_client_ip(request)} '
                    f'データ出力に失敗しました {ocrdata_id=}')
        model_name = 'entry'
        return redirect('Fms_Ocrform:ocrdata_edit',
                            model_name=model_name,
                            ocrdata_id=ocrdata_id,
                            image_no=image_no
                        )
