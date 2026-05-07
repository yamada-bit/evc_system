import re
import requests
import datetime
import logging
import math

from Evc_App.sv_file import (
    sv_get_partner_id,sv_get_publisher_id,
    sv_get_partner_name,sv_get_partner_ryaku_name,sv_conv_company,
    sv_save_detect,get_new_partner_id
)
from users.models import MtPartner

logger = logging.getLogger(__name__)

# 取引先のList 取引先名 + 取引先名(略)
def get_partner_ryaku_list(owner_id):
    partners = []
    lists = MtPartner.objects.filter(owner_id=owner_id).exclude(delete_flg=1).values('partner_id', 'partner_name', 'partner_ryaku_name').order_by('partner_name')
    for item in lists:
        if item and item.get('partner_id'):
            # 空白を除去する
            name = item.get('partner_name') or ''
            name = re.sub(r'\s+', '', name) # 空白は除去
            ryaku = item.get('partner_ryaku_name') or ''
            ryaku = re.sub(r'\s+', '', ryaku) # 空白は除去
            partners.append((item.get('partner_id'), name, ryaku))
    return partners
# textdataの中心座標
def center(textdata):
    x = (textdata.x1 + textdata.x2) / 2
    y = (textdata.y1 + textdata.y2) / 2
    return (x, y)
# textdata間の距離を計算
def distance(textdata1, textdata2):
    c1 = center(textdata1)
    c2 = center(textdata2)
    return math.hypot(c1[0] - c2[0], c1[1] - c2[1])
# 基準のtextdataに近いほうのtextdataを取得
def closer_rect(target, textdata1, textdata2):
    if not target or not textdata1 or not textdata2:
        return None
    d1 = distance(target, textdata1)
    d2 = distance(target, textdata2)
    
    if d1 < d2:
        return textdata1
    else:
        return textdata2

# 取引先,発行元を抽出（登録番号が抽出されたら発行元に）
# textdatalist : areaのtextdataのリスト
# text : 空白文字（改行、タブ、スペースなど）削除した全文データ
def detect_partner(user_id, owner_id, textdatalist, texts, evidence_id):
    reg_publisher_id = None     # 登録番号に対応する取引先マスタのID
    reg_publisher_name = None   # 登録番号に対応した取引先マスタの取引先名

    corporate_number, reg_textdata = extract_registration(textdatalist)    # 登録番号(数字13桁)抽出
    # corporate_number = extract_invoice_number(texts)
    # if corporate_number:
    #     # 登録番号で取引先マスタを検索,なければ登録
    #     reg_publisher_id, reg_publisher_name = get_company_id(user_id, owner_id, corporate_number)

    result = get_matched_partner_id(user_id, owner_id, textdatalist, texts)

    partner_id = result.get('partner_id')
    detect_partner_name = result.get('detect_partner_name')
    matched_partner = result.get('matched_partner')
    textdata_partner = result.get('textdata_partner')
    publisher_id = result.get('publisher_id')
    detect_publisher_name = result.get('detect_publisher_name')
    matched_publisher = result.get('matched_publisher')
    textdata_publisher = result.get('textdata_publisher')

    if reg_publisher_id:    # 登録番号法人が抽出された場合
        if reg_publisher_id == partner_id:  # 登録番号法人が取引先に設定されていた場合
            partner_id = publisher_id
            detect_partner_name = detect_publisher_name
        elif reg_textdata and textdata_partner and textdata_publisher:
            result = closer_rect(reg_textdata, textdata_partner, textdata_publisher)
            # 取引先・発行元の座標と登録番号の座標を比較し登録番号に近いほうを発行元にする
            if result == textdata_partner:  # 登録番号に近いほうが取引先に設定されていた場合
                partner_id = publisher_id
                detect_partner_name = detect_publisher_name
        # 登録番号法人を発行元に設定
        publisher_id = reg_publisher_id
        detect_publisher_name = reg_publisher_name
    else:
        if detect_partner_name and not detect_publisher_name:
            if publisher_id:
                # 検索キーを含む検索文字列（取引先として抽出されている）が後方にあり
                # 検索キーを含まない取引先マスタの取引先名での検索文字列(発行元)が前方にある
                # 検索処理の実行の順序で前方の文字列が発行元として抽出されている
                n1 = texts.find(matched_partner)    # 空白除去した全文データ
                n2 = texts.find(matched_publisher)
                if 0 <= n2 and n2 < n1:
                    id = publisher_id
                    publisher_id = partner_id
                    detect_publisher_name = detect_partner_name
                    partner_id = id
                    detect_partner_name = None

    logger.debug(f'{partner_id=}')
    logger.debug(f'{publisher_id=}')
    # 取引先データがなければ検出情報データ作成
    if (not partner_id and detect_partner_name) or (not publisher_id and detect_publisher_name):
        sv_save_detect(detect_partner_name, detect_publisher_name, user_id, evidence_id)

    return partner_id, publisher_id

