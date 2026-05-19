# import os
import datetime
import calendar
# import threading
# import base64
import logging
import re   # 正規表現操作
# import csv
# from io import TextIOWrapper
# from operator import attrgetter
# from django.utils import timezone
# from django.utils.timezone import make_aware
# from dateutil.relativedelta import relativedelta

# from django.shortcuts import redirect
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from Evc_App.views import OwnerTestMixin

# from django.contrib import messages
# from django.conf import settings
# from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
# from django.http import JsonResponse
# from django.http import HttpResponseRedirect
from django.db.models import Count,Sum
from django.db.models.functions import TruncMonth
# from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN

from users.models import EvcUser,TtEvidence,SysOwner,MtPartner
from commons.utils import ut_get_client_ip,ut_get_localtoday

from Evc_Management.forms import EviSummaryForm,EviInquiryForm

# from Evc_App.sv_json import sv_load_jsonfile,sv_get_textlines
from Evc_App.sv_file import (sv_get_folder_id,sv_get_category_name,
    sv_get_category_list,sv_get_partner_name,sv_get_publisher_name,
    sv_get_partner_id,sv_get_partner_list,sv_get_publisher_id,sv_get_publisher_list,
    sv_get_owner_ryaku_name
)
from Evc_App.views_evidence import get_evidence_list_info,check_processed_date

logger = logging.getLogger(__name__)

# 当月取得 yyyy-mm
def current_month():
    today = ut_get_localtoday()
    yearmonth = today.strftime('%Y-%m')
    return yearmonth

# カテゴリ選択リストの設定
def get_category_choices(owner_id):
    choices = []
    choices.append(('0','カテゴリを選択'))
    lists = sv_get_category_list(owner_id)
    for list in lists:
        # if list != '注文請書':
        choices.append((list, list))
    return choices
# 契約会社・取引先リスト
def get_publisher_list(owner_id):
    choices = []
    lists = sv_get_publisher_list(owner_id)
    for list in lists:
        choices.append((list))
    lists = sv_get_partner_list(owner_id)
    for list in lists:
        choices.append((list))
    return choices

# 検索条件で絞り込み
def filter_evidence(queryset, trade_month, category, partner, publisher, owner_id):
    # 処理年月: yyyy/mm yyyy-mm
    if trade_month:
        try:
            dt = trade_month.replace('/', '').replace('-', '')
            if 6 < len(dt):
                dt = dt[:6]
            bom = datetime.datetime.strptime(dt + '01','%Y%m%d')
            eom = bom.replace(day=calendar.monthrange(bom.year, bom.month)[1])
            date_from = bom
            date_to = eom
            if date_from and date_to:
                queryset = queryset.filter(processed_date__range=[date_from, date_to]).order_by('processed_date')
            elif date_from:
                queryset = queryset.filter(processed_date__gte=date_from).order_by('processed_date')
            elif date_to:
                queryset = queryset.filter(processed_date__lte=date_to).order_by('processed_date')
        except Exception:
            pass
    # カテゴリ
    if category and category != '0':
        queryset = queryset.filter(category_name=category)
    # 取引先
    if partner:
        try:
            partners = MtPartner.objects.filter(owner_id=owner_id,partner_name__contains=partner)
            list = []
            for data in partners:
                list.append(data.partner_id)
            queryset = queryset.filter(partner_id__in=list)
            # partner_id = MtPartner.objects.get(partner_name=partner).partner_id
            # queryset = queryset.filter(partner_id=partner_id)
        except Exception:
            logger.exception(f'MtPartner exception {partner=}')
    # 発行元
    if publisher:
        try:
            list = []
            owners = SysOwner.objects.filter(owner_name__contains=publisher)
            for data in owners:
                list.append(data.owner_id)
            partners = MtPartner.objects.filter(owner_id=owner_id,partner_name__contains=publisher)
            for data in partners:
                list.append(data.partner_id)
            queryset = queryset.filter(publisher_id__in=list)
        except Exception:
            logger.exception(f'{publisher=}')

    return queryset

