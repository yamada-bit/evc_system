import os
import datetime
# import threading
# import base64
import logging
# import re   # 正規表現操作
import json

from django.shortcuts import redirect
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin,UserPassesTestMixin
from django.contrib import messages
# from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
# from django.http import HttpResponseRedirect
# from django.db.models import F  
from typing import cast
from django.http import JsonResponse
# クラス 'AnonymousUser' の属性 'user_id' にアクセスできません
# 属性 'user_id' が不明ですPylancereportAttributeAccessIssueの対処のためcast
# Pythonの型ヒント（Type Hint）用の関数で型安全性や読みやすさの向上が目的。
# 実行時の処理は何もしない。静的解析ツールやIDE向け
from users.models import EvcUser

from commons.utils import ut_get_client_ip
from Evc_App.forms import EvcUploadFileForm,EvcUploadAreaForm,EvcSelectOwnerForm

from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_file import (sv_file2url,sv_handle_uploaded_file,sv_get_filepath,
    get_rootfolder,get_imgfolder_upload,make_upload_dir,make_json_dir,make_processed_ym_dir,make_evidence_image_dir,
    sv_get_select_owner_list,sv_get_owner_ryaku_name,sv_helpurl,sv_delete_file
)
from Evc_App.sv_evidence import sv_create_evidence

from Evc_App.sv_get_image_shape import sv_get_image_shape,sv_get_image_angle,sv_upload_file_base64


VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']
IMAGE_EXTENTIONS = ['.jpg','.jpeg','.png']
# UPLOAD_DIR = settings.MEDIA_ROOT.parent.parent.joinpath('media/upload')

logger = logging.getLogger(__name__)

def health(request):
    return JsonResponse({"status": "ok"})

# 契約会社一覧表示選択
class EvcSelectOwnerView(LoginRequiredMixin, FormView):
    template_name = 'Evc_App/FE_SelectOwner.html'
    form_class = EvcSelectOwnerForm

    def get_success_url(self):
        # return reverse('Evc_App:upload')
        return reverse('accounts:mainmenu')

    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        # 選択リストをパラメタで渡す EvcSelectOwnerForm __init__()
        request_user = cast(EvcUser, self.request.user)
        user_id = request_user.user_id
        kwgs['owners'] = self.get_owner_choices(user_id)
        return kwgs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '契約会社選択'
        # path_lists = [sv_helpurl(), 'SelectOwner_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        return context

    def form_valid(self, form):
        # ModelChoiceFieldを用いると、選択肢がObjectとなってしまう
        # owner_obj = form.cleaned_data.get('owner_cd')
        # if owner_obj:
        #     owner_id = owner_obj.owner_id
        # else:
        #     owner_id = None
        owner_id = self.request.POST.get('owner')
        if owner_id and owner_id != '0':
            # セッションデータに選択された契約会社を格納する。
            self.request.session['owner_id'] = owner_id
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcSelectOwnerView select owner {owner_id=}')
        else:
            messages.error(self.request, '契約会社を選択してください。')
            return super().form_invalid(form) 
            # url = settings.LOGIN_URL   # ログイン画面に戻す
            # return HttpResponseRedirect(url)    # ログイン画面に戻す
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, '契約会社を選択してください。')
        return super().form_invalid(form)
    # 選択リストの設定
    def get_owner_choices(self, user_id):
        choices = []
        choices.append(('0', '-契約会社を選択してください。-'))
        lists = sv_get_select_owner_list(user_id)
        if lists:
            for list in lists:
                # [(owner_id,owner_ryaku_name)]
                choices.append((list[0], list[1]))
            # lists = sv_get_owner_list(user_id)
            # for list in lists:
            #     choices.append((list.owner_id, list.owner_ryaku_name))
        return choices

#Mixinを使って、オーナーIDが有効のみ編集できるようにする
class OwnerTestMixin(UserPassesTestMixin):
    raise_exception = True     # set True if raise 403_Forbidden

    def test_func(self):
        # user = self.request.user
        owner_id = self.request.session.get('owner_id')
        # セッションデータに契約会社が格納されているか。なければ403エラー
        return owner_id
        # 自分のプロフィールのみ編集できるようにする
        # return user.pk == self.kwargs['pk'] or user.is_superuser

