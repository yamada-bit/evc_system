import os
import datetime
# import threading
# import base64
import logging
import re   # 正規表現操作
import math

from django.http import JsonResponse
from django.http import HttpResponse,Http404
from django.shortcuts import render, redirect
from django.views.generic import FormView,ListView,View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
# from django.conf import settings
# from django.utils import timezone
# from django.utils.timezone import make_aware
from dateutil.relativedelta import relativedelta

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse,reverse_lazy
# from django.http import HttpResponseRedirect
# from django.db.models import F  
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from typing import cast
# クラス 'AnonymousUser' の属性 'user_id' にアクセスできません
# 属性 'user_id' が不明ですPylancereportAttributeAccessIssueの対処のためcast
# Pythonの型ヒント（Type Hint）用の関数で型安全性や読みやすさの向上が目的。
# 実行時の処理は何もしない。静的解析ツールやIDE向け

from Evc_App.views import OwnerTestMixin
from users.models import EvcUser,TtEvidence,MtAccount,MtPartner
from commons.utils import (ut_get_localdate,ut_get_timezone_now,
                           ut_get_client_ip,ut_get_localtoday)

from Evc_App.forms import EvcEviListForm,EvcSConCreateForm

from Evc_App.sv_file import (SearchKey,sv_file2url,sv_get_user_authority,
    sv_get_partner_id,sv_get_category_list,sv_get_partner_name,sv_get_publisher_name,
    sv_get_detect_partner_name,sv_get_detect_publisher_name,sv_delete_detect,
    sv_get_partner_list,sv_get_publisher_id,sv_get_publisher_list,sv_create_partner_auto,
    sv_get_account_list,sv_get_account_id,
    sv_get_owner_ryaku_name,sv_get_evidence_filename,
    sv_get_evidence_imagepath,sv_get_corporate_number,
    get_rootfolder,get_imgfolder_upload,
)

from Evc_App.sv_evidence import (sv_update_evidence,sv_update_shiori,
                                 sv_delete_evidence,sv_create_evidence_image,
                                 sv_update_partner,sv_update_publisher,sv_update_use_count)

from Evc_App.sv_export_csv import sv_filter_evidence,sv_response_evidence,sv_filter_today
from Evc_App.sv_pdf_merge_text import add_text_to_pdf,add_text_area_to_pdf

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']
IMAGE_EXTENTIONS = ['.jpg','.jpeg','.png']
# UPLOAD_DIR = settings.MEDIA_ROOT.parent.parent.joinpath('media/upload')

logger = logging.getLogger(__name__)

# ListView ---> 
#   modelで指定したデータベーステーブルからQuerySetを取得する
#   「object_list」という変数にQuerySetを格納する
#   HTMLテンプレートへコンテキストとしてQuerySetを渡す