# 実績サマリー
class EvcEviSummaryView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_Management/FE_EviSummary.html'
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
        owner_id = self.request.session.get('owner_id')
        if not owner_id:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcEviSummaryView session owner_id is None')
        # オーナーIDでで絞り込み
        queryset = queryset.filter(owner_id=owner_id)

        form_month = self.request.GET.get('trade_month', current_month())
        form_category = self.request.GET.get('category', '')
        form_partner = self.request.GET.get('partner', '')
        form_publisher = self.request.GET.get('publisher', '')
        initial_data = {
            'trade_month': form_month,
            'category': form_category,
            'partner' : form_partner,
            'publisher' : form_publisher,
        }
        form = EviSummaryForm(None, initial=initial_data)
        # ChoiceFieldに選択肢の設定
        form.fields['category'].choices = get_category_choices(owner_id)
        form.fields['partner_cd'].choices = sv_get_partner_list(owner_id)
        form.fields['publisher_cd'].choices = sv_get_publisher_list(owner_id)
        self.form = form 
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcEviSummaryView 検索条件で絞り込み')
        # 検索条件で絞り込み
        queryset = filter_evidence(queryset, form_month, form_category, form_partner, form_publisher, owner_id)

        # if form.is_valid():
        #     # バリデーションを実行しデータが有効
        #     evi_id = self.request.GET.get('evi_id')
        #     # # 検索条件で絞り込み
        #     # queryset = sv_filter_evidence(owner_id, self.request, queryset)

        #     # 検索条件で絞り込み
        #     queryset = self.filter_evidence(trade_month, category, queryset)

        #     # セッションにデータを保存
        #     # Object of type date is not JSON serializable が発生するため
        #     # (dictの中に、json変換できないdate形式が存在)dateを文字型に
        #     # if date_from:
        #     #     date_from = date_from.strftime('%Y/%m/%d')
        #     # if date_to:
        #     #     date_to = date_to.strftime('%Y/%m/%d')

        #     # input_data = {
        #     #     'pdf_name': form.cleaned_data.get('pdf_name'),
        #     #     'trade_month': form.cleaned_data.get('trade_month'),
        #     #     'category': form.cleaned_data.get('category'),
        #     #     'partner': form.cleaned_data.get('partner'),
        #     #     'date_from': date_from,
        #     #     'date_to': date_to,
        #     #     'amount': form.cleaned_data.get('amount'),
        #     #     'amount_choice': form.cleaned_data.get('amount_choice'),
        #     # }
        #     # self.request.session['input_data'] = input_data

        #     # request.GETは辞書型であり、リクエスト送信時のデータが格納されている
        #     # if 'page' in self.request.GET:
        #     #     page_no = self.request.GET.get('page')
        #     #     self.request.session['page_no'] = page_no

        # else:
        #     # セッションデータクリア
        #     if 'list_url' in self.request.session:
        #         del self.request.session['list_url']
        #     list_url = self.request.get_full_path()   #build_absolute_uri()
        #     list_url = re.sub('page=[0-9]+', 'page=1', list_url)
        #     list_url = re.sub('evi_id=[0-9]+_[0-9]+', 'evi_id=', list_url)
        #     list_url = re.sub('act=del', 'act=', list_url)
        #     list_url = re.sub('act=duplicate', 'act=', list_url)
        #     self.request.session['list_url'] = list_url
        #     trade_month = current_month()
        #     category = ''
        #     queryset = self.filter_evidence(trade_month, category, queryset)
        #     initial_data = {
        #         'trade_month': trade_month,
        #         'category': category
        #     }
        #     form = EviSummaryForm(None, initial = initial_data)
        #     form.fields['category'].choices = self.get_category_choices(owner_id)
        #     self.form = form
        #     # messages.error(self.request, '検索に失敗しました')

        # セッションデータクリア
        if 'summary_url' in self.request.session:
            del self.request.session['summary_url']
        if 'hlist_url' in self.request.session:
            del self.request.session['hlist_url']
        # 実績一覧からの戻りのurlをセッションデータに登録
        list_url = self.request.get_full_path()     # build_absolute_uri()
        list_url = re.sub('page=[0-9]+', 'page=1', list_url)
        list_url = re.sub('evi_id=[0-9]+_[0-9]+', 'evi_id=', list_url)
        list_url = re.sub('act=del', 'act=', list_url)
        list_url = re.sub('act=duplicate', 'act=', list_url)
        self.request.session['summary_url'] = list_url
        if 'searchpartner' in self.request.session:
            del self.request.session['searchpartner']
        if 'searchpublisher' in self.request.session:
            del self.request.session['searchpublisher']
        self.request.session['searchpartner'] = form_partner
        self.request.session['searchpublisher'] = form_publisher

        # テーブル表示内容を取得
        lists = self.set_evidence_lists(owner_id, queryset)

        # if yearmonthday:
        #     month = yearmonthday.strftime('%Y-%m')
        # else:
        #     month = ut_get_localtoday().strftime('%Y-%m')
        # max_month = (ut_get_localtoday() + relativedelta(years=1)).strftime('%Y-%m')
        # self.extra_context = {
        #     'month': month,
        #     'max_month': max_month,
        # }

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
        context['process_title'] = '実績照会'
        context['owner_ryaku_name'] = owner_ryaku_name
        return context
    # HTMLのテーブルに設定するデータを取得
    def set_evidence_lists(self, owner_id, queryset):
        categorys = sv_get_category_list(owner_id)
        lists = []
        item_no = 1
        try:
            for category in categorys:
                # カテゴリで絞り込む
                categoryset = queryset.filter(category_name=category)
                # 月ごとに集計
                monthly_items  = categoryset.annotate(
                        month=TruncMonth('processed_date')).values('month').annotate(
                        count=Count('evidence_id')).values('month','count').order_by('-month')
                # TruncMonthで日付フィールドを指定、月単位未満の日付のすべての部分を切り捨て、グループ化
                # monthとしてannotateでフィールド追加
                # values()：monthに絞って取得する
                # Count()でレコードの数をカウント、annotateでcountとして追加
                # month,countに絞って取得する
                for m in monthly_items:
                    month = m.get('month')
                    if month:
                        # カテゴリ名をリンクURLに入れると文字化けするのでIDをパラメータに
                        folder_id = sv_get_folder_id(owner_id, category)
                        data = {
                            'item_no': str(item_no),
                            'folder_id': folder_id,
                            'category_name': category,
                            'trade_month': month.strftime('%Y-%m') if month else '',
                            'count': m.get('count'),
                        }
                        lists.append(data)
                        item_no += 1
        except Exception:
            logger.exception('EvcEviSummaryView exception')

        return lists
    # ページネーション分割数
    def get_paginate_by(self, queryset):
        paginate_by = super().get_paginate_by(queryset)
        page_size = self.request.GET.get('page_size')
        if page_size:
            paginate_by = int(page_size)
        return paginate_by
    