# 取引先,発行元を検索
def get_matched_partner_id(user_id, owner_id, textdatalist, texts):
    partner_id = None
    detect_partner_name = None
    matched_partner = None
    textdata_partner = None
    publisher_id = None
    detect_publisher_name = None
    matched_publisher = None
    textdata_publisher = None
    # 取引先マスタから取引先名・取引先名（略称）のリストを取得（空白は除去）
    partner_ryaku_list = get_partner_ryaku_list(owner_id)

    # TextDataごとに検索キーで取引先の抽出
    partner_list = get_matched_partner_name(partner_ryaku_list, textdatalist)
    # 1件目：取引先、2件目：発行元
    if partner_list:
        # matched_partner = partner_list[0]
        matched_partner = partner_list[0].get('name')
        name = sv_conv_company(matched_partner)
        detect_partner_name = name
        textdata_partner = partner_list[0].get('textdata')
        # 抽出取引先名でID取得
        partner_id = sv_get_partner_id(name, owner_id)
        if not partner_id:
            # 抽出した名前(空白除去)で取引先マスタの取引先名・取引先名（略称）を検索してID取得
            partner_id = get_db_matched_partner_id(partner_ryaku_list, name)
        if 1 < len(partner_list):   # 発行元名が抽出された場合
            # matched_publisher = partner_list[1]
            matched_publisher = partner_list[1].get('name')
            name = sv_conv_company(matched_publisher)
            detect_publisher_name = name
            textdata_publisher = partner_list[1].get('textdata')
            # 抽出発行元名でID取得
            publisher_id = sv_get_publisher_id(name, user_id)
            if not publisher_id:
                # 契約会社マスタで一致しない場合、取引先マスタで検索
                publisher_id = sv_get_partner_id(name, owner_id)
                if not publisher_id:
                    # 抽出した名前(空白除去)で取引先マスタの取引先名・取引先名（略称）を検索してID取得
                    publisher_id = get_db_matched_partner_id(partner_ryaku_list, name)
    else:
        # TextDataごとに取引先マスタの取引先名を検索
        # partner_id,matched_partner = get_matched_partner_list(partner_ryaku_list, None, None, textdatalist)
        result = get_matched_partner_list(partner_ryaku_list, None, None, textdatalist)
        partner_id = result.get('id')
        textdata_partner = result.get('textdata')
        matched_partner = result.get('name')    # 空白除去
    # if (not publisher_id and not matched_publisher) and (partner_id or partner_list):
    if matched_partner and not detect_publisher_name:
        # TextDataごとに取引先マスタの取引先名を検索(抽出した取引先を除外)
        # publisher_id,matched_publisher = get_matched_partner_list(partner_ryaku_list, partner_id, matched_partner, textdatalist)
        result = get_matched_partner_list(partner_ryaku_list, partner_id, matched_partner, textdatalist)
        publisher_id = result.get('id')
        textdata_publisher = result.get('textdata')
        matched_publisher = result.get('name')  # 空白除去
        # if not publisher_id:
        #     # 先頭一致で取引先マスタの取引先名を検索(最小文字数が必要)
        #     publisher_id = check_startswith_partner_list(partner_ryaku_list, name, textdatalist)
        # else:    # 発行元未検出
        #     # 取引先を発行元にも設定
        #     publisher_id = partner_id

    result = {
        'issuer': None,
        'method': None,
        'corporate_number': None,
        'partner_id': partner_id,
        'detect_partner_name': detect_partner_name,
        'matched_partner': matched_partner,
        'textdata_partner': textdata_partner,
        'publisher_id': publisher_id,
        'detect_publisher_name': detect_publisher_name,
        'matched_publisher': matched_publisher,
        'textdata_publisher': textdata_publisher,
    }
    return result
    # return partner_id, publisher_id