# エビデンス一覧表示
class EvcEviListView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_App/FE_EviList.html'
    model = TtEvidence
    ordering = '-evidence_id'
    paginate_by = 10 # ページネーション 分割数

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
        # queryset = super().get_queryset().order_by(F('processed_date').desc(nulls_last=True))
        queryset = super().get_queryset()
        # queryset = super().get_queryset().only('evidence_id','owner_id','pdf_name','processed_ym',
        #                                        'category_name','processed_date','partner_id','publisher_id',
        #                                        'total_amount','account_id','slip_number')

        owner_id = self.request.session.get('owner_id')
        if not owner_id:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcEviListView session owner_id is None')
        # オーナーIDでで絞り込み
        queryset = queryset.filter(owner_id=owner_id)

        # request.GET 型でリクエスト　QueryDict型で初期化
        if not self.request.GET.get('today_kubuns'):
            # 検索実行無しでページ遷移するとパラメータが渡されず初期値が設定されない
            # self.request.GET --> <QueryDict: {'page': ['2']}>
            # initial_data = {
            #     'today_kubuns': 'today',
            #     'user_kubuns': 'loginuser',
            # }
            # form = EvcEviListForm(initial_data)
            form = EvcEviListForm(None)
        else:
            # request.GET : requestの情報を辞書型のデータで取得
            form = EvcEviListForm(self.request.GET or None)
        # ChoiceFieldに選択肢の設定
        form.fields['category'].choices = self.get_category_choices(owner_id)
        form.fields['account_choice'].choices = self.get_account_choices(owner_id)
        self.form = form 
        request_user = cast(EvcUser, self.request.user)
        user_id = request_user.user_id
        user_authority = sv_get_user_authority(user_id)   # ユーザ権限
        dup_ids = []
        if user_authority and user_authority != '一般':
            info, dup_ids = check_duplicate(owner_id)   # 重複エビデンスの情報

        # logger.debug(f'{ut_get_client_ip(self.request)} '
        #             f'EvcEviListView query {self.request.GET.dict()}')
        if form.is_valid():
            # バリデーションを実行しデータが有効
            evi_id = self.request.GET.get('evi_id')
            act = self.request.GET.get('act')   # 削除ボタンがクリックされたらテキスト'del'が設定されている
            if evi_id and act == 'del':
                evi_obj = TtEvidence.objects.filter(evidence_id=evi_id).first()
                if evi_obj:
                    name = sv_delete_evidence(evi_id, user_id, owner_id)
                    if name:
                        basename = os.path.splitext(name)[0]
                        # messages.success(self.request, basename + '： を削除しました')
                        logger.info(f'{ut_get_client_ip(self.request)} '
                                    f'EvcEviListView {evi_id}:{basename} を削除しました')
                        if dup_ids:
                            info, dup_ids = check_duplicate(owner_id)   # 重複エビデンスの情報を再取得
                    else:
                        messages.error(self.request, 'データ削除に失敗しました')
                        logger.error(f'{ut_get_client_ip(self.request)} '
                                     f'EvcEviListView データ削除に失敗しました {evi_id}')
            # # 検索条件で絞り込み
            # queryset = sv_filter_evidence(owner_id, self.request, queryset)
            # dup = self.request.GET.getlist('duplist')
            # if dup and dup[0] == '1':
            #     queryset = queryset.filter(evidence_id__in=dup_ids).order_by('-processed_date',
            #            'partner_id','publisher_id','total_amount','-evidence_id')
            # if act == 'duplicate':  # 重複データ検索ボタン  管理者権限以上で表示
            # ページ移動するとactがクリアされるのでduplistを使う
            dup = self.request.GET.get('duplist') 
            if dup == 'duplist':    # 重複データ検索ボタン  管理者権限以上で表示
                queryset = TtEvidence.objects.filter(owner_id=owner_id,evidence_id__in=dup_ids)\
                    .order_by('-processed_date','partner_id','publisher_id','total_amount','-evidence_id')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            'EvcEviListView 重複データ検索')
            else:
                # 検索条件で絞り込み
                queryset = sv_filter_evidence(owner_id, self.request, queryset)
                logger.info(f'{ut_get_client_ip(self.request)} '
                            'EvcEviListView 検索条件で絞り込み')
            # if act == 'search':
            #     # 検索条件のカテゴリの履歴を集計
            #     category = self.request.GET.get('category')
            #     if category and category != '0':
            #         sv_update_use_count(owner_id, category)

           # セッションにデータを保存
            # Object of type date is not JSON serializable が発生するため
            # (dictの中に、json変換できないdate形式が存在)dateを文字型に
            # if date_from:
            #     date_from = date_from.strftime('%Y/%m/%d')
            # if date_to:
            #     date_to = date_to.strftime('%Y/%m/%d')

            # input_data = {
            #     'pdf_name': form.cleaned_data.get('pdf_name'),
            #     'shori_date': form.cleaned_data.get('shori_date'),
            #     'category': form.cleaned_data.get('category'),
            #     'partner': form.cleaned_data.get('partner'),
            #     'date_from': date_from,
            #     'date_to': date_to,
            #     'amount': form.cleaned_data.get('amount'),
            #     'amount_choice': form.cleaned_data.get('amount_choice'),
            # }
            # self.request.session['input_data'] = input_data

            # 検索条件編集からの戻りのurlをセッションデータに
            list_url = self.request.get_full_path()   #build_absolute_uri()
            list_url = re.sub('page=[0-9]+', 'page=1', list_url)
            list_url = re.sub('evi_id=[0-9]+_[0-9]+', 'evi_id=', list_url)
            list_url = re.sub('act=del', 'act=', list_url)
            list_url = re.sub('act=duplicate', 'act=', list_url)
            list_url = re.sub('act=search', 'act=', list_url)
            self.request.session['list_url'] = list_url

            # if 'callfrom' in self.request.session:
            #     if self.request.session['callfrom'] == 'sconcreate':
            #         del self.request.session['callfrom']
            # else:
            #     self.request.session['input_data'] = self.request.GET
            # request.GETは辞書型であり、リクエスト送信時のデータが格納されている

            # if 'page' in self.request.GET:
            #     page_no = self.request.GET.get('page')
            #     self.request.session['page_no'] = page_no

            # kubun = self.request.GET.get('user_kubuns')
            # if kubun == 'none':
            #     info = self.check_duplicate(owner_id)
            #     if info:
            #         messages.success(self.request, 
            #                            '重複データがあります。確認してください。' + '\n' + info)
        else:
            # セッションデータクリア
            if 'list_url' in self.request.session:
                del self.request.session['list_url']
            # ログインユーザで本日のデータを初期表示する
            queryset = sv_filter_today(queryset)  # 本日
            queryset = queryset.filter(create_user=user_id)   # ログインユーザ
            logger.info(f'{ut_get_client_ip(self.request)} '
                        'EvcEviListView initial display')
            # messages.error(self.request, '検索に失敗しました')
        # info, dup_ids = check_duplicate(owner_id)
        # if info:
        #     messages.success(self.request, '重複データがあります。確認してください。' + '\n' + info)

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
        lists = self.set_evidence_lists(queryset, dup_ids, from_no, to_no)
        # 検索条件編集画面　前頁・次頁対応セッション変数
        # ログアウト時に削除
        if lists:
            evilists = []
            for item in lists:
                evilists.append(item['evi_id'])
            self.request.session['evilist'] = evilists

        return lists
            
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form

        # object_list = context['object_list']
        # if object_list:
        #     # 前頁・次頁対応セッション変数：ログアウト時に削除
        #     evilists = []
        #     for item in object_list:
        #         evilists.append(item['evi_id'])
        #     self.request.session['evilist'] = evilists
        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10

        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)

        context['process_title'] = 'エビデンス一覧表示'
        context['owner_ryaku_name'] = owner_ryaku_name
        # path_lists = [sv_helpurl(), 'EviList_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url

        # info, dup_ids = check_duplicate(owner_id)
        # if info:
        #     context['duplicate_info'] = len(dup_ids)    # info

        # object_list : ListViewのget_context_dataで設定　context{'object_list': queryset,
        object_list = context['object_list']
        context['duplicate_info'] = ''
        if object_list:
            for item in object_list:
                if item.get('result') == '重複': # get_queryset：set_evidence_listsで'重複'設定
                    context['duplicate_info'] = '重複'  # 重複データ確認ボタンを表示
                    break
        return context
    # カテゴリ選択リストの設定
    def get_category_choices(self, owner_id):
        choices = []
        choices.append(('0','カテゴリを選択'))
        lists = sv_get_category_list(owner_id)
        for list in lists:
            # if list != '注文請書':
            choices.append((list, list))
        return choices
    # 科目選択リストの設定
    def get_account_choices(self, owner_id):
        choices = []
        choices.append(('0','科目を選択'))
        lists = sv_get_account_list(owner_id)
        for list in lists:
            # if list != '注文請書':
            choices.append(list)
        return choices

    # HTMLのテーブルに表示するデータを取得
    def set_evidence_lists(self, queryset, dup_ids, from_no, to_no):
        lists = []
        item_no = 1
        for item in queryset:
            if from_no and to_no:
                if item_no < from_no or to_no < item_no:
                    data = {
                        'evi_id': item.evidence_id,
                        'item_no': str(item_no)
                    }
                    lists.append(data)
                    item_no += 1
                    continue
            # エビデンス情報を取得
            data = get_evidence_list_info(item)

            date_ok = True
            try:
                # 期限切れのチェック　作成日が取引日の２ヶ月以内
                date_ok = check_processed_date(item.evidence_id, item.processed_date)
            except Exception:
                pass
            # カテゴリ・取引先名・取引日・金額のいずれかに値が設定されていなければNG
            partner_name = data.get('partner_name')
            processed_date = data.get('processed_date')
            amount = data.get('total_amount')
            if not item.category_name or not partner_name or not processed_date:
                result = 'NG'
            else:
                if amount or amount == 0:
                    result = ''
                else:
                    result = 'NG'
            if item.evidence_id in dup_ids: # 重複エビデンス
                result = '重複'
            if not date_ok:     # 期限切れエビデンス
                result = '期限'

            data['item_no'] = str(item_no)
            data['result'] =  result
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
# エビデンス情報を取得
def get_evidence_list_info(eviobj):
    # if eviobj.google_amount == 0:
    #     continue
    # if eviobj.processed_ym:
    #     dt = eviobj.processed_ym[:4] + '/ ' + eviobj.processed_ym[4:]
    # else:
    #     dt = ''
    # try:
    #     dt = eviobj.create_date.strftime('%Y/%m')
    # except Exception:
    #     dt = ''
    try:
        # 四捨五入
        amount = eviobj.total_amount.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
    except Exception:
        amount = ''
    partner_name = ''
    publisher_name = ''
    if eviobj.partner_id:
        partner_name = sv_get_partner_name(eviobj.partner_id)
    else:   # 取引先ID未設定
        partner = sv_get_detect_partner_name(eviobj.evidence_id)
        if partner: # 検出情報に取引先名が存在
            partner_id = sv_get_partner_id(partner, eviobj.owner_id)
            if partner_id:  # 取引先マスタに取引先名が存在
                partner_name = partner
                # エビデンス 取引先更新
                sv_update_partner(eviobj.evidence_id, partner_id)
    # else:
    #     partner = sv_get_detect_partner_name(eviobj.evidence_id)
    #     if partner:
    #         partner_name = '未登録'
    if eviobj.publisher_id:
        publisher_name = sv_get_publisher_name(eviobj.publisher_id)
    else:   # 発行元ID未設定
        publisher = sv_get_detect_publisher_name(eviobj.evidence_id)
        if publisher: # 検出情報に発行元名が存在
            publisher_id = sv_get_partner_id(publisher, eviobj.owner_id)
            if publisher_id:  # 取引先マスタに発行元名が存在
                publisher_name = publisher
                # エビデンス 発行元更新
                sv_update_publisher(eviobj.evidence_id, publisher_id)

    # else:
    #     publisher = sv_get_detect_publisher_name(eviobj.evidence_id)
    #     if publisher:
    #         publisher_name = '未登録'
    try:
        processed_date = eviobj.processed_date.strftime('%Y/%m/%d')
    except Exception:
        processed_date = ''
    try:
        payment_date = eviobj.payment_date.strftime('%Y/%m/%d')
    except Exception:
        payment_date = ''

    if eviobj.account_id:
        try:
            account_name = MtAccount.objects.get(account_id=eviobj.account_id).account_name
        except MtAccount.DoesNotExist:
            account_name = ''
    else:
        account_name = ''
    createday = ut_get_localdate(eviobj.create_date)
    if createday:
        create_date = createday.strftime('%Y/%m/%d')
    else:
        create_date = ''
    userobj = EvcUser.objects.filter(user_id=eviobj.create_user).first()
    if userobj:
        user_name = (userobj.user_name or '')
    else:
        user_name = ''

    data = {
        'pdf_name': os.path.splitext(eviobj.pdf_name)[0],
        'category_name': eviobj.category_name or '',
        'total_amount': amount,
        'partner_name': partner_name,
        'publisher_name': publisher_name,
        'account_name': account_name,
        'account_desc':  eviobj.account_desc or '',
        'slip_number': eviobj.slip_number or '',
        'payment_date': payment_date,
        'processed_date': processed_date,
        'create_date': create_date,
        'user_name': user_name,
        'evi_id': eviobj.evidence_id,
    }
    return data
    
