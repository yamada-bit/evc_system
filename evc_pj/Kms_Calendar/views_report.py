import logging
import os

# import json
import re  # 正規表現操作

# import calendar
# import csv,urllib
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

# from django.http import HttpResponse
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

# from django.utils import timezone
# from django.utils.timezone import make_aware
from django.shortcuts import redirect

# from django.conf import settings
from django.urls import reverse
from django.views.generic import FormView, ListView

from commons.utils import ut_get_client_ip, ut_get_localtime, ut_get_localtoday

# from Evc_App.sv_json import sv_load_jsonfile,sv_json2textdatas,sv_datas2json
from Evc_App.sv_file import (
    get_imgfolder_upload,
    make_json_dir,
    make_upload_dir,
    sv_file2url,
    sv_get_user_authority,
    sv_handle_uploaded_file,
)
from Kms_Calendar.forms import EditReportForm, ReportListForm, UploadReportForm
from Kms_Calendar.models import TtGaikinReport
from Kms_Calendar.svk_report import (
    svk_create_report,
    svk_get_gaikin_rootfolder,
    svk_get_report_imagepath,
    svk_make_report_dir,
    svk_physical_delete_report,
    svk_update_report,
)
from users.models import EvcUser

# from Fms_Ocrform.svt_entry import (sv_create_entry, sv_update_shiori,
#                                       sv_delete_entry, sv_create_entry_image)
# from Evc_App.sv_get_image_shape import sv_get_pdfpages

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']
IMAGE_EXTENTIONS = ['.jpg','.jpeg','.png']

logger = logging.getLogger(__name__)

# 外勤報告書ファイルアップロード(ファイル保存)
class KmsUploadReportView(LoginRequiredMixin, FormView):
    template_name = 'Kms_Calendar/Kms_SaveReport.html'
    form_class = UploadReportForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_form()
        context = {
            'form': form,
            'process_title': 'ファイル保存',
        }
        return context
    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        return kwgs

    def form_valid(self, form):
        logger.debug(f'{ut_get_client_ip(self.request)} '
                    f'KmsUploadReportView {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')

        files = self.request.FILES.getlist('file')
        user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id')
        rootfolder = svk_get_gaikin_rootfolder()   # ルートフォルダを取得
        if not rootfolder:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'KmsUploadReportView upload rootfolder error')
            messages.error(self.request, '保存フォルダが正しく設定されていません。')
            return self.render_to_response(self.get_context_data(form=form))
        make_upload_dir(rootfolder)     # アップロードファイル格納のためのフォルダ作成
        img_upload_dir = get_imgfolder_upload(rootfolder)   # アップロード画像ファイル格納フォルダ
        if not img_upload_dir:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        f'KmsUploadReportView upload imgfolder error {rootfolder=}')
            messages.error(self.request, 'アップロードフォルダが正しく設定されていません。')
            return self.render_to_response(self.get_context_data(form=form))

        svk_make_report_dir(rootfolder) # 外勤報告書ファイルを保存するフォルダ作成
        make_json_dir(rootfolder)   # jsonファイルを保存するフォルダ作成

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
                    uploadfiles.append({'name':f.name, 'path':path})
                    # id = sv_save_upload_entry(user_id, owner_id, basename)
                    # uploadfile = UploadFile(id, f.name, path, 0)
                    # uploadfiles.append(uploadfile)
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'KmsUploadReportView uploadfiles {f.name} -> {path}')
        # 外勤報告書情報登録を実行--->
        lists, error_lists = svk_create_report(uploadfiles, user_id, owner_id)

        cnt = len(error_lists)
        if cnt != 0:
            # 外勤報告書情報登録できないファイルがあった場合
            msgerror = '\n'.join(error_lists)
            messages.error(self.request, f'{msgerror}はパスワードまたは、処理できないファイルです。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                         f'KmsUploadReportView error files {msgerror}')
        else:
            cnt = len(lists)
            if cnt == 0:
                messages.error(self.request, 'アップロードに失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             'KmsUploadReportView アップロードに失敗しました')
            else:
                messages.success(self.request, 'アップロードに成功しました。')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'KmsUploadReportView {cnt}件 アップロードに成功しました。')
        # <---
        return self.render_to_response(self.get_context_data(form=form))
        # return redirect('Fms_Ocrform:entry_list')
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'KmsUploadReportView アップロードに失敗しました {err}')
        return super().form_invalid(form)
