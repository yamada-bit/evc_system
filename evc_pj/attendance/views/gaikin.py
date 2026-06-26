"""
外勤報告書ビュー（旧 Kms_Calendar/views_report.py から移設）。

【URL パターン】
  /attendance/gaikin/              → GaikinListView   (一覧 + 削除)
  /attendance/gaikin/upload/       → GaikinUploadView (アップロード)
  /attendance/gaikin/edit/<id>/    → GaikinEditView   (編集 + 削除)

【owner_id の扱い】
  アップロード時に request.session['owner_id'] から取得し GaikinReport.owner_id に保存する。
  一覧・編集ではユーザー権限（is_staff）に応じて閲覧範囲を切り替える。
"""
import logging
import os
import re

from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, ListView

from commons.utils import ut_get_client_ip, ut_get_localtime, ut_get_localtoday
from Evc_App.sv_file import (
    get_imgfolder_upload,
    make_json_dir,
    make_upload_dir,
    sv_file2url,
    sv_get_user_authority,
    sv_handle_uploaded_file,
)
from ..forms import GaikinEditForm, GaikinListForm, GaikinUploadForm
from ..utils.db_utils import build_user_map
from ..models import GaikinReport
from ..services.gaikin import (
    create_report,
    get_gaikin_rootfolder,
    get_report_imagepath,
    make_report_dir,
    physical_delete_report,
    update_report,
)
from ._base import AttendanceLoginMixin, using_db

logger = logging.getLogger(__name__)

_VALID_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff']


# ---------------------------------------------------------------------------
# アップロード
# ---------------------------------------------------------------------------

class GaikinUploadView(AttendanceLoginMixin, FormView):
    template_name = 'attendance/gaikin/upload.html'
    form_class = GaikinUploadForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '外勤報告書アップロード'
        return context

    def form_valid(self, form):
        logger.debug(f'{ut_get_client_ip(self.request)} GaikinUploadView {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')

        files = self.request.FILES.getlist('file')
        user_id = self.request.user.user_id
        owner_id = self.request.session.get('owner_id', '')
        rootfolder = get_gaikin_rootfolder()
        if not rootfolder:
            messages.error(self.request, '保存フォルダが正しく設定されていません。管理者に連絡してください。')
            return self.render_to_response(self.get_context_data(form=form))

        make_upload_dir(rootfolder)
        img_upload_dir = get_imgfolder_upload(rootfolder)
        if not img_upload_dir:
            messages.error(self.request, 'アップロードフォルダが正しく設定されていません。')
            return self.render_to_response(self.get_context_data(form=form))

        make_report_dir(rootfolder)
        make_json_dir(rootfolder)

        uploadfiles = []
        for f in files:
            basename, extension = os.path.splitext(f.name)
            if extension.lower() in _VALID_EXTENSIONS:
                now = ut_get_localtime()
                time_suffix = now.strftime('_%Y%m%d-%H%M%S%f')
                name = basename + time_suffix + extension
                path = sv_handle_uploaded_file(f, name, rootfolder)
                if path:
                    uploadfiles.append({'name': f.name, 'path': path})

        ok_list, error_list = create_report(uploadfiles, user_id, owner_id)

        if error_list:
            messages.error(self.request, '、'.join(error_list) + ' はパスワード付きまたは処理できないファイルです。')
        elif not ok_list:
            messages.error(self.request, 'アップロードに失敗しました。')
        else:
            messages.success(self.request, f'{len(ok_list)}件 アップロードに成功しました。')

        return self.render_to_response(self.get_context_data(form=form))

    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました。')
        return super().form_invalid(form)


# ---------------------------------------------------------------------------
# 一覧
# ---------------------------------------------------------------------------