# 重複エビデンスの情報
def check_duplicate(owner_id):
    dup_list = []
    dup_ids = []
    if not owner_id:
        return '', dup_ids
    try:
        evidences = TtEvidence.objects.filter(owner_id=owner_id)\
            .values('category_name','tran_detail','evidence_id','partner_id','publisher_id',
                    'total_amount','processed_date').order_by('-evidence_id')
        evi_dict_list = list(evidences.values())
        for i,evi in enumerate(evi_dict_list):
            for j in range(0, i):
                evi2 = evi_dict_list[j]
                if (evi['partner_id'] == evi2['partner_id']
                    and evi['publisher_id'] == evi2['publisher_id']
                    and evi['total_amount'] == evi2['total_amount']
                    and evi['processed_date'] == evi2['processed_date']
                    and evi['category_name'] == evi2['category_name']
                    and evi['tran_detail'] == ''
                    and evi2['tran_detail'] == ''
                ):
                    id = evi['partner_id']
                    category = evi['category_name']
                    partner = sv_get_partner_name(evi['partner_id'])
                    publisher = sv_get_publisher_name(evi['publisher_id'])
                    amount = evi['total_amount']
                    if amount:
                        amount = math.floor(amount)
                        amount = '{:,}'.format(amount)
                    procressed = evi['processed_date']
                    # info = 'カテゴリ:'+str(category)+'\n'
                    # info += '取引先:'+str(partner)+'\n'
                    info = '取引先:'+str(partner)+'\n'
                    info += '発行元:'+str(publisher)+'\n'
                    info += '金額:'+str(amount)+'\n'
                    info += '日付:'+str(procressed)+'\n'
                    dup_list.append(info)
                    dup_ids.append(evi['evidence_id'])
                    dup_ids.append(evi2['evidence_id'])
                    break
    except Exception:
        logger.exception(f'TtEvidence exception {owner_id=}')

    return '\n'.join(dup_list), dup_ids

