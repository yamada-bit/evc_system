import datetime
import re   # 正規表現操作
import logging
from django.db.models import Q  # 条件を一つでも満たすものを取得する場合Q objectsと|を使う

from Evc_App.sv_file import (SearchKey,
    sv_get_category_list,sv_get_partner_id,sv_get_publisher_id,sv_get_partner_ryaku_list,
    sv_get_partner_name,sv_get_partner_ryaku_name,sv_conv_company,sv_get_user_authority,
    sv_get_textlines,sv_get_textdatalist,sv_get_textlines_lf,sv_save_detect
)
# from Evc_App.sv_extract_text import remove_all_whitespace
from users.models import MtPhrase

logger = logging.getLogger(__name__)

# 文字列(TextDatasのリスト)からキー情報を抽出（ページごと)
def sv_search_text(textdatas, user_id, owner_id, area_no, evidence_id):
    if not textdatas:
        logger.error(f'textdatas False {owner_id=}')
        search = SearchKey('その他', None, None, None, None)
        return search
    try:
        # 行単位でTextData.textを連結した文字列のリストを取得(カテゴリ・日付の取得)
        textlines = sv_get_textlines(textdatas, -1, area_no)
        # 行単位でTextData.textをLFで連結した文字列のリストを取得(金額の取得)
        # 同じ行に複数の数値がある場合にLFで区切ることで対処
        textlines_lf = sv_get_textlines_lf(textdatas, -1, area_no)
        # 取引先名以外の文字列が連結しないように
        # TextDataごとの文字列のリストを取得(取引先名の取得)
        textdatalist = sv_get_textdatalist(textdatas, -1, area_no)

        texts = ''.join(textlines)  # 全文データを作成
        # 改行、タブ、スペースなどをまとめて削除 
        # \s --> [\t\n\r\f\v] 	任意の空白文字
        texts = re.sub(r'\s+', '', texts)   # remove_all_whitespace(texts)
        # pattern_dict = {}

        # pattern_dict['date'] = r'[12]\d{3}[/\-年](1[0-2]|0?[1-9])[/\-月]([12][0-9]|3[01]|0?[1-9])日?'
        # pattern_dict['time'] = r'((0?|1)[0-9]|2[0-3])[:時][0-5][0-9]分?'
        # pattern_dict['tel'] = '0\d{1,3}-\d{1,4}-\d{4}'
        # pattern_dict['total_price'] = r'合計¥(0|[1-9]\d*|[1-9]\d{0,2}(,\d{3})+)'
        # pattern_dict['total_price2'] = r'(0|[1-9]\d*|[1-9]\d{0,2}(,\d{3})+)JPY'
        # pattern_dict['category'] = r'契約書|見積書|注文書|注文請書|請求書|領収書'
        # for key, pattern in pattern_dict.items():
        #     matched_string = get_matched_string(pattern, texts)
        #     if matched_string:
        #         print(key, matched_string)
    # tel 03-1234-5678
    # date 2022年10月01日
    # time 08:45
    # total_price 合計¥1,234

        # カテゴリの検索
        category_name = get_matched_category(owner_id, texts)
        logger.debug(f'{category_name=}')
        # 日付の検索
        # processed_date = get_matched_date(texts)
        processed_date = extract_date(textlines_lf) # 妥当性チェック
        logger.debug(f'{processed_date=}')

        # credit = get_creditcard(texts)
        # logger.info('credit  : ' + credit if credit else 'false')

        # 取引先を検索
        partner_id, publisher_id = get_matched_partner_id(user_id, owner_id, textdatalist, texts, evidence_id)

        # 金額を検索
        total_amount = get_matched_amount(textlines_lf)
        logger.debug(f'{total_amount=}')

        search = SearchKey(category_name, processed_date, partner_id, publisher_id, total_amount)
    except Exception:
        logger.exception(f'sv_search_text exception {owner_id=}')
        search = SearchKey('その他', None, None, None, None)

    return search
# 文字列検索
def get_matched_string(pattern, string):
    try:
        regex = re.compile(pattern)  # 正規表現パターンをコンパイル
        result = regex.search(string)
        if result:
            return result.group()   # マッチした部分を文字列として取得(最初のパターンのみ)
        else:
            return False
    except Exception:
        logger.exception(f'get_matched_string exception {pattern=}')
        return False
        