# TextDataごとに取引先の検索
# 行ごとにすると会社名以外の情報が連結されるためTextDataごとに
# e.g.請求書_株式会社 システムブリッジ様_00130438 株式会社 システムブリッジmagic
def get_matched_partner_name(partner_ryaku_list, textdatalist):
    pattern_dict = {}
    # \u4E00-\u9FFF：漢字 \u3040-\u30FF：ひらがな・カタカナ \uFF66-\uFF9F：半角カタカナ \w：英数字やアンダースコア
    # pattern_dict['name'] = r'株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|会社|\.co\.jp'
    # pattern_tupple = ('株式会社','合同会社','(株)','（株）','有限会社','(有)','（有）','会社','.co.jp','.co.jp™')
    pattern_dict['begin'] = r'^(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\(同\)|（同）)[\u4E00-\u9FFF\u3040-\u30FF\uFF66-\uFF9F\w]+'         # 先頭
    # pattern_dict['end'] = r'\w+(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\(同\)|（同）|\.co\.jp)$' # 末尾
    pattern_dict['end'] = r'[\u4E00-\u9FFF\u3040-\u30FF\uFF66-\uFF9F\w]+(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\(同\)|（同）|\.co\.jp)$' # 末尾
    pattern_dict['pre'] = r'(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\(同\)|（同）)[\u4E00-\u9FFF\u3040-\u30FF\uFF66-\uFF9F\w]+' # 株式会社○○
    pattern_dict['suf'] = r'[\u4E00-\u9FFF\u3040-\u30FF\uFF66-\uFF9F\w]+(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\(同\)|（同）|\.co\.jp)'   # ○○株式会社
    pattern_item = r'(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\(同\)|（同）)'
    url_pattern = r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+'
    # taxi_pattern = r'.+タクシー$' # 末尾
    # pattern_dict['begin2'] = r'^(合資会社|\(資\)|（資）|合名会社|\(名\))\w+'    # 先頭
    # pattern_dict['end2'] = r'\w+(合資会社|\(資\)|（資）|合名会社|\(名\))$'      # 末尾
    # 優先キーワード
    keywords = [
        'Inc.', 'Ltd.', 'Co.,', 'Corp.', 'GK', 'G.K.', 'KK', 'K.K'
    ]
    pattern_company = r'(Inc\.?|Ltd\.?|Corp\.?|LLC|K\.?K\.?|G\.?K\.?)'

    charcode = 'cp932' # 文字コード指定

    partner_list = []
    # test_list = [
    #   'マジックソフトウェア・ジャパン株式会社エン',
    #   '株式会社 システムブリッジ',
    #   'ANA X株式会社',
    #   '全日本空輸株式会社 All Nippon Airways Co.,Ltd'
    # ]
    # for text in test_list:
    for textdata in textdatalist:
        try:
            name = False
            text = extract_name(textdata.text)  # 御中・様除去
            if re.search(url_pattern, text):
                continue
            for key, pattern in pattern_dict.items():
                if key == 'pre' or key == 'suf':
                    # 文字列の途中でも一致（空白で分割されるため空白は含まない文字列での抽出）
                    result = re.search(pattern, text)
                    if result:
                        name = result.group()
                        m = re.search(pattern_item, text)
                        if m:
                            start, end = m.span()
                            name1 = text[start:]
                            name2 = text[:end]
                            # 検索キーの前後の文字列を取引先マスタでチェック(空白は除去)
                            name = check_partner_list(partner_ryaku_list, name, name1, name2)
                    # result = re.search(pattern, text)
                    # if result:
                    #     name = result.group()
                else:
                    # 先頭・末尾で一致(空白を除くことで空白を含む文字列を抽出)
                    text2 = re.sub(r'\s+', '', text)    # 空白を除く (株式会社 システムブリッジなど対応)
                    result = re.search(pattern, text2)
                    if result:
                        name = result.group()   # 途中に空白がある会社名の取得ができない(ANA X株式会社)
                        if text != text2:
                            cnt = len(result.groups())
                            if 0 < cnt:
                                match = (result.group(1))
                                if match:
                                    if key == 'begin':
                                        name = match + text.replace(match, '').strip()  # 前後の空白削除
                                    else:
                                        name = text.replace(match, '').strip() + match

                if name:
                    byte_text = name.encode() # 文字列エンコード
                    # 取引先名:50byte
                    if 49 < len(byte_text):
                        logger.debug(f'name length > 49 : {name}')
                        if key == 'begin' or key == 'pre':
                            name = name[0:25]
                        else:
                            name = name[-25:]
                    break
            # if name:
            #     name = re.sub(r'\s+', '', name)   # remove_all_whitespace
            # if not name:
            #     m = re.search(taxi_pattern, text)
            #     if m:
            #         start, end = m.span()
            #         name = text
            if not name:
                result = re.search(pattern_company, text)
                if result:
                    start, end = result.span()
                    name1 = text[start:]
                    name2 = text[:end]  # キーワードまでを抽出
                    name = name2
                    byte_text = name.encode() # 文字列エンコード
                    if 49 < len(byte_text):
                        logger.debug(f'name length > 49 : {name}')
                        name = name[-50:]
                else:
                    continue
            # if not name:
            #     # Ltd.がある場合、Ltd.の左側を抽出(スペースも含めて抽出)
            #     idx = text.find('Ltd.')
            #     if 0 < idx:
            #         name = text[:idx + 4]
            #         byte_text = name.encode() # 文字列エンコード
            #         if 49 < len(byte_text):
            #             logger.debug(f'name length > 49 : {name}')
            #             name = name[-50:]
            #     else:
            #         continue
            logger.debug(f'partner_name {name}')
            if partner_list:
                for list in partner_list:
                    if name != list.get('name'):
                        partner_list.append({'name':name, 'textdata':textdata})
                        # partner_list.append(name)
                        # 2件で終了
                        return partner_list
            else:
                # partner_list.append(name)
                partner_list.append({'name':name, 'textdata':textdata})
        except Exception:
            continue
    return partner_list

