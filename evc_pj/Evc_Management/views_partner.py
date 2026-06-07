# import os
# import datetime
# import calendar
# import threading
# import base64
import csv
import logging
from io import TextIOWrapper

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse

# from operator import attrgetter
# from django.utils import timezone
# from django.utils.timezone import make_aware
from django.shortcuts import redirect

# from django.conf import settings
# from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from django.views.generic import FormView, ListView

from commons.utils import ut_get_client_ip
from Evc_App.sv_export_csv import sv_response_partner

# from Evc_App.sv_json import sv_load_jsonfile,sv_get_textlines
from Evc_App.sv_file import sv_delete_partner, sv_get_owner_ryaku_name, sv_save_partner
from Evc_App.views import OwnerTestMixin
from Evc_Management.forms import EvcPartnerForm, EvcPartnerSaveForm, PartnerListForm

# from django.db.models import Sum
# from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from users.models import MtPartner

logger = logging.getLogger(__name__)

# 取引先一覧
class EvcPartnerListView(LoginRequiredMixin, OwnerTestMixin, ListView):
    template_name = 'Evc_Management/FE_PartnerList.html'
    model = MtPartner
    ordering = 'partner_id'
    paginate_by = 10 # ページネーション 分割数

    def get_queryset(self):
        queryset = super().get_queryset()
        owner_id = self.request.session.get('owner_id')
        # owner_id = get_owner_id(self.request.user.user_id)
        queryset = queryset.filter(owner_id=owner_id)
        form = PartnerListForm(self.request.GET or None)
        self.form = form
        logger.info(f'{ut_get_client_ip(self.request)} '
                    'EvcPartnerListView 検索条件で絞り込み')

        if form.is_valid():
            # 検索条件で絞り込み
            # 取引先を入力
            partner = form.cleaned_data.get('partner')
            if partner:
                try:
                    partners = MtPartner.objects.filter(owner_id=owner_id, partner_name__contains=partner)
                    list = []
                    for data in partners:
                        list.append(data.partner_id)
                    queryset = queryset.filter(partner_id__in=list)
                    # partner_id = MtPartner.objects.get(partner_name=partner).partner_id
                    # queryset = queryset.filter(partner_id=partner_id)
                except Exception:
                    logger.exception(f'{ut_get_client_ip(self.request)} '
                                    f'EvcPartnerListView MtPartner exception {partner=}')
        # 一覧表示内容を取得
        lists = self.set_partner_lists(queryset)
        return lists

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # search formを渡す
        context['form'] = self.form
        context['process_title'] = '取引先一覧'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        # context['page_size'] = self.paginate_by
        page_size = self.request.GET.get('page_size')
        if page_size:
            context['page_size'] = int(page_size)
        else:
            context['page_size'] = 10
        # path_lists = [sv_helpurl(), 'PartnerList_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        return context

    # HTMLのテーブルに設定するデータを取得
    def set_partner_lists(self, queryset):
        lists = []
        for item in queryset:
            if item.partner_type == 1:
                type = '顧客'
            elif item.partner_type == 2:
                type = '仕入先'
            else:
                type = ''
            if item.delete_flg == 1:
                delete_flg = 'true'
            else:
               delete_flg = ''
            data = {
                'partner_id': item.partner_id or '',
                'partner_name': item.partner_name or '',
                'partner_ryaku_name': item.partner_ryaku_name or '',
                'corporate_number': item.corporate_number.strip() if item.corporate_number else '',
                'partner_type': type,
                'charge_dept': item.charge_dept or '',
                'charge_name': item.charge_name or '',
                'charge_email': item.charge_email or '',
                'zip_code': item.zip_code or '',
                'address1': item.address1 or '',
                'address2': item.address2 or '',
                'tel_no': item.tel_no or '',
                'fax_no': item.fax_no or '',
                'delete_flg': delete_flg,
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
# 取引先登録で検索ボタンクリックで取引先一覧ダイアログを表示するリスト
def get_partner_list(request):
    name = request.GET.get('partner_name')
    logger.info(f'{ut_get_client_ip(request)} '
                f'取引先検索ボタンクリック {name=}')
    user_id = request.user.user_id
    # owner_id = get_owner_id(user_id)
    owner_id = request.session.get('owner_id')
    partners = MtPartner.objects.filter(owner_id=owner_id, partner_name__contains=name).exclude(delete_flg=1)
    partner_list = [{'id': partner.partner_id, 'name': partner.partner_name} for partner in partners]
    return JsonResponse({'partner_list': partner_list})

# 取引先CSVダウンロードリクエスト
def export_partner_csv(request):
    logger.info(f'{ut_get_client_ip(request)} '
                'CSVダウンロード')
    # print(request.GET)
    partner_list = MtPartner.objects.all().order_by('-partner_id')
    # リクエストに応じて絞り込み
    owner_id = request.session.get('owner_id')
    if not owner_id:
        logger.error(f'{ut_get_client_ip(request)} '
                    'export_partner_csv session owner_id is None')
    # オーナーIDで絞り込み
    queryset = partner_list.filter(owner_id=owner_id)
    # 検索条件で絞り込み
    partner = request.GET.get('partner')
    if partner:
        try:
            partners = MtPartner.objects.filter(owner_id=owner_id, partner_name__contains=partner)
            list = []
            for data in partners:
                list.append(data.partner_id)
            queryset = queryset.filter(partner_id__in=list)
            # partner_id = MtPartner.objects.get(partner_name=partner).partner_id
            # queryset = queryset.filter(partner_id=partner_id)
        except Exception:
            logger.exception(f'{ut_get_client_ip(request)} '
                            f'MtPartner exception {partner=}')

    # CSVを作成する
    response = sv_response_partner(queryset)
    return response

# 同一取引先名のチェック
def check_partner_name(owner_id, partner_id, partner_name):
    partnerobjs = MtPartner.objects.filter(owner_id=owner_id,partner_name=partner_name).exclude(delete_flg=1)
    for data in partnerobjs:
        if partner_id != data.partner_id:
            logger.debug(f'MtPartner 同一取引先名レコードあり {data.partner_id} : {partner_name}')
            return False
    return True

# 取引先登録
class EvcPartnerView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_Management/FE_Partner.html'
    form_class = EvcPartnerForm

    def get_success_url(self):
        return reverse('Evc_Management:partner_list')
        # return reverse('Evc_Management:partner', kwargs={'partner_id': self.kwargs['partner_id']})

    def get_form_kwargs(self, *args, **kwargs):
        kwgs = super().get_form_kwargs(*args, **kwargs)
        return kwgs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        partner_id = self.kwargs.get('partner_id')
        context['form_name'] = 'partner'
        context['process_title'] = '取引先登録'
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        context['owner_ryaku_name'] = owner_ryaku_name
        context['kubun'] = 'new'
        # path_lists = [sv_helpurl(), 'Partner_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        # context['help_url'] = help_url
        if partner_id == '0':
            return context
        try:
            partnerobj =  MtPartner.objects.get(partner_id=partner_id)
            context['kubun'] = 'change'
        except MtPartner.DoesNotExist:
            return context

        if 'form' not in kwargs:
            default_data = self.get_partner_info(partnerobj)
            form = EvcPartnerForm(initial = default_data)
            context['form'] = form
        return context

    def form_valid(self, form):
        user_id = self.request.user.user_id
        # owner_id = get_owner_id(user_id)
        owner_id = self.request.session.get('owner_id')

        # kubun = self.request.POST['kubun']
        kubun = form.cleaned_data.get('kubuns')
        if kubun == 'new':
            partner_id = '0'
        else:
            partner_id = self.kwargs.get('partner_id')
            if not partner_id or partner_id == '0':
                messages.error(self.request, '取引先が選択されていません。')
                return super().form_invalid(form)
        partner_name = form.cleaned_data.get('partner_name')
        check = check_partner_name(owner_id, partner_id, partner_name)
        if not check:
            messages.error(self.request, '同じ取引先名が存在します。区別出来るようにして下さい。')
            return super().form_invalid(form)
        if kubun == 'new' or kubun == 'change': # 登録
            type = form.cleaned_data.get('partner_types')
            if type == 'customer':
                partner_type = 1
            elif type == 'supplier':
                partner_type = 2
            else:
                partner_type = 0
            partner_ryaku_name = form.cleaned_data.get('partner_ryaku_name')
            corporate_number = form.cleaned_data.get('corporate_number')
            charge_dept = form.cleaned_data.get('charge_dept')
            charge_name = form.cleaned_data.get('charge_name')
            charge_email = form.cleaned_data.get('charge_email')
            zip3 = form.cleaned_data.get('zip3')
            zip4 = form.cleaned_data.get('zip4')
            if zip3 and zip4:
                zip_code = zip3 + '-' + zip4
            else:
                zip_code = ''
            address1 = form.cleaned_data.get('address1')
            address2 = form.cleaned_data.get('address2')
            tel_no = form.cleaned_data.get('tel_no')
            fax_no = form.cleaned_data.get('fax_no')
            charge_email = form.cleaned_data.get('charge_email')
            notes = form.cleaned_data.get('notes')

            data = {
                'partner_id': partner_id,
                'partner_name': partner_name,
                'partner_type': partner_type,
                'partner_ryaku_name': partner_ryaku_name,
                'owner_id': owner_id,
                'corporate_number': corporate_number.strip() if corporate_number else '',
                'charge_dept': charge_dept,
                'charge_name': charge_name,
                'charge_email': charge_email,
                'zip_code': zip_code,
                'address1': address1,
                'address2': address2,
                'tel_no': tel_no,
                'fax_no': fax_no,
                'delete_flg': 0,
                'notes': notes,
            }
            if kubun == 'new':
                partner_id = sv_save_partner(data, user_id, 'new')
                if partner_id:
                    messages.success(self.request, '取引先データを登録しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcPartnerView 取引先データを登録しました。 {partner_id=}')
                    return redirect('Evc_Management:partner', partner_id)
                else:
                    messages.error(self.request, 'データ登録に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                'EvcPartnerView データ登録に失敗しました')
            else:
                partner_id = sv_save_partner(data, user_id, 'change')
                if partner_id:
                    messages.success(self.request, '取引先データを更新しました')
                    logger.info(f'{ut_get_client_ip(self.request)} '
                                f'EvcPartnerView 取引先データを更新しました {partner_id=}')
                else:
                    messages.error(self.request, 'データ更新に失敗しました')
                    logger.error(f'{ut_get_client_ip(self.request)} '
                                'EvcPartnerView データ更新に失敗しました')
        elif kubun == 'delete':   # 削除
            partner_id = self.kwargs.get('partner_id')
            if sv_delete_partner(partner_id, user_id):
                messages.success(self.request, '取引先データを削除しました')
                # return redirect('Evc_Management:partner', '0')
                logger.info(f'{ut_get_client_ip(self.request)} '
                            f'EvcPartnerView 取引先データを削除しました {partner_id=}')
                return redirect('Evc_Management:partner_list')
            else:
                messages.error(self.request, 'データ削除に失敗しました')
                logger.error(f'{ut_get_client_ip(self.request)} '
                            'EvcPartnerView データ削除に失敗しました')

        # return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'データ登録に失敗しました')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcPartnerView データ登録に失敗しました {err}')
        return super().form_invalid(form)
    # フォーム表示のために取引先情報を取得
    def get_partner_info(self, partnerobj):
        kubun = 'change'
        partner_type = partnerobj.partner_type
        type = 'customer' if partner_type == 1 else ('supplier' if partner_type == 2 else 'none')
        if partnerobj.zip_code and 6 < len(partnerobj.zip_code):
            zip3 = partnerobj.zip_code[0:3]
            zip4 = partnerobj.zip_code[-4:]
        else:
            zip3 = None
            zip4 = None
        default_data = {
            # 'partner_id_hidden': partnerobj.partner_id,
            'kubuns': kubun,
            'partner_name': partnerobj.partner_name,
            'partner_types' : type,
            'partner_ryaku_name': partnerobj.partner_ryaku_name,
            'corporate_number': partnerobj.corporate_number.strip() if partnerobj.corporate_number else '',
            'charge_dept': partnerobj.charge_dept,
            'charge_name': partnerobj.charge_name,
            'charge_email': partnerobj.charge_email,
            'zip3': zip3,
            'zip4': zip4,
            'address1' : partnerobj.address1,
            'address2': partnerobj.address2,
            'tel_no': partnerobj.tel_no,
            'fax_no': partnerobj.fax_no,
            'notes': partnerobj.notes,
        }
        return default_data

# 取引先登録（一括）
class EvcPartnerSaveView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_Management/FE_PartnerSave.html'
    form_class = EvcPartnerSaveForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_form()
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        # path_lists = [sv_helpurl(), 'PartnerSave_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        context = {
            'form': form,
            'process_title': '取引先登録（一括）',
            'owner_ryaku_name': owner_ryaku_name
            # 'help_url': help_url
        }
        return context

    def form_valid(self, form):
        try:
            file = self.request.FILES['partnercsv']
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcPartnerSaveView import csv {file.name}')
            rtn = self.save_partner_csv(file)
        except Exception:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            'EvcPartnerSaveView save_partner_csv exception ')
            rtn = False

        if rtn:
            messages.success(self.request, f'{rtn} 件 取引先登録に成功しました。')
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcPartnerSaveView {rtn} 件 取引先登録に成功しました。')
            return self.render_to_response(self.get_context_data(form=form))
        else:
            messages.error(self.request, '取引先登録に失敗しました。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcPartnerSaveView 取引先登録に失敗しました。')
            return self.render_to_response(self.get_context_data(form=form))
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました。')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcPartnerSaveView アップロードに失敗しました。 {err}')
        return super().form_invalid(form)
    # CSVデータ（SJIS)を取引先テーブルに登録
    def save_partner_csv(self, file):
        user_id = self.request.user.user_id
        # owner_id = get_owner_id(user_id)
        owner_id = self.request.session.get('owner_id')

        csv_data = TextIOWrapper(file, encoding='CP932')
        reader = csv.reader(csv_data)
        # ラベルデータをスキップする
        header = next(reader)
        cnt = 0
        for line in reader:
            if len(line) < 14:
                continue
            partner_id = line[0]
            if 10 < len(partner_id):
                continue
            partner_name = line[1]
            if 50 < len(partner_name):
                continue
            try:
                partner_obj = MtPartner.objects.get(partner_id=partner_id,owner_id=owner_id)
                kubun = 'change'
            except MtPartner.DoesNotExist:
                partner_id = '0'
                kubun = 'new'
            check = check_partner_name(owner_id, partner_id, partner_name)
            if not check:
                logger.error(f'EvcPartnerSaveView same partner exists {partner_id=}')
                continue

            type = line[4]
            if type == '顧客':
                partner_type = 1
            elif type == '仕入先':
                partner_type = 2
            else:
                partner_type = 0
            delete_flg = line[13]
            if delete_flg == 'true':
                delete_flg = 1
            else:
                delete_flg = 0

            data = {
                'partner_id': partner_id,
                'partner_name': partner_name,
                'partner_type': partner_type,
                'partner_ryaku_name': line[2] if len(line[2]) < 21 else '',
                'owner_id': owner_id,
                'corporate_number': line[3] if len(line[3]) < 14 else '',
                'charge_dept': line[5] if len(line[5]) < 31 else '',
                'charge_name': line[6] if len(line[6]) < 31 else '',
                'charge_email': line[7] if len(line[7]) < 51 else '',
                'zip_code': line[8] if len(line[8]) < 11 else '',
                'address1': line[9] if len(line[9]) < 101 else '',
                'address2': line[10] if len(line[10]) < 101 else '',
                'tel_no': line[11] if len(line[11]) < 21 else '',
                'fax_no': line[12] if len(line[12]) < 21 else '',
                'delete_flg': delete_flg,
                'notes': '',
            }
            rtn = sv_save_partner(data, user_id, kubun)
            if not rtn:
                return cnt
            else:
                cnt += 1
        return cnt
# 取引先CSVファイルダウンロード
def download_partner_csv(request):
    logger.info(f'{ut_get_client_ip(request)} '
                'CSVダウンロード')
    partner_list = MtPartner.objects.all().order_by('-partner_id')
    # リクエストに応じて絞り込み
    owner_id = request.session.get('owner_id')
    if not owner_id:
        logger.error(f'{ut_get_client_ip(request)} '
                    'export_partner_csv session owner_id is None')
    # オーナーIDで絞り込み
    queryset = partner_list.filter(owner_id=owner_id)

    # CSVを作成する
    response = sv_response_partner(queryset)

    # response = sv_response_partner_sample()
    return response