# カテゴリ検索(フォルダ管理マスタ)
def get_matched_category(owner_id, string):
    categorys = sv_get_category_list(owner_id)
    lists = []
    for list in categorys:
        if list != 'その他':
            lists.append(list)
        # if list == 'その他':
        #     lists.append(list)
    # カテゴリリストに領収書があり領収証がなければ領収証は領収書で処理
    if '領収書' in lists:
        if '領収証' not in lists:
            lists.append('領収証')
    pattern_category = '|'.join(lists)
    matched_string = get_matched_string(pattern_category, string)
    if matched_string:
        if matched_string == '領収証':
            matched_string = '領収書'
        # if matched_string == '注文請書':
        #     matched_string = '注文書'
        category_name = matched_string
    else:
        # category_name = 'その他'
        category_name = get_matched_category_text(string)
        # category_name = get_matched_phrase(owner_id, string)
    return category_name

# フレーズマスタの文字列で検索
def get_matched_phrase(owner_id, string):
    pattern = ''
    # lists = MtPhrase.objects.filter(owner_id=owner_id).exclude(delete_flg=1).values('phrase_id', 'phrase', 'category_name').order_by('phrase')
    # lists = MtPhrase.objects.filter(owner_id=owner_id).values('phrase_id', 'phrase', 'category_name').order_by('phrase_id')
    lists = MtPhrase.objects.filter(Q(owner_id__isnull=True)|Q(owner_id=owner_id)).values('phrase_id','phrase','category_name').order_by('phrase_id')
    for item in lists:
        # phrase_id = item.get('phrase_id')
        phrase = item.get('phrase')
        if phrase:
            phrase = re.sub(r'\s+', '', phrase) # 空白は除去
            phrase = re.escape(phrase)    # すべての正規表現用特殊文字をエスケープ
            if pattern:
                pattern += '|' + phrase
            else:
                pattern = phrase
    matched_string = get_matched_string(pattern, string)
    category_name = 'その他'
    if matched_string:
        for item in lists:
            phrase = item.get('phrase')
            if phrase == matched_string:
                category_name = item.get('category_name')
                break
    logger.debug(f'{category_name=}')
    return category_name

# カテゴリ検索(文言)
def get_matched_category_text(string):
    lists = ['領収いたしました',
            #  '領収致しました']
             '領収致しました','領収']

    # lists = ['正に領収いたしました','正に領収致しました','たしかに頂きました','たしかに受け取りました']
    pattern_category = '|'.join(lists)
    matched_string = get_matched_string(pattern_category, string)
    if matched_string:
        category_name = '領収書'
    else:
        category_name = 'その他'
    logger.debug(f'{category_name=}')
    return category_name

# 年月日文字列検索
def get_matched_date(string):
# 正規表現パターンの一部をカッコ”（）”を使ってグルーピング
    # pattern = r'([12]\d{3})[/\-年](1[0-2]|0?[1-9])[/\-月]([12][0-9]|3[01]|0?[1-9])日?'
    # result = re.search(pattern, string)
    # if result:
    #     try:
    #         y = int(result.group(1))
    #         m = int(result.group(2))
    #         d = int(result.group(3))
    #         return datetime.date(y, m, d) #.strftime('%y-%m-%d')
    #     except Exception:
    #         pass
    # return None
    # 和暦対応
    pattern_dict = {}
    pattern_dict['date'] = r'([12]\d{3})[/\-年](1[0-2]|0?[1-9])[/\-月]([12][0-9]|3[01]|0?[1-9])日?'
    # pattern_dict['date2'] = r"('|昭和|昭|平成|平|令和|令|S|s|H|h|R|r)(\d{1,2})年(0?[1-9]|1[0-2])月(0?[1-9]|[12][0-9]|3[01])日"
    pattern_dict['date2'] = r"('|令和|令|R|r)(\d{1,2})年(0?[1-9]|1[0-2])月(0?[1-9]|[12][0-9]|3[01])日"

    for key, pattern in pattern_dict.items():
        result = re.search(pattern, string)
        if result:
            try:
                if key == 'date':
                    y = int(result.group(1))
                    m = int(result.group(2))
                    d = int(result.group(3))
                    return datetime.date(y, m, d) #.strftime('%y-%m-%d')
                elif key == 'date2':
                    j = result.group(1)
                    y = int(result.group(2))
                    if j == "'":
                        y += 2000
                    elif j == '昭和' or j == '昭' or j == 'S' or j == 's':
                        y += 1925
                    elif j == '平成' or j == '平' or j == 'H' or j == 'h':
                        y += 1988
                    elif j == '令和' or j == '令' or j == 'R' or j == 'r':
                        y += 2018
                    else:
                        y += 2018
                    m = int(result.group(3))
                    d = int(result.group(4))
                    return datetime.date(y, m, d) #.strftime('%y-%m-%d')
            except Exception:
                logger.exception(f'get_matched_date exception {string=}')
    return None
