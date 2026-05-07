import datetime
import logging
import csv,urllib,os
# import io   # BOM付きのUTF-8のCSVファイル
from django.http import HttpResponse
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
# from django.http import FileResponse

from users.models import SysOwner,MtPartner,MtAccount
from Evc_App.sv_file import sv_get_partner_name,sv_get_publisher_name

logger = logging.getLogger(__name__)

# 検索条件で絞り込み
def sv_filter_evidence(owner_id, request, queryset):
    kubun = request.GET.get('today_kubuns')
    if kubun == 'none':
        today_check = False
    else:
        today_check = True
    kubun = request.GET.get('user_kubuns')
    if kubun == 'none':
        user_check = False
    else:
        user_check = True
    if today_check:
        queryset = sv_filter_today(queryset)
    if user_check:
        queryset = queryset.filter(create_user=request.user.user_id)

    pdf_name = request.GET.get('pdf_name')
    if pdf_name:
        queryset = queryset.filter(pdf_name__contains=pdf_name)
    # 処理年月: yyyy/mm
    shori_date = request.GET.get('shori_date')
    if shori_date:
        dt = shori_date.replace('/', '').replace('-', '')
        if 6 < len(dt):
            dt = dt[:6]
        queryset = queryset.filter(processed_ym=dt)
        # bom = ut_get_beginofmonth(shori_date)
        # eom = ut_get_endofmonth(bom)
        # if bom and eom:
        #     queryset = queryset.filter(create_date__range=[bom, eom])
    # 処理年月日: yyyy/mm/dd
    create_date = request.GET.get('create_date')
    if create_date:
        try:
            dt = create_date.replace('/', '').replace('-', '')
            bom = datetime.datetime.strptime(dt,'%Y%m%d').date()
            queryset = filter_create_date(queryset, bom)
        except Exception:
            logger.exception(f'{create_date=}')

    # カテゴリを選択
    category = request.GET.get('category')
    if category and category != '0':
        queryset = queryset.filter(category_name=category)
    # 伝票番号を入力
    slip_number = request.GET.get('slip_number')
    if slip_number and 0 < len(slip_number):
        queryset = queryset.filter(slip_number=slip_number)
    # 取引先を入力
    partner = request.GET.get('partner')
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
            logger.exception(f'{partner=}')
    # 発行元を入力
    publisher = request.GET.get('publisher')
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
            # partner_id = MtPartner.objects.get(partner_name=partner).partner_id
            # queryset = queryset.filter(partner_id=partner_id)
        except Exception:
            logger.exception(f'{publisher=}')
    # 取引日: yyyy/mm/dd
    date_from = request.GET.get('process_date1')
    date_to = request.GET.get('process_date2')
    if date_from and date_to:
        queryset = queryset.filter(processed_date__range=[date_from, date_to]).order_by('processed_date')
    elif date_from:
        queryset = queryset.filter(processed_date__gte=date_from).order_by('processed_date')
    elif date_to:
        queryset = queryset.filter(processed_date__lte=date_to).order_by('processed_date')
    # else:
    #     queryset = queryset.filter(processed_date__isnull=True)
    # 取引金額
    # amount_from = request.GET.get('amount1')
    # amount_to = request.GET.get('amount2')
    # try:
    #     if amount_from and amount_to:
    #         amount_from = amount_from.replace(',','')
    #         amount_to = amount_to.replace(',','')
    #         queryset = queryset.filter(total_amount__range=[int(amount_from), int(amount_to)])
    #     elif amount_from:
    #         amount_from = amount_from.replace(',','')
    #         queryset = queryset.filter(total_amount__gte=int(amount_from))
    #     elif amount_to:
    #         amount_to = amount_to.replace(',','')
    #         queryset = queryset.filter(total_amount__lte=int(amount_to))
    # except Exception:
    #     logger.exception('sv_filter_evidence amount: ' + amount_from + '～' + amount_to)

    amount = request.GET.get('amount')
    if amount:
        amount = amount.replace(',','')
        try:
            amount_choice = request.GET.get('amount_choice')
            if amount_choice == '1':    # 以下
                # queryset = queryset.filter(total_amount__lt=int(amount))
                queryset = queryset.filter(total_amount__lte=int(amount))
            elif  amount_choice == '2': # 以上
                # queryset = queryset.filter(total_amount__gt=int(amount))
                queryset = queryset.filter(total_amount__gte=int(amount))
            elif  amount_choice == '3': # 等しい
                queryset = queryset.filter(total_amount=int(amount))
        except Exception:
            logger.exception(f'{amount=}')
    return queryset
