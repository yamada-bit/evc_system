# import datetime
# import calendar
# import threading
# import base64
import logging
import os
import re  # 正規表現操作
from decimal import ROUND_HALF_UP, Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

# from django.conf import settings
# from django.http import JsonResponse
from django.db.models import Sum

# import csv
# from io import TextIOWrapper
# from operator import attrgetter
# from django.utils import timezone
# from django.utils.timezone import make_aware
# from dateutil.relativedelta import relativedelta
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, ListView

from commons.utils import ut_get_client_ip, ut_get_localdate

# from Evc_App.sv_export_csv import sv_response_partner,sv_response_partner_sample
from Evc_App.sv_export_csv import sv_filter_history, sv_response_history

# from Evc_App.sv_json import sv_load_jsonfile,sv_get_textlines
from Evc_App.sv_file import (
    sv_file2url,
    sv_get_category_list,
    sv_get_evidence_filename,
    sv_get_evidence_imagepath,
    sv_get_owner_ryaku_name,
    sv_get_select_owner_list,
    sv_get_user_name,
)
from Evc_App.views import OwnerTestMixin
from Evc_App.views_evidence import get_evidence_list_info, get_scon_info
from Evc_Management.forms import (
    EvcEviHistoryListForm,
    EvcSConShowForm,
    EvcUseGoogleForm,
)
from users.models import EvcUser, HtEvidence, MtPartner, SysOwner, TtEvidence

logger = logging.getLogger(__name__)