"""
# PostgreSQLデータベースに外勤報告書情報テーブルを作成
def create_report_tabel():
    # データベースに接続
    conn = psycopg.connect(
        "dbname=kms_db user=postgres password=postgres host=localhost port=5432")
    # カーソルを作成
    cur = conn.cursor()

    # テーブル作成SQLを実行
    query = 'CREATE TABLE IF NOT EXISTS public."tt_gaikin_report" ( \
        report_id character varying(20) not null,\
        report_name character varying(50),\
        owner_id character varying(10),\
        pdf_name character varying(50),\
        file_path character varying(100),\
        processed_ym character varying(6),\
        create_user character varying(30),\
        create_date timestamp(6) without time zone,\
        update_user character varying(30),\
        update_date timestamp(6) without time zone,\
        primary key (report_id)\
    );'

    cur.execute(query)
    # コミットして変更を反映
    conn.commit()
    # クローズ
    cur.close()
    conn.close()
def delete_report():
    svk_physical_delete_all()

"""
# 外勤報告書情報一覧表示
class KmsReportListView(LoginRequiredMixin, ListView):
    template_name = 'Kms_Calendar/Kms_ReportList.html'
    model = TtGaikinReport
    ordering = '-report_id'
    paginate_by = 10 # ページネーション 分割数

    # def get_queryset(self, **kwargs):
    #     queryset = super().get_queryset(**kwargs) # TtEntry.objects.all() と同じ結果
    #     # GETリクエストパラメータにkeywordがあれば、それでフィルタする
    #     keyword = self.request.GET.get('keyword')
    #     if keyword is not None:
    #         queryset = queryset.filter(title__contains=keyword)
    #         messages.success(self.request, '「{}」の検索結果'.format(keyword))
    #     queryset = queryset.order_by('-report_id')
    #     return queryset
    def get_queryset(self):
        # queryset = super().get_queryset().order_by(F('processed_date').desc(nulls_last=True))
        queryset = super().get_queryset()
        owner_id = self.request.session.get('owner_id')
        user_id = self.request.user.user_id
        if not owner_id:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'KmsReportListView session owner_id is None')

        today = ut_get_localtoday()
        yearmonth = today.strftime('%Y-%m')
        form_month = self.request.GET.get('report_month', yearmonth)
        # request.GET 型でリクエスト　QueryDict型で初期化
        if not self.request.GET.get('report_id'):
            initial_data = {
                'report_month': form_month,
            }
            form = ReportListForm(None, initial=initial_data)
        else:
            # request.GET : requestの情報を辞書型のデータで取得
            form = ReportListForm(self.request.GET or None)
        self.form = form

        if form.is_valid():
            # バリデーションを実行しデータが有効
            report_id = self.request.GET.get('report_id')
            act = self.request.GET.get('act')   # 削除ボタンがクリックされたら'del'が設定されている
            if report_id and act == 'del':
                try:
                    report_obj =  TtGaikinReport.objects.get(report_id=report_id,delete_flg=0)
                    user_id = self.request.user.user_id
                    # 外勤報告書情報削除/ファイル削除
                    # name = svk_delete_report(report_id, None, None, None, user_id)
                    name = svk_physical_delete_report(report_id)
                    if name:
                        basename = os.path.splitext(name)[0]
                        messages.success(self.request, basename + '： を削除しました')
                        logger.info(f'{ut_get_client_ip(self.request)} '
                                    f'KmsReportListView {report_id}:{basename} を削除しました')
                    else:
                        messages.error(self.request, 'データ削除に失敗しました')
                        logger.error(f'{ut_get_client_ip(self.request)} '
                                        f'KmsReportListView データ削除に失敗しました {report_id}')
                except TtGaikinReport.DoesNotExist:
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                    f'KmsReportListView DoesNotExist データ削除に失敗しました {report_id}')
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'KmsReportListView {form_month}')
        # オーナーIDでで絞り込み
        # queryset = queryset.filter(owner_id=owner_id,delete_flg=0)
        queryset = queryset.filter(delete_flg=0)
        user_authority = sv_get_user_authority(user_id)
        if user_authority == '一般':
            queryset = queryset.filter(create_user=user_id) # ログインユーザ
        # 検索条件で絞り込み
        queryset = filter_report(queryset, form_month)
        # テーブル表示内容を取得
        lists = self.set_report_lists(queryset)

        # 検索条件編集からの戻りのurlをセッションデータに
        list_url = self.request.get_full_path()   #build_absolute_uri()
        list_url = re.sub('page=[0-9]+', 'page=1', list_url)
        list_url = re.sub('report_id=[0-9]+_[0-9]+', 'report_id=', list_url)
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

        # owner_id = self.request.session.get('owner_id')
        # owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)

        context['process_title'] = '外勤報告書情報一覧'
        context['owner_ryaku_name'] = ''

        return context
    # HTMLのテーブルに設定するデータを取得
    def set_report_lists(self, queryset):
        lists = []
        item_no = 1
        for item in queryset:
            if item.processed_ym:
                dt = item.processed_ym[:4] + '/ ' + item.processed_ym[4:]
            else:
                dt = ''
            # try:
            #     dt = item.create_date.strftime('%Y/%m')
            # except Exception:
            #     dt = ''
            userobj = EvcUser.objects.filter(user_id=item.create_user).first()
            user_name = userobj.user_name if userobj else ''

            filepath = item.file_path
            url = sv_file2url(filepath)
            data = {
                'item_no': str(item_no),
                'report_name': item.report_name,
                'pdf_name': os.path.splitext(item.pdf_name)[0],
                'processed_ym': dt,
                'notes': item.notes,
                'user_name': user_name,
                'report_id': item.report_id,
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

# 検索条件で絞り込み
def filter_report(queryset, report_month):
    # 処理年月: yyyy/mm yyyy-mm
    if report_month:
        try:
            dt = report_month.replace('/', '').replace('-', '')
            if 6 < len(dt):
                dt = dt[:6]
            # bom = datetime.datetime.strptime(dt + '01','%Y%m%d')
            # eom = bom.replace(day=calendar.monthrange(bom.year, bom.month)[1])
            date_from = dt
            date_to = dt
            if date_from and date_to:
                queryset = queryset.filter(processed_ym__range=[date_from, date_to]).order_by('processed_ym')
            elif date_from:
                queryset = queryset.filter(processed_ym__gte=date_from).order_by('processed_ym')
            elif date_to:
                queryset = queryset.filter(processed_ym__lte=date_to).order_by('processed_ym')
        except Exception:
            pass

    return queryset

# 外勤報告書情報編集
class KmsEditReportView(LoginRequiredMixin, FormView):
    template_name = 'Kms_Calendar/Kms_EditReport.html'
    form_class = EditReportForm

    def get_success_url(self):
        return reverse('Kms_Calendar:edit_report', kwargs={'report_id': self.kwargs['report_id']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_id = self.kwargs.get('report_id')
        # owner_id = self.request.session.get('owner_id')
        # owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context.update({
            'form_name': 'editreport',
            'process_title': '報告書情報編集',
            'report_id': report_id,
            'owner_ryaku_name': ''  # owner_ryaku_name,
            })
        try:
            report_obj =  TtGaikinReport.objects.get(report_id=report_id)
        except TtGaikinReport.DoesNotExist:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            f'KmsEditReportView TtGaikinReport DoesNotExist {report_id=}')
            return context
        if 'form' not in kwargs:
            if report_obj.processed_ym:
                report_month = report_obj.processed_ym[:4] + '-' + report_obj.processed_ym[4:]
            else:
                report_month = ''
            default_data = {
                'report_id': report_obj.report_id,
                'report_name': report_obj.report_name,
                'report_month': report_month,
                'notes': report_obj.notes
            }
            form = EditReportForm(initial = default_data)
            context['form'] = form

        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'KmsEditReportView {report_id=}')

        # image_no = self.kwargs.get('image_no') or 1
        try:
            # 表示するファイルのurl
            filepath = report_obj.file_path
            url = sv_file2url(filepath)
            images =  svk_get_report_imagepath(report_obj)
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
                'pdf_name': report_obj.pdf_name,
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
                            'KmsEditReportView exception')
        return context

    def form_valid(self, form):
        act = self.request.POST.get('submit_action')

        # owner_id = self.request.session.get('owner_id')
        # image_no = self.kwargs.get('image_no') or 1
        report_id = form.cleaned_data.get('report_id')

        if act == 'update':   # 更新
            user_id = self.request.user.user_id
            return super().form_valid(form)
        elif act == 'commit':   # 登録
            user_id = self.request.user.user_id
            report_name = form.cleaned_data.get('report_name')
            report_month = form.cleaned_data.get('report_month')
            if report_month:
                processed_ym = report_month.replace('/', '').replace('-', '')
            else:
                processed_ym = ''
            notes = form.cleaned_data.get('notes')

            #  外勤報告書情報データ更新
            id = svk_update_report(report_id, report_name, processed_ym, notes, user_id)
            if id:
                messages.success(self.request, 'データを更新しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'KmsEditReportView データを更新しました {report_id=}')
            else:
                messages.error(self.request, 'データ更新に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'KmsEditReportView データ更新に失敗しました {report_id=}')
            return super().form_valid(form)
        elif act == 'cancel':   # 戻る
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            return redirect('Kms_Calendar:report_list')
        elif act == 'delete':   # 削除
            user_id = self.request.user.user_id
            report_name = form.cleaned_data.get('report_name')
            report_month = form.cleaned_data.get('report_month')
            if report_month:
                processed_ym = report_month.replace('/', '').replace('-', '')
            else:
                processed_ym = ''
            notes = form.cleaned_data.get('notes')

            # 外勤報告書情報削除/ファイル削除
            # name = svk_delete_report(report_id, report_name, processed_ym, notes, user_id)
            name = svk_physical_delete_report(report_id)
            if name:
                basename = os.path.splitext(name)[0]
                messages.success(self.request, f'{basename} を削除しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'KmsEditReportView {report_id}:{basename} を削除しました')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'KmsEditReportView データ削除に失敗しました {report_id}')
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            return redirect('Kms_Calendar:report_list')

        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'KmsEditReportView データ登録に失敗しました {err}')
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