# 文字列途中の一致の場合
def extract_partner(text):
    patterns = [
        r'(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社)[\u4E00-\u9FFF\u3040-\u30FF\uFF66-\uFF9F\w]+',          # 株式会社○○
        r'[\u4E00-\u9FFF\u3040-\u30FF\uFF66-\uFF9F\w]+(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\.co\.jp)', # ○○株式会社
    ]    
    # for pattern in pattern_tupple:
    # Python3の文字列に対しては、\wはデフォルトで全角の日本語や英数字などにもマッチ
    try:
        for i, pattern in enumerate(patterns):
            result = re.search(pattern, text)
            if result:
                name = result.group()
                byte_text = name.encode() # 文字列エンコード
                if 49 < len(byte_text):
                    logger.debug(f'name length > 49 : {name}')
                    if i == 0:
                        name = name[0:25]
                    else:
                        name = name[-25:]
                return name
    except Exception:
        logger.exception(f'extract_partner exception {text=}')
        return False
       
    return False

def extract_name(text):
    if text:
        name = text
        idx = text.find('御中')
        if 0 < idx:
            name = text[:idx]
        else:
            idx = text.find('様')
            if 0 < idx:
                name = text[:idx]
        name = name.strip() # 両端の連続する空白文字が取り除かれる
    else:
        name = ''
    return name