# 実績照会
class EvcEviInquiryView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_Management/FE_EviInquiry.html'
    model = TtEvidence
    ordering = '-evidence_id'
    paginate_by = 10 # ページネーション 分割数

    # javascriptで'戻る'ボタンの遷移をしない場合get()でredirectする
    # def get(self, request, *args, **kwargs):
    #     act = self.request.GET.get('act')   # 戻るボタンがクリック実績照会画面に戻る
    #     if act == 'cancel':
    #         if 'summary_url' in self.request.session:
    #             url = self.request.session['summary_url']
    #             return HttpResponseRedirect(url)
    #     return super().get(request, *args, **kwargs)
    def get_queryset(self):
        queryset = super().get_queryset()
        owner_id = self.request.session.get('owner_id')
        if not owner_id:
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcEviInquiryView session owner_id is None')
        # オーナーIDでで絞り込み
        queryset = queryset.filter(owner_id=owner_id)

        kwargs_month = self.kwargs.get('trade_month')   # URLパラメータ
        kwargs_folder_id = self.kwargs.get('folder_id') # URLパラメータ
        # カテゴリ名をパラメータ入れると文字化けするのでIDをパラメータに
        kwargs_category = sv_get_category_name(owner_id, kwargs_folder_id)
        searchpartner = self.request.session.get('searchpartner')
        searchpublisher = self.request.session.get('searchpublisher')
        # if 'searchpartner' in self.request.session:
        #     del self.request.session['searchpartner']
        # if 'searchpublisher' in self.request.session:
        #     del self.request.session['searchpublisher']
        form_month = self.request.GET.get('trade_month', kwargs_month)    # フォーム入力値
        form_category = self.request.GET.get('category', kwargs_category)
        form_partner = self.request.GET.get('partner', searchpartner)
        form_publisher = self.request.GET.get('publisher', searchpublisher)
        initial_data = {
            'trade_month': form_month,
            'category': form_category,
            'partner' : form_partner,
            'publisher' : form_publisher,
        }
        form = EviInquiryForm(None, initial=initial_data)

        # ChoiceFieldに選択肢の設定
        form.fields['category'].choices = get_category_choices(owner_id)
        form.fields['partner_cd'].choices = sv_get_partner_list(owner_id)
        form.fields['publisher_cd'].choices = sv_get_publisher_list(owner_id)
        self.form = form 
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcEviInquiryView 検索条件で絞り込み')
        # 検索条件で絞り込み
        queryset = filter_evidence(queryset, form_month, form_category, form_partner, form_publisher, owner_id)

        # エビデンス詳細画面からの戻りのurlをセッションデータに
        list_url = self.request.get_full_path()   #build_absolute_uri()
        list_url = re.sub('page=[0-9]+', 'page=1', list_url)
        list_url = re.sub('evi_id=[0-9]+_[0-9]+', 'evi_id=', list_url)
        list_url = re.sub('act=del', 'act=', list_url)
        list_url = re.sub('act=duplicate', 'act=', list_url)
        self.request.session['hlist_url'] = list_url
        # EvcSConShowViewに遷移(mode:'evi')のため　'hlist_url'

        # テーブル表示内容を取得
        lists = self.set_evidence_lists(queryset)

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

        context['process_title'] = '実績一覧'
        context['owner_ryaku_name'] = owner_ryaku_name
        # path_lists = [sv_helpurl(), 'EviList_help.html'] 
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        if 'summary_url' in self.request.session:
            summary_url = self.request.session['summary_url']
        else:
            summary_url = ''
        context['summary_url'] = summary_url    # '戻る'ボタンで遷移するURL
        return context
    # HTMLのテーブルに設定するデータを取得
    # EvcEviListViewに同じ
    def set_evidence_lists(self, queryset):
        lists = []
        item_no = 1
        queryset = queryset.order_by('-evidence_id')
        for item in queryset:
            data = get_evidence_list_info(item)
            date_ok = True
            try:
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
            if not date_ok:
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