# 日付データを取得（妥当性チェック）
def extract_date(lines):
    pattern_dict = {}
    # pattern_dict['date'] = r'([12]\d{3})[/\-年](1[0-2]|0?[1-9])[/\-月]([12][0-9]|3[01]|0?[1-9])日?'
    pattern_dict['date'] = r'([12]\d{3})[/年](1[0-2]|0?[1-9])[/月]([12][0-9]|3[01]|0?[1-9])日?'
    # pattern_dict['date2'] = r"('|昭和|昭|平成|平|令和|令|S|s|H|h|R|r)(\d{1,2})年(0?[1-9]|1[0-2])月(0?[1-9]|[12][0-9]|3[01])日"
    pattern_dict['date2'] = r"('|令和|令|R|r)(\d{1,2})[年](0?[1-9]|1[0-2])[月]([12][0-9]|3[01]|0?[1-9])日?"
    pattern_dict['date3'] = r'([12]\d{3})[\-\.](1[0-2]|0?[1-9])[\-\.]([12][0-9]|3[01]|0?[1-9])' # yyyy.mm.dd
    pattern_dict['date4'] = r'(\d{2})[/年\.](1[0-2]|0?[1-9])[/月\.]([12][0-9]|3[01]|0?[1-9])日?'    # yy.mm.dd
    pattern_dict['date5'] = r'([1-9])[/年\.](1[0-2]|0?[1-9])[/月\.]([12][0-9]|3[01]|0?[1-9])日?'    # y.mm.dd
    # マッチさせる順番（OR結合は左からマッチさせるので2023/12/23より先に2023/12/2にマッチするのを防ぐように）

    for key, pattern in pattern_dict.items():
        for line in lines:
            try:
                # line2 = re.sub(r'\s+', '', line)   # 空白・改行・タブ remove_all_whitespace(texts)
                line2 = re.sub('[\u3000 \t]', '', line) # 空白・タブ
                result = re.search(pattern, line2)
                if result:
                    line3 = re.sub(r'\s+', '', line)
                    if key == 'date':
                        y = int(result.group(1))
                        m = int(result.group(2))
                        d = int(result.group(3))
                        logger.debug(f'date matched text {line3}')
                        return datetime.date(y, m, d) #.strftime('%y-%m-%d')
                    elif key == 'date2':
                        j = result.group(1)
                        y = int(result.group(2))
                        if j == "'":
                            y += 2000
                        elif j == '昭和' or j == '昭' or j == 'S' or j == 's':
                            y += 1925
                        elif j == '平成' or j == '平' or j == 'H' or j == 'h':
                            y += 1988
                        elif j == '令和' or j == '令' or j == 'R' or j == 'r':
                            y += 2018
                        else:
                            y += 2018
                        m = int(result.group(3))
                        d = int(result.group(4))
                        logger.debug(f'date matched text 2 {line3}')
                        return datetime.date(y, m, d)
                    elif key == 'date3':    # yyyy.mm.dd
                        y = int(result.group(1))
                        m = int(result.group(2))
                        d = int(result.group(3))
                        # 00610101 23年11月14日 など空白対処のためlineでチェック
                        if check_date(y, m, d, line, result.group()):
                            logger.debug(f'date matched text 3 {line3}')
                            return datetime.date(y, m, d)
                    elif key == 'date4':    # yy.mm.dd
                        y = int(result.group(1))
                        year = datetime.date.today().year
                        if abs(2018 + y - year) < abs(2000 + y - year):
                            y += 2018
                        else:
                            y += 2000
                        m = int(result.group(2))
                        d = int(result.group(3))
                        # 00610101 23年11月14日 などの空白対処のためlineでチェック
                        if check_date(y, m, d, line, result.group()):
                            logger.debug(f'date matched text 4 {line3}')
                            return datetime.date(y, m, d)
                        # if check_date(y, m, d, line2, result.group()):
                        #     # 分割_image_67144193 (2/2) 様 25 年 4月20日 などのスペースがある場合の対処
                        #     logger.debug('date matched text 4: ' + line)
                        #     return datetime.date(y, m, d)
                    elif key == 'date5':    # y.mm.dd
                        y = int(result.group(1)) + 2018
                        m = int(result.group(2))
                        d = int(result.group(3))
                        if check_date(y, m, d, line, result.group()):
                            logger.debug(f'date matched text 5 {line3}')
                            return datetime.date(y, m, d)
                        # if check_date(y, m, d, line2, result.group()):
                        #     logger.debug('date matched text 5: ' + line)
                        #     return datetime.date(y, m, d)
            except Exception:
                logger.exception(f'extract_date exception {line=}')
    return None
