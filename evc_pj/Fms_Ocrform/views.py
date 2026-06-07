import json
import logging
import os

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

# from django.http import HttpResponseRedirect
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

# from django.utils import timezone
# from django.utils.timezone import make_aware
from django.shortcuts import redirect

# from django.conf import settings
from django.urls import reverse
from django.views.generic import FormView, ListView

from commons.utils import ut_get_client_ip, ut_get_localtime

# from Evc_App.sv_create_image import sv_create_ocr_image
# from Evc_App.sv_json import sv_json2textdatas
from Evc_App.sv_file import (
    get_imgfolder_upload,
    make_json_dir,
    make_upload_dir,
    sv_file2url,
    sv_handle_uploaded_file,
)
from Evc_App.sv_get_image_shape import sv_get_image_angle, sv_get_pdfpages
from Fms_Ocrform.forms import EvcEditOcrformForm, EvcOcrformListForm, EvcSaveOcrformForm
from Fms_Ocrform.models import TtOcrform
from Fms_Ocrform.svf_ocrform import (
    get_ocrform_image_dir,
    get_ocrform_rootfolder,
    make_ocrform_dir,
    make_ocrform_image_dir,
    svf_get_area_jsonstr,
    svt_create_ocrform,
    svt_delete_ocrform,
    svt_update_ocrform,
)
from users.models import EvcUser

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']
IMAGE_EXTENTIONS = ['.jpg','.jpeg','.png']

logger = logging.getLogger(__name__)