# エビデンス変更履歴一覧
class EvcEviHistoryListView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_Management/FE_EviHistoryList.html'
    model = HtEvidence
    ordering = '-r_evidence_id'
    paginate_by = 10 # ページネーション 分割数

    # def get_object(self, queryset=None):
    #     return EvcUser.objects.get(user_id=self.request.user.user_id)
    def get_queryset(self):
        # queryset = super().get_queryset()
        # # owner_id = get_owner_id(self.request.user.user_id)
        owner_id = self.request.session.get('owner_id')
        # queryset = queryset.filter(owner_id=owner_id)
        # # initial_dict = dict(page_size=10)
        # # form = EvidenceListForm(self.request.GET or None, initial=initial_dict)
        form = EvcEviHistoryListForm(self.request.GET or None)
        form.fields['category'].choices = self.get_category_choices(owner_id)
        self.form = form
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcEviHistoryListView 検索条件で絞り込み')
        # logger.debug(f'{ut_get_client_ip(self.request)} '
        #             f'EvcEviHistoryListView query {self.request.GET.dict()}')
        lists = []
        if form.is_valid():
            # 検索ボタン押下でリスト表示
            queryset = super().get_queryset()
            queryset = queryset.filter(owner_id=owner_id)

            # 検索条件で絞り込み
            queryset = sv_filter_history(owner_id, self.request, queryset)
            # エビデンス詳細からの戻りのurlをセッションデータに
            list_url = self.request.get_full_path()   #build_absolute_uri()
            list_url = re.sub('page=[0-9]+', 'page=1', list_url)
            list_url = re.sub('evi_id=[0-9]+_[0-9]+', 'evi_id=', list_url)
            list_url = re.sub('act=del', 'act=', list_url)
            list_url = re.sub('act=duplicate', 'act=', list_url)
            self.request.session['hlist_url'] = list_url

            # 一覧表示内容を取得
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
            lists = self.set_evidence_lists(queryset, from_no, to_no)
        else:
            # セッションデータクリア
            if 'hlist_url' in self.request.session:
                del self.request.session['hlist_url']

        return lists

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form
        context['process_title'] = 'エビデンス変更履歴'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        # context['page_size'] = self.paginate_by
        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        # 検索実行しないでページ遷移した場合、checkが外れるのでcontextを使う
        kubun = self.request.GET.get('kubun')
        context['kbn'] = kubun or 'none'
        # path_lists = [sv_helpurl(), 'EviHistoryList_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url

        return context
    # カテゴリ選択リストの設定
    def get_category_choices(self, owner_id):
        choices = []
        choices.append(('0', 'カテゴリを選択'))
        lists = sv_get_category_list(owner_id)
        for list in lists:
            # if list != '注文請書':
            choices.append((list, list))
        return choices

    # HTMLのテーブルに設定するデータを取得
    def set_evidence_lists(self, queryset, from_no, to_no):
        lists = []
        item_no = 1
        for item in queryset:
            if from_no and to_no:
                if item_no < from_no or to_no < item_no:
                    data = {
                        'evi_id': item.evidence_id,
                        # 'item_no': str(item_no),
                        'r_evi_id': item.r_evidence_id
                    }
                    lists.append(data)
                    item_no += 1
                    continue

            data = get_evidence_list_info(item)
            userobj = EvcUser.objects.filter(user_id=item.update_user).first()
            user_name = '(' + (userobj.user_name or '') + ')' if userobj else ''
            kubun = ''
            if item.rireki_kbn:
                # 履歴区分にユーザ名を表示
                if item.rireki_kbn == 'U':
                    kubun = 'キー修正' + user_name
                elif item.rireki_kbn == 'O':
                    kubun = 'OCR修正' + user_name
                elif item.rireki_kbn == 'D':
                    kubun = '削除' + user_name
            data['rireki_kbn'] = kubun
            data['r_evi_id'] =  item.r_evidence_id
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
# エビデンス詳細画面(照会)
class EvcSConShowView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_Management/FE_SConShow.html'
    form_class = EvcSConShowForm

    def get_success_url(self):
        return reverse('Evc_Management:sconshow', kwargs={'r_evi_id': self.kwargs['r_evi_id'], 'mode': self.kwargs['mode']})

    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        # # owner_id = get_owner_id(self.request.user.user_id)
        owner_id = self.request.session.get('owner_id')
        # # ChoideFieldの選択肢をパラメタで渡す SConCreateForm __init__()
        kwgs['categories'] = self.get_category_choices(owner_id)
        # kwgs['partners'] = sv_get_partner_list(owner_id)
        # kwgs['publishers'] = sv_get_publisher_list(owner_id)
        # kwgs['accounts'] = sv_get_account_list(owner_id)
        return kwgs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        r_evi_id = self.kwargs.get('r_evi_id')
        mode = self.kwargs.get('mode')
        context['form_name'] = 'sconcreate'
        context['process_title'] = 'エビデンス詳細'
        # if mode == 'evi':   # 実績照会一覧からの遷移
        #     context['process_title'] = 'エビデンス詳細'
        # else:   # エビデンス変更履歴一覧からの遷移
        #     context['process_title'] = '変更履歴'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        # TtEvidenceとHtEvidenceで項目名が同一なのでオブジェクト変数が同じ
        if mode == 'evi':   # 実績照会一覧からの遷移 'evi'
            try:
                # エビデンス情報テーブル
                r_eviobj =  TtEvidence.objects.get(evidence_id=r_evi_id)
            except TtEvidence.DoesNotExist:
                return context
        else:   # エビデンス変更履歴一覧からの遷移 'r_evi'
            try:
                # エビデンス履歴情報テーブル
                r_eviobj =  HtEvidence.objects.get(r_evidence_id=r_evi_id)
            except HtEvidence.DoesNotExist:
                return context
        try:
            # 表示するファイルのurl
            filepath = sv_get_evidence_filename(r_eviobj)
            # filepath = b_pdf.decode('utf-8')
            url = sv_file2url(filepath)
            imagpath = sv_get_evidence_imagepath(r_eviobj)
            imgurl = sv_file2url(imagpath)

            ext = os.path.splitext(os.path.basename(filepath))[1]
            if ext.lower() == '.pdf':
                context['src_pdffile'] = True
                context['pdffile'] = url
                context['imgfile'] = imgurl
            else:
                context['src_pdffile'] = False
                # context['imgfile'] = url
                context['imgfile'] = imgurl
            context['pdf_name'] = r_eviobj.pdf_name
        except Exception:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            f'EvcSConShowView get pdf url exception {r_eviobj.pdf_name}')
        # context['fulltext'] = eviobj.pdf_handbook#fulltext

        # with open('D:\MyPython2022\EVC\media\img\\test_01_150.png', 'rb') as f:
        #     b_pdf =  f.read()
        # pdfbase64 = base64.b64encode(b_pdf).decode()
        # context['pdffile'] = 'data:image/png;base64,' + pdfbase64

        # iframe インラインでは1MBくらいまでしか表示されない
        # pdfbase64 = base64.b64encode(eviobj.evidence_data).decode()
        # context['pdffile'] = 'data:application/pdf;base64,' + pdfbase64

        if 'form' not in kwargs:
            # エビデンス情報テーブル　または　エビデンス履歴情報テーブル
            default_data = get_scon_info(r_eviobj)
            form = EvcSConShowForm(initial = default_data)
            context['form'] = form
        # if eviobj:
        #     if not eviobj.google_amount or eviobj.google_amount == 0:
        #         messages.error(self.request, 'パスワードが設定または、処理できないファイルです。')
        if mode == 'r_evi':
            context['object_list'] = get_diff(owner_id, r_evi_id)
        return context

    def form_valid(self, form):
        #  name='submit_action' を3つのformに定義(idは別)
        act = self.request.POST.get('submit_action')
        logger.info(f'{ut_get_client_ip(self.request)} '
                f'EvcSConShowView {act=}')

        if act == 'cancel':   # 戻る
            if 'hlist_url' in self.request.session:
                url = self.request.session['hlist_url']
                return redirect(url)
            return redirect('Evc_Management:evi_history_list')

        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ検索に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcSConShowView データ検索に失敗しました {err}')
        return super().form_invalid(form)

    # カテゴリ選択リストの設定
    def get_category_choices(self, owner_id):
        choices = []
        choices.append(('0', ''))
        lists = sv_get_category_list(owner_id)
        for list in lists:
            # if list != '注文請書':
            choices.append((list, list))
        return choices