# 日付の妥当性
# 1750-4-9と取得される01750-4-960146などをエラーに
def check_date(y, m, d, line, result):
    ymd = None
    try:
        if y < 2001 or 2100 < y:
            return None
        s = line.find(result)
        if s == -1:
            return None
        if 0 < s:
            if line[s-1].isdecimal():
                return None
        n = len(result)
        if s + n < len(line):
            if line[s + n].isdecimal():
                return None
        ymd = datetime.date(y, m, d)
    except Exception:
        logger.exception(f'check_date exception {line=}')
    return ymd    
# クレジット決済を判定のため
def get_creditcard(string):
    pattern = r'クレジットカード|クレジット支払'
    regex = re.compile(pattern)  # 正規表現パターンをコンパイル
    result = regex.search(string)
    if result:
        return result.group()   # マッチした部分を文字列として取得(最初のパターンのみ)
    else:
        return False
# 合計金額検索
def get_matched_amount(lines):
    # 先頭に合計がある値
    # matched_string = get_matched_price(lines)

    # if matched_string:
    #     total_amount = re.sub(r'\D', '', matched_string)
    #     logger.debug('get_matched_price  : ' + (total_amount or 'None'))
    #     return total_amount
    # 最大値を取得する
    # price = extract_price(lines)
    amount_dict = extract_amount_dict(lines, False)     # 円,円マークありのみ
    if not amount_dict:
        amount_dict = extract_amount_dict(lines, True)  # 円,円マークなしも検索 20221117110505.pdf
    price = False
    if amount_dict:
        price = max(amount_dict.values())
    else:
        price_list = get_price_list(lines)
        if price_list:
            price =  max(price_list)
    if price:
        if type(price) is str:
            total_amount = int(price)
        else:
            total_amount = price
    else:
        total_amount = None

    return total_amount
# 合計金額文字列検索(先頭に合計)
def get_matched_price(lines):
    # pattern = r'合計¥?(0|[1-9]\d*|[1-9]\d{0,2}(,\d{3})+)円?$'
    # pattern = r'合計¥?(0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)円?'
    pattern = r'^合計¥?(\d{1,3}(?:,\d{3})+|\d+)円?' # 先頭に合計(税抜合計など除外)
    # pattern = r'合計¥?(\d{1,3}(?:,\d{3})+|\d+)円?'
    for line in lines:
        # results = re.findall(pattern, line)
        # if results:
        #     for r in results:
        #         if r.startswith('合計'):
        #             return r
        result = re.search(pattern, line)
        if result:
            return result.group()
    return False

# 対象文字列に一致する金額データを取得
def extract_price(lines):
    pattern_dict = {}
    pattern_dict['invoice'] = r'請求金?額'
    pattern_dict['total'] = r'合計|買上げ?計|対象計'
    pattern_dict['other'] = r'金額|現計|決済|支払'

    price_list = []
    for key, pattern in pattern_dict.items():
        matched_list = get_matched_text_list(pattern, lines)
        if matched_list:
            for text in matched_list:
                try:
                    price = search_price(key, text)
                    if price:
                        price_list.append(price)
                        logger.debug('price : ' + re.sub(r'\s+', '', text) + '->' + str(price)) # LF削除
                    # return price
                except Exception:
                    continue
    if price_list:
        return max(price_list)
    return False

