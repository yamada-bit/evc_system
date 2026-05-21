# import os
import datetime
# import math
import hashlib
import calendar
import logging

# import base64
# パスワードを生成
import secrets
import string
# import shutil
# import subprocess
# import chardet

# from Crypto.Cipher import AES
# from Crypto.Util.Padding import pad
# from Crypto.Util.Padding import unpad
# from Crypto.Random import get_random_bytes

from django.utils import timezone
from django.utils.timezone import make_aware
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN

logger = logging.getLogger(__name__)

def ut_get_client_ip(request):
    forwarded_addr = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_addr:
        # 'HTTP_X_FORWARDED_FOR'ヘッダがある場合: 転送経路の先頭要素を取得
        client_addr = forwarded_addr.split(',')[0]
    else:
        # 'HTTP_X_FORWARDED_FOR'ヘッダがない場合: 直接接続なので'REMOTE_ADDR'ヘッダを参照
        client_addr = request.META.get('REMOTE_ADDR','')
    return 'IP:' + client_addr

def print_e(e):
    if settings.DEBUG:
        print(e)
    else:
        pass

# ハッシュ値を使ってログ出力(ユーザIDはハッシュ値で)
def ut_get_hash(dat):
    if dat:
        hs = hashlib.md5(dat.encode()).hexdigest()
    else:
        hs = 'None'
    return hs

# timezone付き（aware）
# DB保存で使用
# datetime.datetime.now()    # タイムゾーン情報を持たない（Naive）
# datetime.datetime(2026, 5, 15, 15, 0, 0)
# timezone.now()   # timezone付き（aware）通常UTC
# datetime.datetime(2026, 5, 15, 6, 0, 0, tzinfo=datetime.timezone.utc)
def ut_get_timezone_now():
    # return datetime.datetime.now()    # タイムゾーン情報を持たない（Naive）
    return timezone.now()   # timezone付き（aware）通常UTC

# ローカルタイムゾーン（現地時間）の日時(JST)
# datetime.datetime(2026, 5, 15, 15, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='Asia/Tokyo')
def ut_get_localtime():
    return timezone.localtime()

# ローカルの日付を取得 
def ut_get_localtoday():
    return timezone.localdate()

# NativeをJSTのdatetimeに変換(9時間ずれるため調整)
def ut_get_localdate(date):
    localdate = None
    if date:
        try:
            # Djangoでは、PostgreSQLだとdatetimeFieldはDB上ではtimestamp with time zoneとなり、
            # タイムゾーンはUTC
            # 9時間ずれるため調整
            # date_utc = make_aware(date, timezone=datetime.timezone.utc)
            # localdate = timezone.localtime(date_utc)
            if timezone.is_naive(date): # 渡された日時が Naive だったら Aware に変換する
                date = timezone.make_aware(date, datetime.timezone.utc)
            localdate = timezone.localtime(date)
        except Exception:
            logger.exception(f'ut_get_localdate exception {date=}')
    return localdate

# 月初日付の取得
def ut_get_beginofmonth(shori_date):
    try:
        if '/' in shori_date:
            bom = datetime.datetime.strptime(shori_date + '/01','%Y/%m/%d')
        elif '-' in shori_date:
            bom = datetime.datetime.strptime(shori_date + '-01','%Y-%m-%d')
        else:
            bom = datetime.datetime.strptime(shori_date + '01','%Y%m%d')
    # bom = datetime.datetime.strptime(shori_date,'%Y-%m-%d')
    # bom = bom.replace(day=1)
    except Exception:
        logger.exception(f'ut_get_beginofmonth exception {shori_date}')
        return False
    return bom
# 月末日付の取得
def ut_get_endofmonth(dt):
    try:
        eom = dt.replace(day=calendar.monthrange(dt.year, dt.month)[1])
    except Exception:
        logger.exception(f'ut_get_endofmonth exception {dt}')
        return False
    return eom

def ut_get_random_password_string(length):
    # pass_chars = string.ascii_letters + string.digits
    pass_chars = string.ascii_lowercase + string.digits
    # pass_chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    password = ''.join(secrets.choice(pass_chars) for i in range(length))
    # print("Random string of length", length, "is:", password)

    return password

# # fileの文字コードを判定する
# def ut_get_encoding_type(file):
#     # バイナリモードでファイルを開いて読み込む
#     with open(file, 'rb') as f:
#         raw_data = f.read()
#     encoding = chardet.detect(raw_data)
#     return encoding

# CSV読み込みで'null'文字列をNoneにする
def null2none(str):
    if str == 'null':
        str = None
    if not str:
        str = None
    return str

def is_integer(n):
    try:
        float(n)
    except ValueError:
        return False
    else:
        return float(n).is_integer()

def str2int(str):
    if not str:
        return 0
    d = 0
    try:
        str = str.replace(',','').replace('"','')
        d = int(str)
    except Exception as e:
        print_e(e)
    return d
# 空白は０に
def str2decimal(str):
    d = Decimal(0)
    if not str or str == '-':
        return d
    try:
        str = str.replace(',','').replace('"','')
        d = Decimal(str)
    except Exception as e:
        print_e(e)
    return d
# 空白は[null]に(null=Trueが設定された項目)
# 空白はdefault値に
def str2decimal_none(str, value=None):
    d = value
    if not str or str == '-':
        return d
    try:
        str = str.replace(',','').replace('"','')
        d = Decimal(str)
    except Exception as e:
        print_e(e)
    return d