# 重複確認ボタンクリックで表示するメッセージを返す
def get_duplicate_info(request):
    logger.info(f'{ut_get_client_ip(request)} '
                '重複確認ボタンクリック')
    evidence_id = request.GET.get('evidence_id')
    user_id = request.user.user_id
    # owner_id = get_owner_id(user_id)
    owner_id = request.session.get('owner_id')
    info, dup_ids = check_duplicate(owner_id)
    duplicate_info = {'id': evidence_id, 'info': info}
    return JsonResponse({'duplicate_info': duplicate_info})

# 期限切れのチェック　作成日が取引日の２ヶ月以内
def check_processed_date(evi_id, processed_date):
    if not processed_date:
        return True
    fromday = ut_get_localtoday() - relativedelta(months=2)
    try:
        eviobj =  TtEvidence.objects.get(evidence_id=evi_id)
        createday = ut_get_localdate(eviobj.create_date)
        if createday:
            fromday = createday.date() - relativedelta(months=2)
    except TtEvidence.DoesNotExist:
        pass

    try:
        # Djangoでは、PostgreSQLだとdatetimeFieldはDB上ではtimestamp with time zoneとなり、タイムゾーンはUTC
        # todayをUTCに変換
        # fromday_start_str = str(fromday) + ' 00:00:00'
        # fromday_start = datetime.datetime.strptime(fromday_start_str, '%Y-%m-%d %H:%M:%S')
        # fromday_start = fromday_start.astimezone(datetime.timezone.utc)
        # str_time = fromday_start.strftime('%Y/%m/%d')
        if processed_date < fromday:
            return False
    except Exception:
        logger.exception('check_processed_date exception')
    return True