# 検索キーの前後の文字列で取引先マスタの取引先名の文字列を検索
def check_partner_list(partner_ryaku_list, name, name1, name2):
    name = re.sub(r'\s+', '', name) if name else '' # 空白は除去
    name1 = re.sub(r'\s+', '', name1) if name1 else '' # 空白は除去
    name2 = re.sub(r'\s+', '', name2) if name2 else '' # 空白は除去
    for list in partner_ryaku_list:
        # ('partner_id', 'partner_name', 'partner_ryaku_name')
        if list[1]:
            list1 = list[1]
            ryaku1 = list[2]
            if name == list1 or name == ryaku1:
                return name
            if name1 == list1 or name1 == ryaku1:
                return name1
            if name2 == list1 or name2 == ryaku1:
                return name2
    return name

# 取引先マスタの取引先名・取引先名（略称）を検索してidを取得
def get_db_matched_partner_id(partner_ryaku_list, name):
    if not name:
        return None
    partner_id = None
    name = re.sub(r'\s+', '', name) # 空白は除去
    for list in partner_ryaku_list:
        # ('partner_id', 'partner_name', 'partner_ryaku_name')
        if list[1]:
            if list[1] == name:
                partner_id = list[0]
                break
            if list[2]:
                if list[2] == name:
                    partner_id = list[0]
                    break
    if not partner_id:
        for list in partner_ryaku_list:
            if list[1]:
                if list[1] in name:
                    partner_id = list[0]
                    break
                if list[2]:
                    if list[2] in name:
                        partner_id = list[0]
                        break

    logger.debug(f'{partner_id=}')
    return partner_id
# TextDataごとに取引先マスタの取引先名を検索(抽出した取引先を除外)
def get_matched_partner_list(partner_ryaku_list, partner_id, matched_partner, textdatalist):
    if partner_id:
        # 取引先名取得
        partner_name = sv_get_partner_name(partner_id)
        if partner_name:
            partner_name = re.sub(r'\s+', '', partner_name) # 空白は除去
        # 取引先名(略称)取得
        partner_ryaku_name = sv_get_partner_ryaku_name(partner_id)
        if partner_ryaku_name:
            partner_ryaku_name = re.sub(r'\s+', '', partner_ryaku_name)
    else:
        partner_name = None
        partner_ryaku_name = None
    if matched_partner:
        matched_partner = re.sub(r'\s+', '', matched_partner)
    matched_partner_id = None
    result = {
        'id':None,
        'name':'',
        'textdata':None,
    }
    for textdata in textdatalist:
        if not textdata.text:
            continue
        text = re.sub(r'\s+', '', textdata.text) # 空白は除去
        # 抽出済みの取引先名・取引先名（略称）は除外
        if text == partner_name or text == partner_ryaku_name or text == matched_partner:
            continue
        if partner_name and partner_name in text\
                or partner_ryaku_name and partner_ryaku_name in text\
                or matched_partner and matched_partner in text:
            continue
        for list in partner_ryaku_list:
            if text == list[1]: # 取引先マスタの取引先名
                matched_partner_id = list[0]
                break
            if text == list[2]: # 取引先マスタの取引先名(略称)
                matched_partner_id = list[0]
                break
            if list[1]: # 検索キーを除外した取引先名で検索
                remove_key_name = remove_search_key(list[1])
                if text == remove_key_name:
                    matched_partner_id = list[0]
                    break
            if list[2]:
                remove_key_name = remove_search_key(list[2])
                if text == remove_key_name:
                    matched_partner_id = list[0]
                break
        if matched_partner_id:
            result['id'] = matched_partner_id
            result['name'] = text
            result['textdata'] = textdata
            break
    logger.debug(f'{matched_partner_id=} {result["name"]}')

    return result   #matched_partner_id,matched_string