# ファイルアップロード(ファイル保存)
class EvcUploadView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_App/FE_FileSave.html'
    form_class = EvcUploadFileForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_form()
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        # path_lists = [sv_helpurl(), 'FileSave_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        context = {
            'form': form,
            'process_title': 'ファイル保存',
            'owner_ryaku_name': owner_ryaku_name
            # 'help_url': help_url
        }
        return context
    # def get_object(self, queryset=None):
    #     return EvcUser.objects.get(user_id=self.request.user.user_id)
    def form_valid(self, form):
        logger.debug(f'{ut_get_client_ip(self.request)} '
                     f'EvcUploadView start {datetime.datetime.now()}')

        files = self.request.FILES.getlist('file')
        request_user = cast(EvcUser, self.request.user)
        user_id = request_user.user_id
        # user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id')
        rootfolder = get_rootfolder(owner_id)   # 契約会社のルートフォルダを取得
        if not rootfolder:
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'EvcUploadView rootfolder error {owner_id=}')
            messages.error(self.request, '契約会社情報が正しくありません。')
            return self.render_to_response(self.get_context_data(form=form))
        make_upload_dir(rootfolder)     # アップロードファイル格納のためのフォルダ作成
        img_upload_dir = get_imgfolder_upload(rootfolder)
        if not img_upload_dir:
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'EvcUploadView upload imgfolder error {owner_id=}')
            messages.error(self.request, '契約会社情報が正しくありません。')
            return self.render_to_response(self.get_context_data(form=form))

        # make_category_dir(owner_id)
        ymdir = make_processed_ym_dir(rootfolder)     # ファイルを保存する年月フォルダ作成
        if not ymdir:
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'EvcUploadView processed_ym_dir error {owner_id=}')
            messages.error(self.request, '契約会社情報が正しくありません。')
            return self.render_to_response(self.get_context_data(form=form))
        make_evidence_image_dir(rootfolder) # エビデンス画像ファイルを保存するフォルダ作成
        make_json_dir(rootfolder)           # jsonファイルを保存するフォルダ作成

        # json_dir = get_jsonfolder(rootfolder)
        # act = self.request.POST.get('submit_action')
        # クリックしたボタンによって異なる処理を行う(buttonタグ内のnameのプロパティ)
        if 'btn_area' in self.request.POST:     # 画像分割
            act = 'area'
        elif 'btn_cropimage' in self.request.POST:   # スマホボタン
            act = 'cropimage'
        else:   # 実行ボタン
            act = 'upload'
        specif_pages = ''
        evidence_kubun =  self.request.POST.get('evidence_kubuns')  # page/file
        if evidence_kubun and evidence_kubun == 'file': # １ファイルを1エビデンスで登録
            pass
        elif evidence_kubun and evidence_kubun == 'specif': # ページ指定
            specif_pages = self.request.POST.get('specif')
        else:   # ページごとにエビデンス登録
            evidence_kubun = 'page'
        uploadfiles = []
        # ファイルをアップロードする
        for f in files:
            # basename, extension = os.path.splitext(f.name)
            ex = os.path.splitext(f.name)
            extension = ex[1] # 拡張子を取得
            if extension.lower() in VALID_EXTENSIONS:
                basename = ex[0]
                now = datetime.datetime.now()
                time = now.strftime('_%Y%m%d-%H%M%S%f')
                name = basename + time + extension  # ファイル名の重複をさけるため時刻追加
                path = False
                if act == 'cropimage' and extension.lower() in IMAGE_EXTENTIONS:
                    imageBase64 = self.request.POST.get('photo')
                    if imageBase64:
                        imgpath = sv_get_filepath(name, rootfolder)
                        # Base64に変換された画像データを取得
                        path = sv_upload_file_base64(imageBase64, imgpath)
                    else:
                        logger.error(f'{ut_get_client_ip(self.request)} '
                                     f'EvcUploadView get_photo_base64 error {f.name}')
                if not path:
                    path = sv_handle_uploaded_file(f, name, rootfolder)
                if path:
                    uploadfiles.append({'name':f.name, 'path':path, 'imgpath':''})
                    # id = sv_save_upload_evidence(user_id, owner_id, basename)
                    # uploadfile = UploadFile(id, f.name, path, 0)
                    # uploadfiles.append(uploadfile)
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcUploadView uploadfile {f.name} -> {path}')

        if act == 'area' or act == 'cropimage':
            # ファイルをアップロードし「画面分割画面」または「画面分割プレビュー画面」へ遷移する
            areafiles = []
            # for uploadfile in uploadfiles:
            if len(uploadfiles) == 1:   # １ファイルのみ処理
                uploadfile = uploadfiles[0]
                filename = uploadfile.get('name')
                path = uploadfile.get('path')
                if act == 'area':   # PCは全ページ
                    ocrimages = sv_create_ocr_image(path, img_upload_dir, -1)
                else:   # スマホは先頭ページのみを画像分割
                    ocrimages = sv_create_ocr_image(path, img_upload_dir, 1)
                if not ocrimages:   # パスワード設定などにより読み込めない
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                 f'EvcUploadView ocrimages error {filename}')
                    messages.error(self.request, f'{filename}はパスワードまたは、処理できないファイルです。')
                else:
                    # セッション変数にアップロードしたファイルの情報を設定する
                    for img in ocrimages:
                        if act == 'area':
                            postext = ''
                        else:
                            postext = get_image_shape(img)  # スマホは画像の分割領域を取得
                        areafiles.append({'name':filename, 'path':path, 'imgpath':img, 'areas':postext})
                    self.request.session['area_files'] = areafiles 
                    if act == 'cropimage':
                        # スマホは「画面分割プレビュー画面」へ遷移する
                        logger.info(f'{ut_get_client_ip(self.request)} '
                                    f'redirect upload_cropimage {filename=}')
                        return redirect('Evc_App:upload_cropimage')
                    else:
                        # PCは「画面分割画面」へ遷移する
                        logger.info(f'{ut_get_client_ip(self.request)} '
                                    f'redirect upload_area {filename=}')
                        return redirect('Evc_App:upload_area', image_no=1)
            else:
                logger.error(f'{ut_get_client_ip(self.request)} '
                             'EvcUploadView upload failed : no file')
                messages.error(self.request, 'アップロードに失敗しました。')
            return self.render_to_response(self.get_context_data(form=form))

        # アップロードファイル情報をJSONファイルに
        # sv_save_upload_json(uploadfiles, json_dir)

        # アップロードしたファイルをエビデンス登録を実行
        areas_flg = False
        lists, error_lists = sv_create_evidence(uploadfiles, user_id, owner_id, areas_flg, evidence_kubun, specif_pages)

        cnt = len(error_lists)
        if cnt != 0:
            # エビデンス登録できないファイルがあった場合
            msgerror = '\n'.join(error_lists)
            messages.error(self.request, f'{msgerror}はパスワードまたは、処理できないファイルです。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'EvcUploadView error files {msgerror}')
        else:
            cnt = len(lists)
            if cnt == 0:
                messages.error(self.request, 'アップロードに失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             'EvcUploadView アップロードに失敗しました')
            else:
                messages.success(self.request, 'アップロードに成功しました。')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcUploadView {cnt}件 アップロードに成功しました。')
        logger.debug(f'{ut_get_client_ip(self.request)} '
                     f'EvcUploadView end {datetime.datetime.now()}')
        return self.render_to_response(self.get_context_data(form=form))
        # return redirect('Evc_App:evidence_list')
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcUploadView アップロードに失敗しました {err}')
        return super().form_invalid(form) 

# ファイルアップロード画像分割(PC)
class EvcUploadAreaView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_App/FE_UploadArea.html'
    form_class = EvcUploadAreaForm
    def get_success_url(self):
        return reverse('Evc_App:upload_area', kwargs={'image_no': self.kwargs['image_no']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        image_no = self.kwargs.get('image_no') or 1 # 表示するページ番号
        form = self.get_form()
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        imgpath = ''
        imgurl = ''
        postext = ''
        imageno_list = []
        page_obj = None
        nonset = ''
        # アップロードしたファイルの情報をセッション変数で取得
        area_files = None
        if 'area_files' in self.request.session:
            area_files = self.request.session.get('area_files')
            if area_files:
                uploadfile = area_files[image_no - 1]
                imgpath = uploadfile.get('imgpath')
                imgurl = sv_file2url(imgpath)
                postext = uploadfile.get('areas')
                # 前頁・次頁対応ページング
                imageno_list = list(range(1, len(area_files) + 1))
                page_obj = self.get_page_obj(imageno_list, image_no)
                for idx, file in enumerate(area_files):
                    if idx + 1 != image_no:
                        if file.get('areas') == '': # 領域が指定されてないページがあるか
                            nonset = 'nonset'
                            break
        # if not postext:
        #     postext = get_image_shape(imgpath)
        #     if area_files:
        #         areafiles2 = []
        #         for idx, file in enumerate(area_files):
        #             if idx + 1 == image_no:
        #                 file['areas'] = postext
        #             areafiles2.append(file)
        #         self.request.session['area_files'] = areafiles2

        # path_lists = [sv_helpurl(), 'UploadArea_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        context = {
            'form': form,
            'process_title': '画像分割',
            'owner_ryaku_name': owner_ryaku_name,
            'imgpath': imgurl,
            'image_no': image_no,
            'areas': postext,
            'angle': get_image_angle(imgpath),
            'othersareas': nonset   # 領域が指定されてないページの有無
            # 'help_url': help_url,
        }
        if page_obj:
            context['page_obj'] = page_obj
            if page_obj.has_next():
                context['next_image_no'] = imageno_list[page_obj.next_page_number() - 1]
            if page_obj.has_previous():
                context['previous_image_no'] = imageno_list[page_obj.previous_page_number() - 1]

        return context
    def form_valid(self, form):
        # act = self.request.POST.get('submit_action')
        image_no = int(self.request.POST.get('image_no') or '1')
        pageno = 0
        if 'btn_cancel' in self.request.POST:
            act = 'cancel'
        elif 'btn_save' in self.request.POST:
            act = 'save'    # 領域を保存
        elif 'btn_upload' in self.request.POST:
            act = 'upload'  # エビデンス登録
        else:
            pagebtn = form.cleaned_data.get('pagebtn')
            if pagebtn: # ページ移動
                if pagebtn == 'back_btn':
                    pageno = image_no - 1 
                else:
                    pageno = image_no + 1 
                act = 'save' if 0 < pageno else 'none'
            else:
                act = 'none'

        # image_no = int(self.request.POST.get('image_no') or '1')
        imgpath = None
        path = None
        area_files = None
        if 'area_files' in self.request.session:
            area_files = self.request.session.get('area_files')
            if act == 'cancel' or act == 'upload':
                del self.request.session['area_files']
            if area_files:
                uploadfile = area_files[image_no - 1]
                filename = uploadfile.get('name')
                path = uploadfile.get('path')
                imgpath = uploadfile.get('imgpath')
        if act == 'cancel':
            # アップロードしたファイルの削除
            if path:
                sv_delete_file(path)
            if area_files:
                for uploadfile in area_files:
                  imgpath = uploadfile.get('imgpath')
                  sv_delete_file(imgpath)
            logger.info(f'{ut_get_client_ip(self.request)} '
                        'EvcUploadAreaView cancel')
            return redirect('Evc_App:upload')
        jsonpos = form.cleaned_data.get('postext')  # JSON
        if area_files:
            areafiles2 = []
            for idx, file in enumerate(area_files):
                if idx + 1 == image_no:
                    # areafiles.append({'name':filename, 'path':path, 'imgpath':img, 'areas':''})
                    file['areas'] = jsonpos # 設定された領域を格納
                areafiles2.append(file)
            if act == 'save':   # ページ移動で領域情報をセッション変数で保存
                self.request.session['area_files'] = areafiles2
            area_files = areafiles2
        if act == 'save':
            logger.info(f'{ut_get_client_ip(self.request)} '
                        'EvcUploadAreaView save')
            if 0 < pageno:  # ページ移動
                return redirect('Evc_App:upload_area', image_no=pageno)
            else:
                messages.success(self.request, '領域を保存しました。')
                return super().form_valid(form)
        if act == 'none':
            messages.error(self.request, '不具合が発生しました。')
            return super().form_valid(form)

        # エビデンス登録を実行
        request_user = cast(EvcUser, self.request.user)
        user_id = request_user.user_id
        # user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id')
        if area_files:
            areas_flg = True
            lists, error_lists = sv_create_evidence(area_files, user_id, owner_id, areas_flg, 'page', '')
            cnt = len(lists)
        else:
            cnt = 0
        if cnt == 0:
            messages.error(self.request, 'パスワードまたは、処理できないファイルです。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                         'EvcUploadAreaView アップロードに失敗しました。')
        else:
            messages.success(self.request, 'アップロードに成功しました。')
            logger.info(f'{ut_get_client_ip(self.request)} '
                        'EvcUploadAreaView アップロードに成功しました。')
        # if imgpath:
        #     # basename_without_ext, ext_name = os.path.splitext(os.path.basename(filename))
        #     # if ext_name.lower() == '.pdf':
        #     sv_delete_file(imgpath)
        return redirect('Evc_App:upload')
        # return self.render_to_response(self.get_context_data(form=form))
    
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcUploadAreaView アップロードに失敗しました {err}')
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
# 画像の分割領域を取得
def get_image_shape(filepath):
    jsontext = ''
    if filepath:
        try:
            areas = sv_get_image_shape(filepath)
            dicts = []
            for area in areas:
                x1 = area[0]
                y1 = area[1]
                x2 = area[2]
                y2 = area[3]
                dicts.append({ 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2 })
            jsontext = json.dumps(dicts)
            logger.debug(f'get_image_shape {jsontext} : {filepath}')
        except Exception:
            logger.exception(f'get_image_shape exception {filepath=}')
    return jsontext
def get_image_angle(filepath):
    angle = 0
    try:
        angle = sv_get_image_angle(filepath)
    except Exception:
        logger.exception(f'get_image_angle exception {filepath=}')
    return angle

# ファイルアップロード画像分割プレビュー(スマホ)
class EvcUploadCropimageView(EvcUploadAreaView):
    template_name = 'Evc_App/FE_UploadCropimage.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title']= '切り出し確認'
        # path_lists = [sv_helpurl(), 'UploadCropimage_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        return context