def get_matched_text_list(pattern, lines):
    matched_list = []
    try:
        for line in lines:
            m = re.search(pattern, line)
            if m:
                start, end = m.span()
                matched_list.append(line[start:])
                string = re.sub(r'\s+', '', line[start:])    # LF削除
                logger.debug(f'price matched text {string} {start}:{end}') # start <= x < end
    except Exception:
        logger.exception('get_matched_text_list exception')
    return matched_list

# 金額データを取得
def extract_amount_dict(lines, nonmark):
    pattern_dict = {}
    pattern_dict['amount'] = r'請求金?額|発注金?額|領収金?額|合計金?額|受領金?額'
    pattern_dict['total1'] = r'合計|買上げ?計|対象計'
    pattern_dict['total2'] = r'金額'
    # pattern_dict['total'] = r'合計|金額|買上げ?計|対象計'
    # pattern_dict['other'] = r'現計|決済|支払'
    # pattern_dict['total'] = r'合計|買上げ?計|対象計'
    # pattern_dict['other'] = r'金額|現計|決済|支払'

    # pattern_tupple = ('請求金額','請求額','合計','買上げ計','買上計','対象計','現計','決済','金額','支払')

    amount_dict = {}
    amount = 0
    for key, pattern in pattern_dict.items():
        if nonmark and key == 'total2': # 金額の行では円￥がある数値のみ
            break
        try:
            for i, line in enumerate(lines):
                result = re.search(pattern, line)
                if result:
                    start, end = result.span()
                    matched_pattern = line[start:end] # start <= x < end
                    # text = line[start:]
                    text = line # 左記の金額　に対処するため行の文字列全体　
                    amount = amount_dict.get(matched_pattern, 0)
                    if nonmark:
                        price = search_price(key, text) # 同じ行は円￥がない数値も金額に
                    else:
                        price = search_price('other', text) # 円￥がある数値のみを金額に
                    if price and amount < price:
                        amount_dict[matched_pattern] = price
                        logger.debug('price matched text ' + ('nonmark : ' if nonmark else ' : ') + matched_pattern)
                        logger.debug('price : ' + re.sub(r'\s+', '', text) + '->' + str(price)) # LF削除
                    # elif key == 'amount':   # 上下の行を検索
                    # elif key == 'amount' or key == 'total1':   # 上下の行を検索
                    elif not nonmark and key != 'total2':
                        # 上下の行で円￥がある数値：金額に
                        if 0 < i:
                            text2 = lines[i - 1]
                            price = search_price('other', text2)
                            if price and amount < price:
                                amount_dict[matched_pattern] = price
                                logger.debug('price matched text 上行 : ' + matched_pattern)
                                logger.debug('上行 price : ' + re.sub(r'\s+', '', text2) + '->' + str(price)) # LF削除
                        if not price and i < len(lines) - 1:
                            text2 = lines[i + 1]
                            price = search_price('other', text2)
                            if price and amount < price:
                                amount_dict[matched_pattern] = price
                                logger.debug('price matched text 下行 : ' + matched_pattern)
                                logger.debug('下行 price : ' + re.sub(r'\s+', '', text2) + '->' + str(price)) # LF削除
        except Exception:
            logger.exception('extract_amount_dict exception')
        # amount,total1で一致すれば終了
        if (key == 'amount' or key == 'total1') and amount_dict:
            break
    return amount_dict
# ピリオド＋3桁の数値をカンマ＋3桁の数値に
def rep_period(text):
    regex = re.compile(r'\.(\d{3})')    # 再利用したい部分を ()
    text = regex.sub(r',\1', text)      # 置換したい部分に1番目の再利用したい部分 
    # text = repr(text)   # エスケープシーケンスを無視（無効化）したraw文字列
    # text = text.replace('\\','¥')
    return text