# CSVダウンロードリクエスト
def export_evidence_csv(request):
    logger.info(f'{ut_get_client_ip(request)} '
                'CSVダウンロード')
    # print(request.GET)
    evidence_list = TtEvidence.objects.all().order_by('-evidence_id')
    # リクエストに応じて絞り込み
    owner_id = request.session.get('owner_id')
    if not owner_id:
        logger.error(f'{ut_get_client_ip(request)} '
                    'export_evidence_csv session owner_id is None')
    # オーナーIDで絞り込み
    queryset = evidence_list.filter(owner_id=owner_id)
    # 検索条件で絞り込み
    queryset = sv_filter_evidence(owner_id, request, queryset)
    # CSVを作成する
    response = sv_response_evidence(queryset)
    return response

# 検索条件編集
class EvcSConCreateView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_App/FE_SConCreate.html'
    form_class = EvcSConCreateForm

    def get_success_url(self):
        return reverse('Evc_App:sconcreate', kwargs={'evi_id': self.kwargs['evi_id']})
   
    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        # owner_id = get_owner_id(self.request.user.user_id)
        owner_id = self.request.session.get('owner_id')
        # ChoideFieldの選択肢をパラメタで渡す SConCreateForm __init__()
        kwgs['categories'] = self.get_category_choices(owner_id)
        kwgs['partners'] = sv_get_partner_list(owner_id)
        kwgs['publishers'] = sv_get_publisher_list(owner_id)
        kwgs['accounts'] = sv_get_account_list(owner_id)
        return kwgs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evi_id = self.kwargs.get('evi_id')
        context['form_name'] = 'sconcreate'
        context['process_title'] = '検索条件編集'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        # path_lists = [sv_helpurl(), 'SConCreate_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        try:
            eviobj =  TtEvidence.objects.get(evidence_id=evi_id)
        except TtEvidence.DoesNotExist:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                             f'EvcSConCreateView TtEvidence DoesNotExist {evi_id}')
            return context
        try:
            # 表示するファイルのurl
            filepath = sv_get_evidence_filename(eviobj)
            # filepath = b_pdf.decode('utf-8')
            url = sv_file2url(filepath)
            imagpath = sv_get_evidence_imagepath(eviobj)  
            if not os.path.exists(imagpath):    # 画像がなければ作成
                sv_create_evidence_image(evi_id)
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
            context['pdf_name'] = eviobj.pdf_name

        except Exception:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                             f'EvcSConCreateView get pdf url exception {eviobj.pdf_name}')
        # context['fulltext'] = eviobj.pdf_handbook#fulltext

        # with open('D:\MyPython2022\EVC\media\img\\test_01_150.png', 'rb') as f:
        #     b_pdf =  f.read()
        # pdfbase64 = base64.b64encode(b_pdf).decode()
        # context['pdffile'] = 'data:image/png;base64,' + pdfbase64

        # iframe インラインでは1MBくらいまでしか表示されない
        # pdfbase64 = base64.b64encode(eviobj.evidence_data).decode()
        # context['pdffile'] = 'data:application/pdf;base64,' + pdfbase64

        # 前頁・次頁対応ページング
        if 'evilist' in self.request.session:
            evilists = self.request.session['evilist']
            page_obj = self.get_page_obj(evilists, evi_id)
            context['page_obj'] = page_obj
            if page_obj.has_next():
                context['next_evi_id'] = evilists[page_obj.next_page_number() - 1]
            if page_obj.has_previous():
                context['previous_evi_id'] = evilists[page_obj.previous_page_number() - 1]

        if 'form' not in kwargs:
            default_data = get_scon_info(eviobj)
            form = EvcSConCreateForm(initial = default_data)
            context['form'] = form
        # if eviobj:
        #     if not eviobj.google_amount or eviobj.google_amount == 0:
        #         messages.error(self.request, 'パスワードが設定または、処理できないファイルです。')
        return context

    def form_valid(self, form):
        #  name='submit_action' を3つのformに定義(idは別)
        act = self.request.POST.get('submit_action')
 
        # if 'callfrom' in self.request.session:
        #     del self.request.session['callfrom']
        owner_id = self.request.session.get('owner_id')
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'EvcSConCreateView {act=}')
        request_user = cast(EvcUser, self.request.user)
        user_id = request_user.user_id

        if act == 'commit': # 登録
            category_name = ''
            category = form.cleaned_data.get('category')
            if category and category != '0':
                category_name = category
            evi_id = form.cleaned_data.get('evidence_id')
            partner = form.cleaned_data.get('partner')
            partner_id = sv_get_partner_id(partner, owner_id)
            if not partner_id and partner:
                # 取引先データ作成
                partner_id = sv_create_partner_auto(partner, user_id, owner_id)
            publisher = form.cleaned_data.get('publisher')
            publisher_id = get_publisher_id(evi_id, publisher, user_id)
            if not publisher_id and publisher:
                publisher_id = sv_get_partner_id(publisher, owner_id)
                if not publisher_id:
                    # 取引先データ作成
                    publisher_id = sv_create_partner_auto(publisher, user_id, owner_id)
            # publisher = form.cleaned_data.get('publisher_cd')
            # if publisher and publisher != '0':
            #     publisher_id = sv_get_publisher_id(publisher, user_id)
            #     if not publisher_id:
            #         publisher_id = sv_get_partner_id(publisher, owner_id)
            sv_delete_detect(evi_id)    # 検出情報データ削除
            process_date = form.cleaned_data.get('process_date')
            amount = form.cleaned_data.get('amount')
            if amount:
                try:
                    if type(amount) is str:
                        amount = amount.replace(',','')
                        total_amount = int(amount)
                    else:
                        total_amount = amount
                except Exception:
                    total_amount = None
            else:
                total_amount = None
            account = form.cleaned_data.get('account')
            account_id = sv_get_account_id(account, user_id, owner_id, True)
            account_desc = form.cleaned_data.get('account_desc')
            search = SearchKey(category_name, process_date, partner_id, publisher_id, total_amount)
            duplicate_ok = form.cleaned_data.get('duplicate_check')
            slip_number = form.cleaned_data.get('slip_number')
            payment_date = form.cleaned_data.get('payment_date')
            # エビデンス情報テーブル更新
            id = sv_update_evidence(evi_id, search, account_id, account_desc, duplicate_ok, slip_number, payment_date, user_id)

            # params = {
            #     'evidence_id': evi_id,
            #     'search': search,
            #     'account_id': account_id,
            #     'account_desc': account_desc,
            #     'user_id': user_id,
            # }
            # # 辞書dictに**を付けて引数にすると、要素のキーを引数名、値を引数の値として展開して、
            # # 個別の引数として渡される
            # # エビデンス情報テーブル更新
            # id = sv_update_evidence(**params)
            
            if id:
                # 期限切れのチェック　作成日が取引日の２ヶ月以内
                date_ok = check_processed_date(evi_id, process_date)
                if date_ok:
                    messages.success(self.request, '検索条件データを登録しました')
                else:
                    messages.success(self.request, '２ケ月以前の取引日は期限切れです。')
                    # messages.success(self.request, '２ケ月以前の取引日は期限切れです。データを削除してください。')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcSConCreateView 検索条件データを登録しました {evi_id}')
            else:
                messages.error(self.request, 'データ登録に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'EvcSConCreateView データ登録に失敗しました {evi_id}')

        elif act == 'update':   # テキストデータ更新
            evi_id = form.cleaned_data.get('evidence_id')
            fulltext = form.cleaned_data.get('fulltext')
            # エビデンス テキストデータ更新
            id = sv_update_shiori(evi_id, fulltext, user_id, owner_id)
            if id:
                messages.success(self.request, 'テキストデータを更新しました')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcSConCreateView テキストデータを更新しました {evi_id}')
            else:
                messages.error(self.request, 'データ更新に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'EvcSConCreateView データ更新に失敗しました {evi_id}')
        elif act == 'cancel':   # 戻る
            # セッションデータをここで削除してもページ遷移後のlist表示で作成されるのでログアウト時に削除
            # if 'evilist' in self.request.session:
            #     del self.request.session['evilist']

            # 検索条件が異なる更新をした場合に戻るとおかしくなる
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            # self.request.session['callfrom'] = 'sconcreate'
            return redirect('Evc_App:evidence_list')
        elif act == 'delete':   # 削除
            evi_id = form.cleaned_data.get('evidence_id')
            #  エビデンス情報削除/ファイル削除 
            name = sv_delete_evidence(evi_id, user_id, owner_id)
            if name:
                basename = os.path.splitext(name)[0]
                messages.success(self.request, f'{basename} を削除しました')
                # self.request.session['callfrom'] = 'sconcreate'
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcSConCreateView {evi_id}:{basename} を削除しました')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                             f'EvcSConCreateView データ削除に失敗しました {evi_id}')
            # セッション変数でリダイレクトURLを取得
            if 'list_url' in self.request.session:
                url = self.request.session['list_url']
                return redirect(url)
            return redirect('Evc_App:evidence_list')

        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcSConCreateView データ登録に失敗しました {err}')
        return super().form_invalid(form)
    # 前頁・次頁対応ページング
    def get_page_obj(self, evilists, evi_id):
        page_no = 1
        for idx, evi in enumerate(evilists):
            if evi == evi_id:
                page_no = idx + 1
                break
        paginator = Paginator(evilists, 1)
        try:
            page_obj = paginator.page(page_no)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)   
        return page_obj 
    # カテゴリ選択リストの設定
    def get_category_choices(self, owner_id):
        choices = []
        choices.append(('0', ''))
        lists = sv_get_category_list(owner_id)
        for list in lists:
            # if list != '注文請書':
            choices.append((list, list))
        return choices
# フォーム表示のためにエビデンス情報を取得
# eviobj : TtEvidenceまたはHtEvidence
# TtEvidence(エビデンス情報テーブル)とHtEvidence(エビデンス履歴情報テーブル)で項目名が同一
def get_scon_info(eviobj):
    try:
        amount = eviobj.total_amount.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
        amount = '{:,}'.format(amount)
    except Exception:
        amount = ''
    processed_date = eviobj.processed_date
    detect_partner = ''
    if eviobj.partner_id:
        partner = sv_get_partner_name(eviobj.partner_id)
    else:   # 取引先ID未設定
        partner = sv_get_detect_partner_name(eviobj.evidence_id)
        if partner: # 検出情報に取引先名が存在
            partner_id = sv_get_partner_id(partner, eviobj.owner_id)
            if not partner_id:  # 取引先マスタに取引先名が存在しない
                detect_partner = partner    # 未登録メッセージ表示
    detect_publisher = ''
    corporate_number = ''
    if eviobj.publisher_id:
        publisher = sv_get_publisher_name(eviobj.publisher_id)
        corporate_number = sv_get_corporate_number(eviobj.publisher_id)
        if corporate_number:
            corporate_number = f'登録番号:T{corporate_number}'
    else:   # 発行元ID未設定
        publisher = sv_get_detect_publisher_name(eviobj.evidence_id)
        if publisher: # 検出情報に発行元名が存在
            publisher_id = sv_get_partner_id(publisher, eviobj.owner_id)
            if not publisher_id:# 取引先マスタに発行元名が存在しない
                detect_publisher = publisher    # 未登録メッセージ表示
    category = ''
    if eviobj.category_name:
        owner_id = eviobj.owner_id
        # owner_id = get_owner_id(user_id)
        list = sv_get_category_list(owner_id)
        for name in list:
            if name == eviobj.category_name:
                category = name
                break
    account = ''
    if eviobj.account_id:
        try:
            account = MtAccount.objects.get(account_id=eviobj.account_id).account_name
        except MtAccount.DoesNotExist:
            pass
    account_desc = eviobj.account_desc or ''
    # duplicate_check = eviobj.tran_detail.get('重複')
    duplicate_check = True if eviobj.tran_detail != '' else False
    default_data = {
        'evidence_id': eviobj.evidence_id,
        'fulltext': eviobj.pdf_handbook,
        'category': category,
        'partner' : partner,
        'publisher' : publisher,
        'corporate_number': corporate_number,
        'detect_partner' : detect_partner,
        'detect_publisher' : detect_publisher,
        'process_date': processed_date,
        'amount': amount,
        'account' : account,
        'account_desc' : account_desc,
        'duplicate_check' : duplicate_check,
        'slip_number' : eviobj.slip_number or '',
        'payment_date' : eviobj.payment_date or '',
    }
    return default_data

def get_publisher_id(evi_id, publisher, user_id):
    try:
        eviobj = TtEvidence.objects.get(evidence_id=evi_id)
    except TtEvidence.DoesNotExist:
        logger.exception(f'TtEvidence DoesNotExist {evi_id}')
        return ''
    if eviobj and eviobj.publisher_id:
        try:
            partner_obj = MtPartner.objects.get(partner_id=eviobj.publisher_id)
            if partner_obj.corporate_number and partner_obj.partner_name == 'API未登録':
                if publisher != 'API未登録':
                    partner_obj.partner_name = publisher
                    if partner_obj.create_date:
                        partner_obj.create_date = ut_get_localdate(partner_obj.create_date)
                    partner_obj.update_user = user_id
                    partner_obj.update_date = ut_get_timezone_now()
                    partner_obj.save()
                return eviobj.publisher_id
        except MtPartner.DoesNotExist:
            logger.exception(f'MtPartner DoesNotExist {eviobj.publisher_id}')
        except Exception:
            logger.exception(f'MtPartner exception {eviobj.publisher_id}')

    publisher_id = sv_get_publisher_id(publisher, user_id)
    return publisher_id

class PdfMergeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        owner_id = self.request.session.get('owner_id')
        evi_id = self.kwargs.get('evi_id')
        try:
            eviobj = TtEvidence.objects.get(evidence_id=evi_id)
        except TtEvidence.DoesNotExist:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                             f'PdfMergeView TtEvidence DoesNotExist {evi_id}')
            raise Http404("Data does not exist")
        evi_start = evi_id[:15]
        evi_objs = TtEvidence.objects.filter(evidence_id__startswith=evi_start).order_by('evidence_id')
        fulltexts = []
        for obj in evi_objs:
            fulltext = obj.pdf_handbook
            fulltexts.append(fulltext)
        filename = eviobj.pdf_name
        if filename:
            idx = filename.rfind('.pdf')
            filename = filename[:idx] + '_text.pdf'
        else:
            filename = 'pdf_text.pdf'
        filepath = sv_get_evidence_filename(eviobj)
        # PDF出力
        response = HttpResponse(status=200, content_type='application/pdf')
        # response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)  # ダウンロードする場合
        response['Content-Disposition'] = 'filename="{}"'.format(filename)  # 画面に表示する場合
        
        # PDFに透明テキストを追加
        response = add_text_to_pdf(response, filepath, fulltexts)

        # テキストの位置を合わせるにはこちら-->
        # rootfolder = get_rootfolder(owner_id)
        # img_upload_dir = get_imgfolder_upload(rootfolder)
        # if not img_upload_dir:
        #     logger.error(f'upload imgfolder error {rootfolder=}')
        #     raise Http404("Data does not exist")
        # # pypdfを使って元のPDFページを読み込み、reportlabで透明テキストを座標を合わせて加え、新しいPDFを作成
        # response = add_text_area_to_pdf(response, filepath, img_upload_dir)
        # if not response:
        #     raise Http404("text data error")
        # <-- テキストの位置を合わせるにはこちら

        return response