# エビデンスの変更履歴を差分表示
def get_diff(owner_id, r_evi_id):
    dicts = []
    try:
        # エビデンス履歴情報テーブル
        htobj = HtEvidence.objects.get(owner_id=owner_id,r_evidence_id=r_evi_id)
    except HtEvidence.DoesNotExist:
        return dicts
    try:
        # エビデンス情報テーブル
        cur_evi = TtEvidence.objects.get(owner_id=owner_id,evidence_id=htobj.evidence_id)
    except TtEvidence.DoesNotExist:
        cur_evi = None  # 削除
    # エビデンス履歴情報テーブル
    queryset = HtEvidence.objects.filter(owner_id=owner_id,evidence_id=htobj.evidence_id)\
            .order_by('-update_date')
    if queryset:
        try:
            if cur_evi:
                # エビデンス情報テーブル
                after = get_obj_data(cur_evi)
            else:
                after = None
            for item in  queryset:
                # エビデンス履歴情報テーブル
                before = get_obj_data(item)
                if after:
                    difference = after.items() - before.items()
                    diff_dict = dict(difference)
                    for k, v in diff_dict.items():
                        item_name = get_item_name(k)
                        # if k == 'fulltext':
                        #     item_name = 'OCR取得テキスト'
                        # else:
                        #     item_name = get_item_name(k)
                        if item_name:
                            after_val = v
                            before_val = before.get(k)
                            if k == 'process_date' or k == 'payment_date':
                                if after_val:
                                    after_val = after_val.strftime('%Y/%m/%d')
                                if before_val:
                                    before_val = before_val.strftime('%Y/%m/%d')
                            data = {
                                'item_name': item_name,
                                'before_value': before_val,
                                'after_value': after_val,
                                'update_date': after.get('update_date'),
                                'user_name': after.get('user_name'),
                            }
                            dicts.append(data)
                after = before
        except Exception:
            logger.exception('get_diff exception ')
    return dicts
# 項目名称
def get_item_name(k):
    item_dict = {'category':'カテゴリ','partner':'取引先','publisher':'発行元','process_date':'取引日',
                 'amount':'金額','account':'科目','account_desc':'摘要',
                 'slip_number':'伝票番号','payment_date':'支払日'}
    return item_dict.get(k)
# エビデンス情報テーブル　または　エビデンス履歴情報テーブル
def get_obj_data(item):
    user_name = sv_get_user_name(item.update_user)
    update_date = ut_get_localdate(item.update_date)
    if update_date:
        update_date = update_date.strftime('%Y/%m/%d')
    else:
        update_date = ''

    data = get_scon_info(item)
    # if item.processed_date:
    #     processed_date = item.processed_date.strftime('%Y/%m/%d')
    # else:
    #     processed_date = ''

    # if item.payment_date:
    #     payment_date = item.payment_date.strftime('%Y/%m/%d')
    # else:
    #     payment_date = ''

    data['update_date'] = update_date
    data['user_name'] = user_name
    return data