# 金額の検索
def search_price(key, text):
    # pattern1 = r'¥?(0|[1-9]\d*|[1-9]\d{0,2}(,\d{3})+)円?$'
    # pattern = r'¥?(0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)円?'
    pattern_dict = {}
    if key == 'other':
        # r'現計|決済|金額|支払' の場合は, ¥で始まるか、円で終わる数値を対象にする
        # (?:パターン) キャプチャを行わないキャプチャグループ
        # pattern_dict['price1'] = r'c(\d{1,3}(?:,\d{3})+|\d+)'
        # pattern_dict['price2'] = r'(\d{1,3}(?:,\d{3})+|\d+)円'
        # pattern_dict['price1'] = r'¥\s*(\d{1,3}(?:(?:.|,)\d{3})+|\d+)' # .を,とみなす NG
        # pattern_dict['price2'] = r'(\d{1,3}(?:(?:.|,)\d{3})+|\d+)\s*円'
        pattern_dict['price1'] = r'¥\s*(\d{1,3}(?:,\d{3})+|\d+)'
        pattern_dict['price2'] = r'(\d{1,3}(?:,\d{3})+|\d+)\s*円'
        pattern_dict['price3'] = r'\\\s*(\d{1,3}(?:,\d{3})+|\d+)'   # ¥が\に置き換わる場合に対処
        pattern_dict['price4'] = r'(\d{1,3}(?:,\d{3})+|\d+)\s*JPY'
        text = rep_period(text)
    else:
        pattern_dict['price0'] = r'¥?(\d{1,3}(?:,\d{3})+|\d+)円?'
        text = rep_period(text)

    # pattern = r'¥?(\d{1,3}(?:,\d{3})+|\d+)円?'

    price_list = []
    for key, pattern in pattern_dict.items():
        results = re.findall(pattern, text)
        if results:
            for r in results:
                price = re.sub(r'\D', '', r)
                # 消費税など%の数値を除外
                idx = text.find(r)
                if idx != -1:
                    if idx + len(r) < len(text):
                        if text[idx + len(r)] == '%':
                            continue
                p = int(price)
                # if 999 < p and ',' not in r:
                #     continue
                if p < 1000000000000:
                    price_list.append(int(price))
                logger.debug(f'search_price {price=}')
    if price_list:
        return max(price_list)
    return False
    # result = re.search(pattern, text)
    # if result:
    #     matched_string = result.group()
    #     price = re.sub(r'\D', '', matched_string)
    #     return price
    # else:
    #     return False
# 文字列無しで金額のみを抽出
def get_price_list(lines):
    price_list = []
    try:
        for line in lines:
            price = search_price('other', line)
            if price:
                price_list.append(price)
                logger.debug('price : ' + re.sub(r'\s+', '', line) + '->' + str(price)) # LF削除
    except Exception:
        logger.exception('get_price_list exception')
    return price_list