# hh:mm
def str2time(str):
    try:
        hour, minute = map(int, str.split(':'))
        hm_time = datetime.time(hour, minute, 0)
    except Exception as e:
        print_e(e)
        hm_time = None
    return hm_time
# yyyy/mm yyyy/mm/dd yyyy-mm yyyy-mm-dd
def str2date(str):
    ymd_date = None
    try:
        ymd = str.split('/')
        if len(ymd) == 2:
            ymd_date = datetime.datetime(int(ymd[0]), int(ymd[1]), 1).date()
        elif len(ymd) == 3:
            ymd_date = datetime.datetime.strptime(str, '%Y/%m/%d').date()
        else:
            ymd = str.split('-')
            if len(ymd) == 2:
                ymd_date = datetime.datetime(int(ymd[0]), int(ymd[1]), 1).date()
            elif len(ymd) == 3:
                ymd_date = datetime.datetime(int(ymd[0]), int(ymd[1]), int(ymd[2])).date()
    except Exception as e:
        print_e(e)
    return ymd_date
# yyyy/mm
def date2monthstr(date):
    str = ''
    try:
        str = date.strftime('%Y/%#m') # 先頭の0や空白を削除するために#を指定
    except Exception as e:
        print_e(e)
    return str

# Decimal('0E-10'):0.0000000000 を 0 にする
# 指数部や末尾のゼロを取り除く
def decimal_zeros(decimal_val):
    if decimal_val == 0:
        return '0'
    else:
        try:
            # d = '{0:f}'.format(decimal_val) # 指数表記を小数表記
            d = remove_exponent(decimal_val)
            return str(d)
        except Exception as e:
            print_e(e)
            return ''
        # s = str(decimal_val)
        # return s
# 指数部や末尾のゼロを取り除き、有効数字を忘れ、しかし値を変えずにおく
# docs.python.org/3.10/library/decimal.html#decimal-faq
# Python ドキュメント 10進数の固定小数点と浮動小数点の算術演算 10進数FAQ
def remove_exponent(d):
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
# 数値fの小数点以下を正規化し、文字列で返す
def decimal_normalize(decimal_val):
    # 数値を正規化 (normalize) して、右端に連続しているゼロを除去
    d = Decimal.normalize(decimal_val)
    b = remove_exponent(d)
    return str(b)

# カンマ区切り文字列に変換する
def decimal2comma(d):
    if not d:
        return '0'
    str = '{:,}'.format(d)
    return str

# 文字列に変換する
def get_tco2_str(tco2):
    if not tco2:
        return '0'
    return str(tco2)
# 小数点以下3桁目を四捨五入し、2桁目までを取得する
def round_tco2_2(tco2):
    if not tco2:
        return 0
    try:
        tco2 = tco2.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception as e:
        tco2 = 0
        print_e(e)
    return tco2
# 小数点以下を四捨五入
def round_tco2_0(tco2):
    if not tco2:
        return 0
    try:
        # tco2 = math.ceil(tco2)
        tco2 = int(tco2.quantize(Decimal('1.'), rounding=ROUND_HALF_UP))
    except Exception as e:
        tco2 = 0
        print_e(e)
    return tco2
# 小数点以下2桁目を四捨五入し、1桁目までを取得する
def round_tco2_1(tco2):
    if not tco2:
        return 0
    try:
        tco2 = tco2.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    except Exception as e:
        tco2 = 0
        print_e(e)
    return tco2
# 小数点以下2桁目を四捨五入し、1桁目までの文字列を取得する
def round_tco2_1_str(tco2):
    if not tco2:
        return '0'
    try:
        tco2 = tco2.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    except Exception as e:
        tco2 = 0
        print_e(e)
    return str(tco2)
# ログインした年月から換算して11月前から1年
def get_period():
    today = ut_get_localtoday()
    if today.month == 12:
        lastyear =  datetime.datetime(today.year, 1, 1)
    else:
        lastyear =  datetime.datetime(today.year - 1, today.month + 1, 1)
    return lastyear,today


# # AES_KEYをsettingsから読み込みエンコード
# # AES_KEY = settings.AES_KEY.encode('utf-8')
# AES_KEY = b"cZERo135642Monsc" 
# def aes_encryption(data):
#   """
#   AESによる暗号化を行う
#   """
#   # ランダムの初期化ベクトルの生成
#   iv = get_random_bytes(AES.block_size)
#   # 受け取ったデータをエンコード
#   data = data.encode('utf-8')
#   cipher = AES.new(key=AES_KEY, mode=AES.MODE_CBC, iv=iv)
#   # 暗号化(パディングする)
#   encrypted_data = cipher.encrypt(pad(data, AES.block_size))
#   db_data = base64.b64encode(iv + encrypted_data).decode('utf-8')
#   return db_data

# def aes_decryption(data):
#   """
#   AESによる復号化を行う
#   """
#   # dbから読み込んだデータのエンコード
#   data = base64.b64decode(data.encode('utf-8'))
#   # 初期化ベクトル+暗号化されたデータをそれぞれに分割
#   iv = data[:AES.block_size]
#   encrypted_data = data[AES.block_size:]
#   # 復号
#   cipher = AES.new(AES_KEY, AES.MODE_CBC, iv = iv)
#   unencrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
#   # デコード
#   unencrypted_data = unencrypted_data.decode('utf-8')
#   return unencrypted_data