# CSVダウンロードリクエスト
def export_history_csv(request):
    logger.info(f'{ut_get_client_ip(request)} '
                'CSVダウンロード')
    # print(request.GET)
    evidence_list = HtEvidence.objects.all().order_by('-evidence_id')
    # リクエストに応じて絞り込み
    owner_id = request.session.get('owner_id')
    if not owner_id:
        logger.error(f'{ut_get_client_ip(request)} '
                    'export_history_csv session owner_id is None')
    # オーナーIDで絞り込み
    queryset = evidence_list.filter(owner_id=owner_id)
    # 検索条件で絞り込み
    queryset = sv_filter_history(owner_id, request, queryset)
    # CSVを作成する
    response = sv_response_history(queryset)
    return response

# Google利用履歴
class EvcUseGoogleView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_Management/FE_UseGoogle.html'
    model = TtEvidence
    ordering = 'create_date'
    paginate_by = 10 # ページネーション 分割数

    # def get_object(self, queryset=None):
    #     return EvcUser.objects.get(user_id=self.request.user.user_id)
    # def get_queryset(self, **kwargs):
    #     queryset = super().get_queryset(**kwargs) # TtEvidence.objects.all() と同じ結果
    #     # GETリクエストパラメータにkeywordがあれば、それでフィルタする
    #     keyword = self.request.GET.get('keyword')
    #     if keyword is not None:
    #         queryset = queryset.filter(title__contains=keyword)
    #         messages.success(self.request, '「{}」の検索結果'.format(keyword))
    #     queryset = queryset.order_by('-evidence_id')
    #     return queryset
    def get_queryset(self):
        # queryset = super().get_queryset()
        # エビデンス情報テーブルから情報を取得
        queryset = super().get_queryset().filter(google_amount__isnull=False)
        # エビデンス履歴情報テーブルから削除されたエビデンスの情報を取得
        r_queryset = HtEvidence.objects.filter(google_amount__isnull=False, rireki_kbn='D').order_by('create_date')

        # queryset = super().get_queryset().filter(google_amount__isnull=False).values_list(
        #     'processed_ym','owner_id','partner_id','category_name','google_amount','create_user')
        # r_queryset = HtEvidence.objects.filter(google_amount__isnull=False).values_list(
        #     'processed_ym','owner_id','partner_id','category_name','google_amount','create_user')

        form = EvcUseGoogleForm(self.request.GET or None)
        form.fields['owner'].choices = self.get_owner_choices(self.request.user.user_id)
        self.form = form
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcUseGoogleView 検索条件で絞り込み')

        if form.is_valid():
            kubun = form.cleaned_data.get('kubun')
            # 検索条件で絞り込み
            # 契約会社を選択
            owner_id = form.cleaned_data.get('owner')
            # 処理年月: yyyy/mm
            shori_date_from = form.cleaned_data.get('shori_date1')
            shori_date_to = form.cleaned_data.get('shori_date2')
            queryset = self.filter_queryset(queryset, kubun, owner_id, shori_date_from, shori_date_to)
            r_queryset = self.filter_queryset(r_queryset, kubun, owner_id, shori_date_from, shori_date_to)
        else:
            kubun = None
            queryset = self.filter_queryset(queryset, kubun, None, None, None)
            r_queryset = self.filter_queryset(r_queryset, kubun, None, None, None)

        # 一覧表示内容を取得
        lists = self.set_evidence_lists(queryset, kubun)
        r_lists = self.set_evidence_lists(r_queryset, kubun)
        # エビデンス情報(tt_evidence)+エビデンス履歴情報(ht_evidence)
        if kubun == 'summ':
            summlists = []
            # エビデンス情報(tt_evidence)とエビデンス履歴情報(ht_evidence)の両方に存在するデータをひとつに
            for list in lists:
                ym = list.get('processed_ym')
                id = list.get('owner_id')
                amount = list.get('google_amount')
                for i, r_list in enumerate(r_lists):
                    r_ym = r_list.get('processed_ym')
                    r_id = r_list.get('owner_id')
                    if r_ym == ym and r_id == id:
                        r_amount = r_list.get('google_amount')
                        amount = amount + (r_amount or 0)
                        del r_lists[i]
                        break
                list['google_amount'] = amount
                summlists.append(list)
            for r_list in r_lists:
                summlists.append(r_list)
            lists = sorted(summlists, key = lambda x : (x.get('processed_ym'),x.get('owner_id')))
        else:
            # エビデンス情報(tt_evidence)にエビデンス履歴情報(ht_evidence)を追加
            for list in r_lists:
                lists.append(list)
            lists = sorted(lists, key = lambda x : x.get('create_date'))
        return lists

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form
        context['process_title'] = 'AI-OCR利用履歴'

        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        # 検索実行しないでページ遷移した場合、checkが外れるのでcontextを使う
        kubun = self.request.GET.get('kubun')
        context['kbn'] = kubun or 'none'
        # path_lists = [sv_helpurl(), 'UseGoogle_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url

        return context
    # 検索条件で絞り込み
    def filter_queryset(self, queryset, kubun, owner_id, shori_date_from, shori_date_to):
        if owner_id and owner_id != '0':
            queryset = queryset.filter(owner_id=owner_id)
        else:
            lists = sv_get_select_owner_list(self.request.user.user_id)
            owners = []
            for list in lists:
                owners.append(list[0])
            queryset = queryset.filter(owner_id__in=owners)

        # 処理年月: yyyy/mm
        if shori_date_from:
            shori_date_from = shori_date_from.replace('/', '').replace('-', '')
        if shori_date_to:
            shori_date_to = shori_date_to.replace('/', '').replace('-', '')

        if shori_date_from and shori_date_to:
            queryset = queryset.filter(processed_ym__range=[shori_date_from, shori_date_to])
        elif shori_date_from:
            queryset = queryset.filter(processed_ym__gte=shori_date_from)
        elif shori_date_to:
            queryset = queryset.filter(processed_ym__lte=shori_date_to)

        if kubun == 'summ':
            # 指定なし⇒明細をそのまま表示する。（並びは作成年月日の昇順）
            # 集計⇒処理年月別、契約会社別グルーピングして、Google件数を集計して表示する。
            #（取引先名、カテゴリ、利用者　）空白とする。
            queryset = queryset.values('processed_ym','owner_id').annotate(total=Sum('google_amount')).order_by('processed_ym','owner_id')
        return queryset

    # 選択リストの設定
    def get_owner_choices(self, user_id):
        choices = []
        lists = sv_get_select_owner_list(user_id)
        if lists and len(lists) == 1:
            choices.append((lists[0][0], lists[0][1]))
        else:
            choices.append(('0', '契約会社を選択'))
            if lists:
                for list in lists:
                    if list[0] and list[1]:
                        choices.append((list[0], list[1]))
        return choices

    # HTMLのテーブルに設定するデータを取得
    def set_evidence_lists(self, queryset, kubun):
        lists = []

        for item in queryset:
            if kubun == 'summ':
                create_date = None
                owner_id = item.get('owner_id')
                if item.get('processed_ym'):
                    dt = item.get('processed_ym')[:4] + '/ ' + item.get('processed_ym')[4:]
                else:
                    dt = ''
                try:
                    owner_ryaku_name =SysOwner.objects.get(owner_id=owner_id).owner_ryaku_name
                except SysOwner.DoesNotExist:
                    owner_ryaku_name = ''
                partner_ryaku_name = ''
                category_name = ''
                user_name = ''
                try:
                    amount = item.get('total').quantize(Decimal('0'), rounding=ROUND_HALF_UP)
                except Exception:
                    amount = None
            else:
                create_date = ut_get_localdate(item.create_date)
                owner_id = item.owner_id

                if item.processed_ym:
                    dt = item.processed_ym[:4] + '/ ' + item.processed_ym[4:]
                else:
                    dt = ''
                try:
                    owner_ryaku_name =SysOwner.objects.get(owner_id=item.owner_id).owner_ryaku_name
                except SysOwner.DoesNotExist:
                    owner_ryaku_name = ''
                try:
                    partner_ryaku_name = MtPartner.objects.get(partner_id=item.partner_id).partner_ryaku_name
                except MtPartner.DoesNotExist:
                    partner_ryaku_name = ''
                category_name = item.category_name
                try:
                    user_name =EvcUser.objects.get(user_id=item.create_user).user_name
                except EvcUser.DoesNotExist:
                    user_name = ''
                try:
                    amount = item.google_amount.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
                except Exception:
                    amount = None
            if not amount:
                continue
            data = {
                'processed_ym': dt,
                'owner_id': owner_id,
                'owner_name': owner_ryaku_name or '',
                'partner_name': partner_ryaku_name or '',
                'category_name': category_name or '',
                'user_name': user_name or '',
                'google_amount': amount or '',
                'create_date': create_date
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