# 検索キーを除去
def remove_search_key(text):
    patterns = [
        # r'(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社)',          # 株式会社○○
        r'(株式会社|\(株\)|（株）|有限会社|\(有\)|（有）|合同会社|\.co\.jp)', # ○○株式会社
    ]
    if text:
        try:
            for pattern in patterns:
                result = re.search(pattern, text)   # 検索キーで検索
                if result:
                    start, end = result.span()
                    s1 = text[start:end]
                    text = text.replace(s1, '')   # 検索キーを除去
        except Exception:
            logger.exception('exception')
    return text

# 取引先マスタの取引先名の文字列を先頭一致で検索
# 印影などで途中で切れている場合の対応
def check_startswith_partner_list(partner_ryaku_list, partner_name, textdatalist):
    publish_id = None
    try:
        for textdata in textdatalist:
            text = textdata.text
            if not text or len(text) < 10:  # 最小文字数が必要
                continue
            name = re.sub(r'\s+', '', text) if text else '' # 空白は除去
            if partner_name.startswith(name):   # 取引先はSKIP
                continue
            for list in partner_ryaku_list:
                # ('partner_id', 'partner_name', 'partner_ryaku_name')
                list1 = list[1]
                ryaku1 = list[2]
                if list1.startswith(name) or ryaku1.startswith(name):
                    publish_id = list[0]
                    break
            if publish_id:
                logger.debug(f'partner startswith : {text} : {publish_id}')
                break
    except Exception:
        logger.exception('check_startswith_partner_list exception')
    return publish_id
# =========================
# 登録番号抽出
# =========================
def extract_registration(textdatalist):
    reg_pattern = r'T\d{13}'
    for textdata in textdatalist:
        text = textdata.text
        # if line['y'] > 200:
        match = re.search(reg_pattern, text)
        if match:
            reg_no = match.group()
            if reg_no.startswith('T'):
                return reg_no[1:], textdata
            # T・ハイフン・スペースを除去して数字のみにする
            # reg_no = re.sub(r'[^0-9]', '', reg_number)
            
            return reg_no, textdata
    return None, None
# =========================
# 登録番号で取引先マスタを検索,なければ法人番号APIで会社名取得し登録
# =========================
def get_company_id(user_id, owner_id, corporate_number):
    issuer = None
    partner_id = None
    # 法人番号で検索
    partnerobj = MtPartner.objects.filter(owner_id=owner_id, corporate_number=corporate_number).exclude(delete_flg=1).first()
    if partnerobj:
        issuer = partnerobj.partner_name
        partner_id = partnerobj.partner_id
        issuer_method = 'partner_db'
    else:
        # issuer = fetch_company_name_from_invoice_api(corporate_number)
        # issuer_method = 'invoice_api'
        # 法人番号APIで会社名取得
        company_info = get_company_info(corporate_number)
        if company_info:
            issuer = company_info.get('name')
            # 名称で検索
            partnerobj = MtPartner.objects.filter(owner_id=owner_id, partner_name=issuer).exclude(delete_flg=1).first()
            # 「get」で条件に合ったオブジェクトが複数個存在する場合、MultipleObjectsReturnedという例外が発生
            # partner_id = MtPartner.objects.get(partner_name=name).partner_id
            if partnerobj:
                partner_id = update_partner_registration(partnerobj, user_id, corporate_number)
            else:
                partner_id = create_partner_registration(user_id, owner_id, issuer, corporate_number)
            issuer_method = 'invoice_api'
    return partner_id, issuer