# 本日で絞り込み
def sv_filter_today(queryset):
    today = datetime.date.today()
    return filter_create_date(queryset, today)
# 作成日で絞り込み
def filter_create_date(queryset, day):
    try:
    # Djangoでは、PostgreSQLだとdatetimeFieldはDB上ではtimestamp with time zoneとなり、タイムゾーンはUTC
    # todayをUTCに変換
        today_start_str = str(day) + ' 00:00:00'
        today_start = datetime.datetime.strptime(today_start_str, '%Y-%m-%d %H:%M:%S')
        today_start = today_start.astimezone(datetime.timezone.utc)
        # today_start = today_start - datetime.timedelta(hours=9)
        today_end_str = str(day) + ' 23:59:59'
        today_end = datetime.datetime.strptime(today_end_str, '%Y-%m-%d %H:%M:%S')
        today_end = today_end.astimezone(datetime.timezone.utc)
        # today_end = today_end + datetime.timedelta(hours=15)
        queryset = queryset.filter(create_date__range=(today_start, today_end))
    except Exception:
        logger.exception(f'filter date={day}')
    return queryset

# UTF-8 から Shift-JIS に変換できない文字コードがあるため、
# 「 CP932 」文字コード、errors='replace'で変換する(無効なバイト列を？に置き換える)
def cp932_replace(str):
    if str:
        str = str.encode('cp932', 'replace')
        str = str.decode('cp932')
    return str

# エビデンス情報からCSVを作成する
def sv_response_evidence(queryset):
    response = HttpResponse(content_type='text/csv; charset=CP932')
    # response = HttpResponse(content_type='text/csv')    # BOM付きのUTF-8のCSVファイル
    now = datetime.datetime.now()
    str_time = now.strftime('_%Y%m%d%H%M%S')

    csvfile = 'エビデンス' + str_time + '.csv'
    filename = urllib.parse.quote((csvfile).encode('utf8'))
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'{}'.format(filename)

    # writer = csv.writer(response, quoting=csv.QUOTE_ALL)    # 全てのフィールドをクォートします。
    writer = csv.writer(response)
    # sio = io.StringIO()         # BOM付きのUTF-8のCSVファイル
    # writer = csv.writer(sio)    # BOM付きのUTF-8のCSVファイル

    # header = ['ファイル名', 'カテゴリ', '金額', '取引先', '日付']
    header = ['カテゴリ', '金額', '取引先', '発行元', '取引日', '科目', '摘要']
    writer.writerow(header)
    for evidence in queryset:
        partner = sv_get_partner_name(evidence.partner_id)
        publisher = sv_get_publisher_name(evidence.publisher_id)
        try:
            processed_date = evidence.processed_date.strftime('%Y/%m/%d')
        except Exception:
            processed_date = ''
        try:
            amount = evidence.total_amount.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
            # amount = '{:,}'.format(amount)
        except Exception:
            amount = ''
        # UTF-8 から Shift-JIS に変換できない文字コードがあるため、
        # 「 CP932 」文字コード、errors='replace'で変換する
        publisher = cp932_replace(publisher)
        partner = cp932_replace(partner)
        account = ''
        if evidence.account_id:
            try:
                account = MtAccount.objects.get(account_id=evidence.account_id).account_name
            except MtAccount.DoesNotExist:
                pass
        account = cp932_replace(account)
        account_desc = evidence.account_desc or ''
        account_desc = cp932_replace(account_desc)
        slip_number= evidence.slip_number or '',
        try:
            writer.writerow([
                        #   evidence.pdf_name,
                          evidence.category_name,
                          amount,
                          partner,
                          publisher,
                          processed_date,
                          account,
                          account_desc
                        ])
        except Exception:
            logger.exception('sv_response_evidence writerow exception')
    logger.debug(f'sv_response_evidence {csvfile}')
    # response.write(sio.getvalue().encode('utf_8_sig'))    # BOM付きのUTF-8のCSVファイル

    return response