class GaikinListView(AttendanceLoginMixin, ListView):
    template_name = 'attendance/gaikin/list.html'
    model = GaikinReport
    paginate_by = 10
    context_object_name = 'report_list'

    def get_queryset(self):
        user_id = self.request.user.user_id
        today = ut_get_localtoday()
        default_month = today.strftime('%Y-%m')
        form_month = self.request.GET.get('report_month', default_month)

        if not self.request.GET.get('report_id'):
            form = GaikinListForm(None, initial={'report_month': form_month})
        else:
            form = GaikinListForm(self.request.GET or None)
        self.form = form

        queryset = GaikinReport.objects.using(using_db).filter(delete_flg=0)
        user_authority = sv_get_user_authority(user_id)
        if user_authority == '一般':
            queryset = queryset.filter(create_user=user_id)

        # 処理年月で絞り込み
        ym = form_month.replace('/', '').replace('-', '')[:6]
        if ym:
            queryset = queryset.filter(processed_ym=ym).order_by('processed_ym')
        else:
            queryset = queryset.order_by('-report_id')

        # 一覧に戻るための URL をセッションに保存
        list_url = self.request.get_full_path()
        list_url = re.sub(r'page=\d+', 'page=1', list_url)
        list_url = re.sub(r'report_id=[^&]*', 'report_id=', list_url)
        list_url = re.sub(r'act=del', 'act=', list_url)
        self.request.session['gaikin_list_url'] = list_url

        # 表示用データに変換
        return self._build_display_list(queryset)

    def _build_display_list(self, queryset) -> list:
        rows = list(queryset)
        user_map = build_user_map(item.create_user for item in rows if item.create_user)
        items = []
        for idx, item in enumerate(rows, start=1):
            processed = ''
            if item.processed_ym:
                processed = item.processed_ym[:4] + '/' + item.processed_ym[4:]
            user_obj = user_map.get(item.create_user)
            user_name = user_obj.user_name if user_obj else ''
            items.append({
                'item_no': str(idx),
                'report_name': item.report_name or '',
                'pdf_name': os.path.splitext(item.pdf_name or '')[0],
                'processed_ym': processed,
                'notes': item.notes or '',
                'user_name': user_name,
                'report_id': item.report_id,
                'pdffile': sv_file2url(item.file_path),
            })
        return items

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form
        context['process_title'] = '外勤報告書一覧'
        page_size = self.request.GET.get('page_size')
        try:
            context['page_size'] = int(page_size) if page_size else 10
        except ValueError:
            context['page_size'] = 10
        return context

    def get_paginate_by(self, queryset):
        page_size = self.request.GET.get('page_size')
        try:
            return int(page_size) if page_size else self.paginate_by
        except ValueError:
            return self.paginate_by

    def post(self, request, *args, **kwargs):
        report_id = request.POST.get('report_id')
        act = request.POST.get('act')
        if report_id and act == 'del':
            try:
                GaikinReport.objects.using(using_db).get(report_id=report_id, delete_flg=0)
                name = physical_delete_report(report_id)
                if name:
                    messages.success(request, f'{os.path.splitext(name)[0]}: 削除しました。')
                else:
                    messages.error(request, 'データ削除に失敗しました。')
            except GaikinReport.DoesNotExist:
                messages.error(request, '対象の報告書が見つかりません。')
        return redirect(reverse('attendance:gaikin_list'))


# ---------------------------------------------------------------------------
# 編集
# ---------------------------------------------------------------------------

class GaikinEditView(AttendanceLoginMixin, FormView):
    template_name = 'attendance/gaikin/edit.html'
    form_class = GaikinEditForm

    def get_success_url(self):
        return reverse('attendance:gaikin_edit', kwargs={'report_id': self.kwargs['report_id']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_id = self.kwargs.get('report_id')
        context.update({
            'process_title': '報告書情報編集',
            'report_id': report_id,
        })
        try:
            obj = GaikinReport.objects.using(using_db).get(report_id=report_id)
        except GaikinReport.DoesNotExist:
            logger.exception(f'GaikinEditView GaikinReport.DoesNotExist {report_id=}')
            return context

        if 'form' not in kwargs:
            report_month = ''
            if obj.processed_ym:
                report_month = obj.processed_ym[:4] + '-' + obj.processed_ym[4:]
            context['form'] = GaikinEditForm(initial={
                'report_id':    obj.report_id,
                'report_name':  obj.report_name or '',
                'report_month': report_month,
                'notes':        obj.notes or '',
            })

        # ファイルプレビュー情報
        try:
            filepath = obj.file_path or ''
            ext = os.path.splitext(os.path.basename(filepath))[1].lower() if filepath else ''
            images = get_report_imagepath(obj)
            imgurl = sv_file2url(images[0]) if images else ''
            context.update({
                'pdf_name':    obj.pdf_name or '',
                'src_pdffile': (ext == '.pdf'),
                'pdffile':     sv_file2url(filepath),
                'bk_img':      imgurl,
                'page_count':  len(images),
            })
        except Exception:
            logger.exception(f'GaikinEditView preview exception {report_id=}')
        return context

    def form_valid(self, form):
        act = self.request.POST.get('submit_action')
        report_id = form.cleaned_data.get('report_id')
        user_id = self.request.user.user_id

        if act == 'commit':
            report_name  = form.cleaned_data.get('report_name', '')
            report_month = form.cleaned_data.get('report_month', '')
            processed_ym = report_month.replace('/', '').replace('-', '') if report_month else ''
            notes = form.cleaned_data.get('notes', '')
            result = update_report(report_id, report_name, processed_ym, notes, user_id)
            if result:
                messages.success(self.request, 'データを更新しました。')
            else:
                messages.error(self.request, 'データ更新に失敗しました。')
            return super().form_valid(form)

        elif act == 'delete':
            name = physical_delete_report(report_id)
            if name:
                messages.success(self.request, f'{os.path.splitext(name)[0]} を削除しました。')
            else:
                messages.error(self.request, 'データ削除に失敗しました。')
            back_url = self.request.session.get('gaikin_list_url', reverse('attendance:gaikin_list'))
            return redirect(back_url)

        elif act == 'cancel':
            back_url = self.request.session.get('gaikin_list_url', reverse('attendance:gaikin_list'))
            return redirect(back_url)

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました。')
        return super().form_invalid(form)