API_KEY = 'あなたのAPIキー'
# =========================
# 法人番号APIで会社名取得
# =========================
def get_company_info(corporate_number: str):
    # reg_dict = {
    #     '6010003022051':'Google Cloud Japan GK',
    #     '5011001032976':'マジックソフトウェア・ジャパン株式会社',
    #     '6810468297923':'シェ　アンドレ　ド　サクレクール',
    #     '8700150129635':'Squarespace Ireland Limited',
    # }
    # for key, val in reg_dict.items():
    #     if corporate_number == key:
    #         return {
    #             'name': val,
    #             'address': ''
    #         }
    # return None
    url = 'https://api.houjin-bangou.nta.go.jp/4/num'
    
    params = {
        'id': API_KEY,
        'number': corporate_number,
        'type': '12'  # JSON
    }
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        return None
    data = response.json()
    try:
        company = data['corporations'][0]
        return {
            'name': company['name'],
            'address': company['prefectureName'] + company['cityName']
        }
    except (KeyError, IndexError):
        return None
# =========================
# インボイスAPIで会社名取得
# =========================
def fetch_company_name_from_invoice_api(reg_no: str):
    """
    国税庁インボイス登録番号照会API
    """
    url = 'https://www.invoice-kohyo.nta.go.jp/regno-search/num'
    
    params = {
        'number': reg_no,
        'type': 'json'
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        # res.raise_for_status()
        data = res.json()
        # APIレスポンス例に応じて調整
        if data and 'results' in data and len(data['results']) > 0:
            return data['results'][0].get('name')
    except Exception as e:
        print(f'API error: {e}')
        # pass
    return None

# =========================
# 登録番号と国税庁のデータから取引先データ作成
# =========================
def create_partner_registration(user_id, owner_id, name, corporate_number):
    if not name or not owner_id:
        return None
    # d = datetime.date.today().strftime('%y%m%d')
    # id = d + '0001'
    id = get_new_partner_id()

    try:
        create_date=datetime.datetime.now() 
        obj = MtPartner(
            partner_id=id,
            partner_name=name,
            owner_id=owner_id,
            partner_type=0,
            corporate_number=corporate_number,
            delete_flg=0,
            create_date=create_date,
            create_user=user_id,
            update_user=user_id,
            update_date=create_date,
        )
        obj.save()
        logger.info(f'create_partner_registration {id} : {name}')
    except Exception:
        logger.exception(f'create_partner_registration save Exception {id} : {name}')
        id = None

    return id
# =========================
# 取引先データ登録番号更新
# =========================
def update_partner_registration(partner_obj, user_id, corporate_number):
    id = partner_obj.partner_id
    try:
        partner_obj.corporate_number = corporate_number
        partner_obj.update_user = user_id
        partner_obj.update_date = datetime.datetime.now()
        partner_obj.save()
        logger.info(f'update_partner_registration {id}')
    except Exception:
        logger.exception(f'update_partner_registration save Exception {id}')

    return id

# =========================
# 登録番号抽出
# =========================
def extract_invoice_number(text: str):
    """
    T + 13桁の登録番号を抽出
    """
    match = re.search(r'T\d{13}', text)
    return match.group(0) if match else None
# =========================
# 登録番号で取引先検索
# =========================
def find_by_reg_no(owner_id, corporate_number):
    partnerobj = MtPartner.objects.filter(owner_id=owner_id, corporate_number=corporate_number).exclude(delete_flg=1).first()
    return partnerobj
    # try:
    #     # 「get」で条件に合ったオブジェクトが複数個存在する場合、MultipleObjectsReturnedという例外が発生
    #     return MtPartner.objects.get(corporate_number=corporate_number)
    # except MtPartner.DoesNotExist:
    #     return None

# =========================
# 国税庁データをDB化し検索
# =========================
def get_company_name(reg_number):
    return None
    # from app.models import Company
    # try:
    #     company = Company.objects.get(registration_number=reg_number)
    #     return company.name
    # except:
    #     return None

# ############################################
#
#
# ############################################
def detect_company(text, items):
    # text, items = parse_vision_response(response)
    # 抽出
    result = extract_parties(text, items)
    return result

# Vision APIの座標付き取得
def parse_vision_response(response):
    items = []
    full_text = response.full_text_annotation.text

    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                text = ''
                for word in paragraph.words:
                    text += ''.join([s.text for s in word.symbols])

                box = paragraph.bounding_box.vertices

                items.append({
                    'text': text,
                    'x': box[0].x,
                    'y': box[0].y
                })

    return full_text, items

# =========================
# ④ メイン処理
# =========================
def extract_parties(text, items):
    # result = {
    #     'issuer': None,
    #     'method': None,
    #     'reg_no': None
    # }
    # 1. 登録番号チェック
    reg_no = extract_invoice_number(text)
    if reg_no:
      # T・ハイフン・スペースを除去して数字のみにする
      corporate_number = re.sub(r'[^0-9]', '', reg_no)

    issuer = None
    method = None

    # ① 発行元確定
    if corporate_number:
        # 発行元（登録番号ベース）        
        issuer = fetch_company_name_from_invoice_api(corporate_number)
        issuer_method = 'invoice_api'

    if not issuer:
        # 2. OCRテキストから推定
        issuer,issuer_method = extract_issuer_from_text(items)

    # ② 候補抽出
    candidates = extract_company_candidates(items)

    # ③ 発行元除外
    if issuer:
        candidates = [c for c in candidates if issuer not in c]

    # ④ 得意先スコアリング
    scored = [(c, score_customer(c)) for c in candidates]

    scored.sort(key=lambda x: x[1], reverse=True)

    customer = scored[0][0] if scored and scored[0][1] > 0 else None

    return {
        'issuer': issuer,
        'issuer_method': issuer_method,
        'customer': customer,
        'corporate_number': corporate_number,
        'candidates': scored  # デバッグ用
    }

# =========================
# ③ 発行元抽出（ルールベース）
# =========================
def extract_issuer_from_text(lines) -> tuple[str | None, str | None]:
    """
    OCRテキストから発行元候補を抽出
    """
    # lines = [line.strip() for line in text.split('\n') if line.strip()]

    # 優先キーワード
    keywords = [
        '株式会社', '有限会社', '合同会社',
        'Inc.', 'Ltd.', 'Co.,', 'Company'
    ]

    # for line in lines[:15]:  # 上部にあることが多い
    for line in lines:
        if any(k in line for k in keywords):
            return line, 'rule_based'

    # fallback：一番上の行
    # return (lines[0] if lines else None), 'fallback'
    return None, 'fallback'

# =========================
# 得意先抽出
# 会社名候補抽出
# =========================
# def extract_company_candidates(lines):
#     # lines = [l.strip() for l in text.split('\n') if l.strip()]

#     keywords = ['株式会社', '有限会社', '合同会社']
#     exclude_keywords = [
#         '発行', '請求元', '販売元'
#     ]
#     candidates = []

#     for line in lines:
#         if any(k in line for k in keywords):
#             if not any(e in line for e in exclude_keywords):
#                 candidates.append(line)

#     return candidates

def extract_company_candidates(items):
    pattern = re.compile(r'(株式会社|有限会社|合同会社|\(株\)|㈱)')

    results = []

    for item in items:
        text = item#['text']

        # OCR誤認識対策（簡易）
        text_norm = (
            text.replace('会杜', '会社')
                .replace('株式会', '株式会社')
        )

        if pattern.search(text_norm):
            # item['text'] = text_norm
            # results.append(item)
            results.append(text_norm)

    return results
# =========================
# 得意先判定スコア
# =========================
def score_customer(line: str):
    score = 0

    if '御中' in line:
        score += 5
    if '様' in line:
        score += 3
    if '殿' in line:
        score += 3
    # # 右側にある
    # if x > width * 0.5:
    #     score += 3
    # # 上部にある
    # if y < height * 0.4:
    #     score += 2

    # 減点（よくあるノイズ）
    if '銀行' in line:
        score -= 5
    if '支店' in line:
        score -= 3
    if '発行' in line:
        score -= 3
    if '登録番号' in line:
        score -= 5

    return score

# 正規化
def normalize(name: str):
    return (
        name.replace('株式会社', '')
            .replace('(株)', '')
            .replace(' ', '')
            .lower()
    )