# 取引先情報からCSVを作成する
def sv_response_partner(queryset):
    response = HttpResponse(content_type='text/csv; charset=CP932')
    now = datetime.datetime.now()
    str_time = now.strftime('_%Y%m%d%H%M%S')

    csvfile = '取引先' + str_time + '.csv'
    fname = urllib.parse.quote((csvfile).encode('utf8'))
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'{}'.format(fname)

    writer = csv.writer(response)
    header = ['取引先ID','取引先','取引先名（略称）','法人番号','取引先区分','担当者部門','担当者','担当者メールアドレス','郵便番号','住所','ビル・棟名他','電話番号','FAX番号','削除フラグ']
    writer.writerow(header)
    for partner in queryset:
        if partner.partner_type == 1:
            type = '顧客'
        elif partner.partner_type == 2:
            type = '仕入先'
        else:
            type = ''
        if partner.delete_flg == 1:
            delete_flg = 'true'
        else:
            delete_flg = ''
        # UTF-8 から Shift-JIS に変換できない文字コードがあるため、
        # 「 CP932 」文字コード、errors='replace'で変換する
        if partner.partner_name:
            partner_name = cp932_replace(partner.partner_name)
        else:
            partner_name = ''
        if partner.partner_ryaku_name:
            partner_ryaku_name = cp932_replace(partner.partner_ryaku_name)
        else:
            partner_ryaku_name = ''
        try:
            writer.writerow([
                        partner.partner_id or '',
                        partner_name,
                        partner_ryaku_name,
                        partner.corporate_number.strip() if partner.corporate_number else '',
                        type,
                        partner.charge_dept or '',
                        partner.charge_name or '',
                        partner.charge_email or '',
                        partner.zip_code or '',
                        partner.address1 or '',
                        partner.address2 or '',
                        partner.tel_no or '',
                        partner.fax_no or '',
                        delete_flg,
                        ])

        except Exception:
            logger.exception('sv_response_partner writerow exception')
    logger.debug(f'sv_response_partner {csvfile}')
    return response

# 取引先CSVファイルを作成する
def sv_response_partner_sample():
    response = HttpResponse(content_type='text/csv; charset=CP932')
    now = datetime.datetime.now()
    str_time = now.strftime('_%Y%m%d%H%M%S')

    csvfile = '取引先' + str_time + '.csv'
    fname = urllib.parse.quote((csvfile).encode('utf8'))
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'{}'.format(fname)
    try:
        writer = csv.writer(response)
        header = ['取引先ID','取引先','取引先名（略称）','法人番号','取引先区分','担当者部門','担当者','担当者メールアドレス','郵便番号','住所','ビル・棟名他','電話番号','FAX番号','削除フラグ']
        writer.writerow(header)
    except Exception:
        logger.exception('sv_response_partner_sample writerow exception')
    logger.debug(f'sv_response_partner_sample {csvfile}')

    return response

    # response['content_type'] = 'text/csv'
    # response['Content-Disposition'] = 'attachment; filename=' + fname
    
    # if os.path.exists(csvfile):
    #     response = FileResponse(open(csvfile, 'rb'))

    # return response        