# 取引先,発行元を検索
def get_matched_partner_id(user_id, owner_id, textdatalist, texts, evidence_id):
    partner_id = None
    publisher_id = None
    detect_partner_name = None
    detect_publisher_name = None
    matched_string = ''
    matched_partner = None
    matched_publisher = None
    # 取引先マスタから取引先名・取引先名（略称）のリストを取得
    lists = sv_get_partner_ryaku_list(owner_id)
    # 空白を除去する
    partner_ryaku_list = []
    for list in lists:
        # ('partner_id', 'partner_name', 'partner_ryaku_name')
        if list[1]:
            name1 = re.sub(r'\s+', '', list[1]) # 空白は除去
        else:
            name1 = ''
        if list[2]:
            name2 = re.sub(r'\s+', '', list[2]) # 空白は除去
        else:
            name2 = ''
        partner_ryaku_list.append((list[0], name1, name2))
    # TextDataごとに検索キーで取引先の抽出
    partner_list = get_matched_partner_name(partner_ryaku_list, textdatalist)
    # 1件目：取引先、2件目：発行元
    if partner_list:
        matched_partner = partner_list[0]
        name = sv_conv_company(partner_list[0])
        detect_partner_name = name
        # 抽出取引先名でID取得
        partner_id = sv_get_partner_id(name, owner_id)
        if not partner_id:
            # 抽出した名前(空白除去)で取引先マスタの取引先名・取引先名（略称）を検索してID取得
            partner_id = get_db_matched_partner_id(partner_ryaku_list, name)
        # if not partner_id:
        #     # auto_create = False if sv_get_user_authority(user_id) == '一般' else True
        #     auto_create = True
        #     if auto_create:
        #         # 取引先データがなければ取引先マスタ（MtPartner）データ作成
        #         partner_id = sv_get_partner_id(name, owner_id)
        if 1 < len(partner_list):   # 発行元名が抽出された場合
            matched_publisher = partner_list[1]
            name = sv_conv_company(partner_list[1])
            detect_publisher_name = name
            # 抽出発行元名でID取得
            publisher_id = sv_get_publisher_id(name, user_id)
            if not publisher_id:
                # 契約会社マスタで一致しない場合、取引先マスタで検索
                publisher_id = sv_get_partner_id(name, owner_id)
                if not publisher_id:
                    # 抽出した名前(空白除去)で取引先マスタの取引先名・取引先名（略称）を検索してID取得
                    publisher_id = get_db_matched_partner_id(partner_ryaku_list, name)
                # if not partner_id and publisher_id:
                #     partner_id = publisher_id
        # if not publisher_id:
        #     # 取引先を発行元にも設定
        #     publisher_id = partner_id
    else:
        # TextDataごとに取引先マスタの取引先名を検索
        partner_id,matched_partner = get_matched_partner_list(partner_ryaku_list, None, None, textdatalist)
    if (not publisher_id and not matched_publisher) and (partner_id or partner_list):
        # TextDataごとに取引先マスタの取引先名を検索(抽出した取引先を除外)
        publisher_id,matched_publisher = get_matched_partner_list(partner_ryaku_list, partner_id, matched_partner, textdatalist)
        # if not publisher_id:
        #     # 先頭一致で取引先マスタの取引先名を検索(最小文字数が必要)
        #     publisher_id = check_startswith_partner_list(partner_ryaku_list, name, textdatalist)
        if publisher_id and partner_list:
            # 検索キーを含む検索文字列（取引先として抽出されている）が後方にあり
            # 検索キーを含まない取引先マスタの取引先名での検索文字列(発行元)が前方にある
            # 検索処理の実行の順序で前方の文字列が発行元として抽出されている
            n1 = texts.find(matched_partner)
            n2 = texts.find(matched_publisher)
            if 0 <= n2 and n2 < n1:
                id = publisher_id
                publisher_id = partner_id
                detect_publisher_name = detect_partner_name
                partner_id = id
                detect_partner_name = None
        # else:    # 発行元未検出
        #     # 取引先を発行元にも設定
        #     publisher_id = partner_id
    logger.debug(f'{partner_id=}')
    logger.debug(f'{publisher_id=}')
    # 取引先データがなければ検出情報データ作成
    if (not partner_id and detect_partner_name) or (not publisher_id and detect_publisher_name):
        sv_save_detect(detect_partner_name, detect_publisher_name, user_id, evidence_id)

    return partner_id, publisher_id

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

    charcode = 'cp932' # 文字コード指定

    partner_list = []
    # test_list = [
    #   'マジックソフトウェア・ジャパン株式会社エン',
    #   '株式会社 システムブリッジ',
    #   'ANA X株式会社',
    #   '全日本空輸株式会社 All Nippon Airways Co.,Ltd'
    # ]
    # for text in test_list:
    for text in textdatalist:
        try:
            name = False
            text = extract_name(text)
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
                            # 検索キーの前後の文字列を取引先マスタでチェック
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
                # Ltd.がある場合、Ltd.の左側を抽出(スペースも含めて抽出)
                idx = text.find('Ltd.')
                if 0 < idx:
                    name = text[:idx + 4]
                    byte_text = name.encode() # 文字列エンコード
                    if 49 < len(byte_text):
                        logger.debug(f'name length > 49 : {name}')
                        name = name[-50:]
                else:
                    continue
            logger.debug(f'partner_name {name}')
            if partner_list:
                for list in partner_list:
                    if name != list:
                        partner_list.append(name)
                        # 2件で終了
                        return partner_list
            else:
                partner_list.append(name)
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
    matched_string = None
    for text in textdatalist:
        if not text:
            continue
        text = re.sub(r'\s+', '', text) # 空白は除去
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
                matched_string = text
                break
            if text == list[2]: # 取引先マスタの取引先名(略称)
                matched_partner_id = list[0]
                matched_string = text
                break
            if list[1]: # 検索キーを除外した取引先名で検索
                remove_key_name = remove_search_key(list[1])
                if text == remove_key_name:
                    matched_partner_id = list[0]
                    matched_string = text
                    break
            if list[2]:
                remove_key_name = remove_search_key(list[2])
                if text == remove_key_name:
                    matched_partner_id = list[0]
                    matched_string = text
                    break
    logger.debug(f'{matched_partner_id=} {matched_string=}')
    return matched_partner_id,matched_string
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
        for text in textdatalist:
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
