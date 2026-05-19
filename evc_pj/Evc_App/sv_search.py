import datetime
import re   # 正規表現操作
import logging
from django.db.models import Q  # 条件を一つでも満たすものを取得する場合Q objectsと|を使う

from commons.utils import ut_get_localtoday
from Evc_App.sv_file import (SearchKey,
    sv_get_category_list,
    sv_get_textlines,sv_get_textdatas_area,sv_get_textlines_lf,
)
# from Evc_App.sv_extract_text import remove_all_whitespace
from Evc_App.sv_search_company import detect_partner

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
        textdatalist = sv_get_textdatas_area(textdatas, -1, area_no)

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
        partner_id, publisher_id = detect_partner(user_id, owner_id, textdatalist, texts, evidence_id)

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
                        year = ut_get_localtoday().year
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