# 履歴 検索条件で絞り込み
def sv_filter_history(owner_id, request, queryset):
    kubun = request.GET.get('kubun')
    if kubun:
        if kubun == 'change':
            queryset = queryset.filter(rireki_kbn='U')
        elif kubun == 'ocr':
            queryset = queryset.filter(rireki_kbn='O')
        elif kubun == 'delete':
            queryset = queryset.filter(rireki_kbn='D')
    pdf_name = request.GET.get('pdf_name')
    if pdf_name:
        queryset = queryset.filter(pdf_name__contains=pdf_name)
    # 処理年月: yyyy/mm
    shori_date = request.GET.get('shori_date')
    if shori_date:
        dt = shori_date.replace('/', '').replace('-', '')
        if 6 < len(dt):
            dt = dt[:6]
        queryset = queryset.filter(processed_ym=dt)
        # bom = datetime.datetime.strptime(shori_date + '/01','%Y/%m/%d')
        # eom = ut_get_endofmonth(bom)
        # queryset = queryset.filter(create_date__range=[bom, eom])
    # 処理年月日: yyyy/mm/dd
    create_date = request.GET.get('create_date')
    if create_date:
        try:
            dt = create_date.replace('/', '').replace('-', '')
            bom = datetime.datetime.strptime(dt,'%Y%m%d').date()
            queryset = filter_create_date(queryset, bom)
        except Exception:
            logger.exception(f'{create_date=}')
    # カテゴリを選択
    category = request.GET.get('category')
    if category and category != '0':
            queryset = queryset.filter(category_name=category)
    # 伝票番号を入力
    slip_number = request.GET.get('slip_number')
    if slip_number and 0 < len(slip_number):
        queryset = queryset.filter(slip_number=slip_number)

    # 取引先を入力
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
            logger.exception(f'{partner=}')
    # 発行元を入力
    publisher = request.GET.get('publisher')
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

    # 取引日: yyyy/mm/dd
    date_from = request.GET.get('process_date1')
    date_to = request.GET.get('process_date2')
    if date_from and date_to:
        queryset = queryset.filter(processed_date__range=[date_from, date_to]).order_by('processed_date')
    elif date_from:
        queryset = queryset.filter(processed_date__gte=date_from).order_by('processed_date')
    elif date_to:
        queryset = queryset.filter(processed_date__lte=date_to).order_by('processed_date')
    # else:
    #     queryset = queryset.filter(processed_date__isnull=True)
    # 取引金額
    # amount_from = form.cleaned_data.get('amount1')
    # amount_to = form.cleaned_data.get('amount2')
    # try:
    #     if amount_from and amount_to:
    #         amount_from = amount_from.replace(',','')
    #         amount_to = amount_to.replace(',','')
    #         queryset = queryset.filter(total_amount__range=[int(amount_from), int(amount_to)])
    #     elif amount_from:
    #         amount_from = amount_from.replace(',','')
    #         queryset = queryset.filter(total_amount__gte=int(amount_from))
    #     elif amount_to:
    #         amount_to = amount_to.replace(',','')
    #         queryset = queryset.filter(total_amount__lte=int(amount_to))
    # except Exception:
    #     logger.exception('EvcEviHistoryListView amount: ' + amount_from + '～' + amount_to)

    amount = request.GET.get('amount')
    if amount:
        amount = amount.replace(',','')
        try:
            amount_choice = request.GET.get('amount_choice')
            if amount_choice == '1':    # 以下
                # queryset = queryset.filter(total_amount__lt=int(amount))
                queryset = queryset.filter(total_amount__lte=int(amount))
            elif  amount_choice == '2': # 以上
                # queryset = queryset.filter(total_amount__gt=int(amount))
                queryset = queryset.filter(total_amount__gte=int(amount))
            elif  amount_choice == '3': # 等しい
                queryset = queryset.filter(total_amount=int(amount))
        except Exception:
            logger.exception(f'{amount=}')
    return queryset
# 履歴情報からCSVを作成する
def sv_response_history(queryset):
    response = HttpResponse(content_type='text/csv; charset=CP932')
    now = datetime.datetime.now()
    str_time = now.strftime('_%Y%m%d%H%M%S')

    csvfile = 'エビデンス変更履歴' + str_time + '.csv'
    filename = urllib.parse.quote((csvfile).encode('utf8'))
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'{}'.format(filename)

    # writer = csv.writer(response, quoting=csv.QUOTE_ALL)    # 全てのフィールドをクォートします。
    writer = csv.writer(response)
    # header = ['ファイル名', 'カテゴリ', '金額', '取引先', '日付']
    header = ['履歴区分', 'カテゴリ', '金額', '取引先', '発行元', '取引日', '科目', '摘要']
    writer.writerow(header)
    for htevidence in queryset:
        kubun = ''
        if htevidence.rireki_kbn:
            # 履歴区分にユーザ名を表示
            if htevidence.rireki_kbn == 'U':
                kubun = 'キー修正'
            elif htevidence.rireki_kbn == 'O':
                kubun = 'OCR修正'
            elif htevidence.rireki_kbn == 'D':
                kubun = '削除'
        partner = sv_get_partner_name(htevidence.partner_id)
        publisher = sv_get_publisher_name(htevidence.publisher_id)
        try:
            processed_date = htevidence.processed_date.strftime('%Y/%m/%d')
        except Exception:
            processed_date = ''
        try:
            amount = htevidence.total_amount.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
            # amount = '{:,}'.format(amount)
        except Exception:
            amount = ''
        # UTF-8 から Shift-JIS に変換できない文字コードがあるため、
        # 「 CP932 」文字コード、errors='replace'で変換する
        publisher = cp932_replace(publisher)
        partner = cp932_replace(partner)
        account = ''
        if htevidence.account_id:
            try:
                account = MtAccount.objects.get(account_id=htevidence.account_id).account_name
            except MtAccount.DoesNotExist:
                pass
        account = cp932_replace(account)
        account_desc = htevidence.account_desc or ''
        account_desc = cp932_replace(account_desc)
        slip_number= htevidence.slip_number or '',
        try:
            writer.writerow([
                        #   htevidence.pdf_name,
                          kubun,
                          htevidence.category_name,
                          amount,
                          partner,
                          publisher,
                          processed_date,
                          account,
                          account_desc
                        ])
        except Exception:
            logger.exception('sv_response_history writerow exception')
    logger.debug(f'sv_response_history {csvfile}')
            
    return response