# フォーム登録(フォーム登録)
class EvcSaveOcrformView(LoginRequiredMixin, FormView):
    template_name = 'Fms_Ocrform/FE_SaveOcrform.html'
    form_class = EvcSaveOcrformForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_type = self.kwargs.get('data_type') or 1
        # data_type:1 PDFファイルのみ
        form = self.get_form()
        context.update({
            'form': form,
            'process_title': 'フォーム登録',
            'data_type': data_type
        })
        return context
    def form_valid(self, form):
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'EvcSaveOcrformView {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
        data_type = self.kwargs.get('data_type') or 1

        # files = self.request.FILES.getlist('file')
        # １ファイルだけアップロードされる
        file_obj = self.request.FILES.get('file')
        files = []
        if file_obj:
            files.append(file_obj)
        else:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcSaveOcrformView upload file empty')
            messages.error(self.request, 'アップロードに失敗しました')
            return self.render_to_response(self.get_context_data(form=form))
        user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id')
        if not owner_id:
            try:
                userobj = EvcUser.objects.get(user_id=user_id)
                owner_id = userobj.owner_id
                if owner_id == '0000000000':
                    owner_id = 'sysb001'
                    logger.debug(f'{ut_get_client_ip(self.request)} '
                        'EvcSaveOcrformView set owner_id 0000000000 -> sysb001')
                else:
                    logger.debug(f'{ut_get_client_ip(self.request)} '
                                f'EvcSaveOcrformView set owner_id {owner_id=}')
                self.request.session['owner_id'] = owner_id
            except Exception:
                logger.exception(f'{ut_get_client_ip(self.request)} '
                                'EvcSaveOcrformView owner_id error')
                messages.error(self.request, '契約会社情報が正しくありません。')
                return self.render_to_response(self.get_context_data(form=form))

        rootfolder = get_ocrform_rootfolder()   # フォーム管理のルートフォルダを取得
        if not rootfolder:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcSaveOcrformView rootfolder error')
            messages.error(self.request, 'ルートフォルダが正しくありません。')
            return self.render_to_response(self.get_context_data(form=form))
        make_upload_dir(rootfolder)     # アップロードファイル格納のためのフォルダ作成
        img_upload_dir = get_imgfolder_upload(rootfolder)
        if not img_upload_dir:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        f'EvcSaveOcrformView upload imgfolder error {rootfolder=}')
            messages.error(self.request, 'アップロードフォルダが正しくありません。')
            return self.render_to_response(self.get_context_data(form=form))

        make_ocrform_dir(rootfolder)        # フォームファイルを保存するフォルダ作成
        make_ocrform_image_dir(rootfolder)  # フォーム画像ファイルを保存するフォルダ作成
        make_json_dir(rootfolder)           # jsonファイルを保存するフォルダ作成

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
                    uploadfiles.append({'name':f.name, 'path':path})
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcSaveOcrformView uploadfiles {f.name} -> {path}')
        # フォーム登録を実行--->
        analyze_pdf = False
        # analyze_pdf:True
        #   OpenCVで矩形領域を抽出 フォームの項目領域取得
        #  「PDFMiner」ライブラリを使ってテキスト抽出（textdatasデータ）(別プロセスで処理)
        lists, error_lists, evi_lists = svt_create_ocrform(uploadfiles, user_id, owner_id,
                                                            rootfolder, data_type, analyze_pdf)

        cnt = len(error_lists)
        if cnt != 0:
            # フォーム登録できないファイルがあった場合
            msgerror = '\n'.join(error_lists)
            messages.error(self.request, f'{msgerror} はパスワードまたは、処理できないファイルです。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'EvcSaveOcrformView error files {msgerror}')
            return self.render_to_response(self.get_context_data(form=form))
        else:
            cnt = len(lists)
            if cnt == 0:
                messages.error(self.request, 'アップロードに失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             'EvcSaveOcrformView アップロードに失敗しました')
                return self.render_to_response(self.get_context_data(form=form))
            else:
                # messages.success(self.request, 'フォームアップロードしました。')
                ocrform_id = evi_lists[0] if evi_lists else '0'
                logger.info(f'{ut_get_client_ip(self.request)} '
                            'EvcSaveOcrformView アップロードに成功しました。')
        # <---
                # フォーム編集画面に遷移
                return redirect('Fms_Ocrform:edit_ocrform',
                                 data_type=data_type, ocrform_id=ocrform_id, image_no=1)
        # return redirect('Fms_Ocrform:ocrform_list')
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcSaveOcrformView アップロードに失敗しました {err}')
        return super().form_invalid(form)
# フォーム一覧
class EvcOcrformListView(LoginRequiredMixin, ListView):
    template_name = 'Fms_Ocrform/FE_OcrformList.html'
    model = TtOcrform
    ordering = '-ocrform_id'
    paginate_by = 10 # ページネーション 分割数

    def get_queryset(self):
        queryset = super().get_queryset()
        data_type = self.kwargs.get('data_type') or 1
        form = EvcOcrformListForm(self.request.GET or None)
        self.form = form

        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcOcrformListView')
        if data_type == 1:
            form_id = 'ofrm_'
        else:
            form_id = 'ocrdata_'
        queryset = queryset.filter(ocrform_id__contains=form_id)

        if form.is_valid():
            # 検索条件で絞り込み
            # フォーム名を入力
            name = form.cleaned_data.get('name')
            if name:
                ocrforms = TtOcrform.objects.filter(ocrform_name__contains=name)
                list = []
                for data in ocrforms:
                    list.append(data.ocrform_id)
                queryset = queryset.filter(ocrform_id__in=list)

        # データベースのフォームの情報を保存していたセッション変数を削除
        if 'form_pages' in self.request.session:
            del self.request.session['form_pages']
        # 一覧表示内容を取得
        lists = self.set_ocrform_lists(queryset)
        return lists

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_type = self.kwargs.get('data_type') or 1
        context.update({
            'form': self.form,
            'process_title': 'フォーム一覧',
            'data_type': data_type
        })
        # owner_id = self.request.session.get('owner_id')
        # if owner_id:
        #     owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        # else:
        #     owner_ryaku_name = ''
        # context['owner_ryaku_name'] = owner_ryaku_name
        # context['page_size'] = self.paginate_by
        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        return context

    # HTMLのテーブルに設定するデータを取得
    def set_ocrform_lists(self, queryset):
        lists = []
        for item in queryset:
            data = {
                'ocrform_id': item.ocrform_id or '',
                'ocrform_name': item.ocrform_name or '',
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

# フォーム情報編集
class EvcEditOcrformView(LoginRequiredMixin, FormView):
    template_name = 'Fms_Ocrform/FE_EditOcrform.html'
    form_class = EvcEditOcrformForm

    def get_success_url(self):
        return reverse('Fms_Ocrform:edit_ocrform',
                        kwargs={'data_type': self.kwargs['data_type'],
                                'ocrform_id': self.kwargs['ocrform_id'],
                                'image_no': self.kwargs['image_no']
                        }
                      )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_type = self.kwargs.get('data_type') or 1
        # data_type:1 表追加を有効に
        ocrform_id = self.kwargs.get('ocrform_id')
        if ocrform_id == '0000':
            try:
                result_first = TtOcrform.objects.all().first()
                if result_first:
                    ocrform_id = result_first.ocrform_id
            except Exception:
                pass
        context.update({
            'form_name': 'editocrform',
            'process_title': 'フォーム編集',
            'ocrform_id': ocrform_id,
            'data_type': data_type
            })

        # owner_id = self.request.session.get('owner_id')
        # if owner_id:
        #     owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        # else:
        #     owner_ryaku_name = ''
        # context['owner_ryaku_name'] = owner_ryaku_name
        if 'form' not in kwargs:
            default_data = {
                'fulltext': '',
            }
            form = EvcEditOcrformForm(initial = default_data)
            context['form'] = form

        try:
            ocrform_obj =  TtOcrform.objects.get(ocrform_id=ocrform_id)
        except TtOcrform.DoesNotExist:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOcrformView DoesNotExist {ocrform_id=}')
            return context
        image_no = self.kwargs.get('image_no') or 1
        try:
            pdfname = ocrform_obj.ocrform_name
            # rootfolder = get_rootfolder(owner_id)
            rootfolder = get_ocrform_rootfolder()   # フォームルートフォルダを取得
            img_dir = get_ocrform_image_dir(rootfolder)

            # アップロードしたファイルの情報をセッション変数で取得
            if 'form_pages' in self.request.session:
                form_pages = self.request.session.get('form_pages')
            else:
                # セッション変数にデータベースのフォームの情報を保存
                form_pages = self.get_form_pages(ocrform_obj, img_dir)

            if form_pages and image_no - 1 < len(form_pages):
                uploadfile = form_pages[image_no - 1]
                imgpath = uploadfile.get('imgpath')
                area = uploadfile.get('area')
                text = uploadfile.get('text')
                # 前頁・次頁対応ページング
                imageno_list = list(range(1, len(form_pages) + 1))
            else:
                imgpath = os.path.join(img_dir, ocrform_id + '_001.jpg').replace(os.sep,'/')
                area = ''
                text = ''
                imageno_list = []
            imgurl = sv_file2url(imgpath)

            context.update({
                'pdf_name': pdfname,
                'src_pdffile': False,
                'imgfile': imgurl,
                'angle': get_image_angle(imgpath),
                'areas': area,
                'object_list': text,
                })
            page_obj = self.get_page_obj(imageno_list, image_no)
            context['page_obj'] = page_obj
            if page_obj.has_next():
                context['next_image_no'] = imageno_list[page_obj.next_page_number() - 1]
            if page_obj.has_previous():
                context['previous_image_no'] = imageno_list[page_obj.previous_page_number() - 1]

        except Exception:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOcrformView exception {ocrform_id=}')
        return context

    def form_valid(self, form):
        data_type = self.kwargs.get('data_type') or 1
        ocrform_id = self.kwargs.get('ocrform_id')
        image_no = self.kwargs.get('image_no') or 1
        act = self.request.POST.get('submit_action')
        owner_id = self.request.session.get('owner_id')
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'EvcEditOcrformView {act=}')

        if act == 'commit':   # 更新
            user_id = self.request.user.user_id
            # ocrform_id = form.cleaned_data.get('ocrform_id')
            # fulltext = form.cleaned_data.get('fulltext')
            json_str = self.request.POST.get('object_list_json')
            postext = self.request.POST.get('postext')
            # lists = []
            # count = int(self.request.POST.get('object_list_num'))
            # for id in range(1, count + 1):
            #     item = self.request.POST.get(f'item_name_{id}')
            #     area = self.request.POST.get(f'area_no_{id}')
            #     data = {
            #         'item_no': str(id),
            #         'item_name': item,
            #         'area_no': area,
            #         'result': '',
            #     }
            #     lists.append(data)
            if json_str:
                form_pages = self.set_form_pages(json_str, postext, image_no)

                # フォームデータ更新
                id = svt_update_ocrform(ocrform_id, user_id, form_pages)
                if id:
                    messages.success(self.request, 'フォームデータを登録しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOcrformView フォームデータを登録しました {ocrform_id=}')
                else:
                    messages.error(self.request, 'データ登録に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                f'EvcEditOcrformView データ登録に失敗しました {ocrform_id=}')
            else:
                messages.error(self.request, '登録データがありません')
                logger.error(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOcrformView 登録データがありません {ocrform_id=}')
            return redirect('Fms_Ocrform:ocrform_list', data_type=data_type)
        elif act == 'delete':   # 削除
            user_id = self.request.user.user_id
            #  フォーム情報削除/ファイル削除
            name = svt_delete_ocrform(ocrform_id, user_id, owner_id)
            if name:
                basename = os.path.splitext(name)[0]
                messages.success(self.request, f'{basename} を削除しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOcrformView {ocrform_id}:{basename} を削除しました')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                            f'EvcEditOcrformView データ削除に失敗しました {ocrform_id=}')
            # セッション変数でリダイレクトURLを取得
            # if 'list_url' in self.request.session:
            #     url = self.request.session['list_url']
            #     return redirect(url)
            return redirect('Fms_Ocrform:ocrform_list', data_type=data_type)
        elif act == 'cancel':   # 戻る
            return redirect('Fms_Ocrform:ocrform_list', data_type=data_type)
        elif act == 'back_btn' or act == 'next_btn':    # 前頁・次頁対応ページング
            json_str = self.request.POST.get('object_list_json')
            postext = self.request.POST.get('postext')
            self.set_form_pages(json_str, postext, image_no)    # セッション変数に編集内容を保存
            if act == 'back_btn':
                pageno = image_no - 1
            else:
                pageno = image_no + 1
            if 0 < pageno:
                return redirect('Fms_Ocrform:edit_ocrform',
                                 data_type=data_type, ocrform_id=ocrform_id, image_no=pageno)
            else:
                messages.error(self.request, 'ページ番号が取得できません。')
                logger.error(f'{ut_get_client_ip(self.request)} '
                            'ページ番号が取得できません。')
                return super().form_valid(form)
        return super().form_valid(form)
    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcEditOwnerView データ登録に失敗しました {err}')
        return super().form_invalid(form)
    # セッション変数にデータベースのフォームの情報を保存
    def get_form_pages(self, ocrform_obj, img_dir):
        path = ocrform_obj.ocrform_path
        filename = ocrform_obj.ocrform_name
        ocrform_id = ocrform_obj.ocrform_id
        entry_pages = []
        page_cnt = 1
        basename_without_ext, ext_name = os.path.splitext(os.path.basename(path))
        if ext_name.lower() == '.pdf':
            cnt = sv_get_pdfpages(path)
            if cnt and 0 < cnt:
                page_cnt = cnt
        for i in range(1, page_cnt + 1):
            img =  os.path.join(img_dir, ocrform_id + f'_{i:03d}.jpg').replace(os.sep,'/')
            # 輪郭枠座標をjson文字列に変換(javascriptで処理)
            area = svf_get_area_jsonstr(ocrform_obj.ocrform_area, i)
            # JSONデータをPythonオブジェクト(list型)へ変換
            text = get_jsontext_list(ocrform_obj.ocrform_text, i)

            entry_pages.append({
                 'name':filename,
                 'path':path,
                 'imgpath':img,
                 'area':area,
                 'text':text
                })
        self.request.session['form_pages'] = entry_pages
        return entry_pages
    # セッション変数に送信されてきた編集内容を保存
    def set_form_pages(self, json_str, postext, image_no):
        form_pages = []
        if 'form_pages' in self.request.session:
            form_pages = self.request.session.get('form_pages')
            if form_pages and image_no - 1 < len(form_pages):
                uploadfile = form_pages[image_no - 1]
                uploadfile['area'] = postext
                # JSONデータをPythonオブジェクト(list型)へ変換
                uploadfile['text'] = json.loads(json_str)
                form_pages[image_no - 1] = uploadfile
                self.request.session['form_pages'] = form_pages
        return form_pages
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
# フォームテキスト情報を取得し指定ページのデータをPythonオブジェクト(list型)へ変換
def get_jsontext_list(ocrform_text, page_no):
    dicts = []
    if not ocrform_text:
        data = {
            'item_no': '1',
            'item_name': '項目データなし',
            'area_no': '',
            'item_json': '',
            'table_id': '',
        }
        dicts.append(data)
        return dicts
    # json.loads 関数 JSON 形式の文字列データから、Python オブジェクト(dict, list)を作成
    object_list = json.loads(ocrform_text) # JSONデータをPythonオブジェクト(list型)へ変換
    if object_list:
        try:
            for pagedata in object_list:
                if pagedata.get('page_no') == str(page_no):
                    list = pagedata.get('page_list')
                    if list:
                        for item in list:
                            data = {
                                'item_no': item.get('item_no'),
                                'item_name': item.get('item_name'),
                                'area_no': item.get('area_no'),
                                'item_json': item.get('item_json') or '',
                                'table_id': item.get('table_id') or '',
                                # 'table_id': table_id,
                            }
                            dicts.append(data)
                    else:   # データがない場合ダミーで１行作成
                        data = {
                            'item_no': '1',
                            'item_name': '項目データなし',
                            'area_no': '',
                            'item_json': '',
                            'table_id': '',
                        }
                        dicts.append(data)

        except Exception:
            logger.exception('get_jsontext_list exception ')
    return dicts
# ocrfom_idのリストを取得
def get_ocrform_ids():
    ids = []
    try:
        ids = list(TtOcrform.objects.all()\
                   .order_by('ocrform_id')\
                   .values_list('ocrform_id', flat=True)
                   )
    except Exception:
        logger.exception('get_ocrform_id exception ')
    return ids
# def get_image_shape(ocrform_id, page_no):
#     jsontext = ''
#     if ocrform_id:
#         try:
#             ocrform_obj =  TtOcrform.objects.get(ocrform_id=ocrform_id)
#         except TtOcrform.DoesNotExist:
#             return ''
#         try:
#             jsontext = sv_get_area_jsonstr(ocrform_obj.ocrform_area, page_no)
#             logger.debug('get_image_shape  : ' + jsontext + ':' + ocrform_id)
#         except Exception:
#             logger.exception('get_image_shape exception : ' + ocrform_id)
#     return jsontext
# 回転角度を取得
def get_image_angle(filepath):
    angle = 0
    try:
        angle = sv_get_image_angle(filepath)
    except Exception:
        logger.exception(f'get_image_angle exception {os.path.basename(filepath)}')
    return angle
