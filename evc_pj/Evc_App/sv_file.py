import dataclasses
import datetime
import logging
import os
from decimal import Decimal

from django.conf import settings
from sequences import get_next_value

from commons.utils import (
    ut_get_hash,
    ut_get_localdate,
    ut_get_localtoday,
    ut_get_timezone_now,
)
from users.models import EvcUser, MtAccount, MtFolder, MtPartner, SysOwner, TtDetect

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class UploadFile:
    id: str
    filename: str
    path: str
    flg: int
# OCRデータ
@dataclasses.dataclass
class DetectJson:
    page_no: int
    text: str
# OCRデータ一覧
@dataclasses.dataclass
class DetectJsons:
    filename: str
    pdfpath: str
    detect_list: list[DetectJson]

@dataclasses.dataclass
class TextData:
    x1: int
    y1: int
    x2: int
    y2: int
    text: str

@dataclasses.dataclass
class TextDatas:
    ocrtext_flg: int
    page_no: int
    area_no: int
    page_width: int
    page_height: int
    textdata_list: list[TextData]

# 全文検索データ
@dataclasses.dataclass
class FullText:
    page_no: int
    text: str
# 全文検索データ一覧
@dataclasses.dataclass
class FullTexts:
    filename: str
    pdfpath: str
    fulltext_list: list[FullText]

# 検索条件
@dataclasses.dataclass
class SearchKey:
    category_name: str | None
    processed_date: datetime.date | None
    partner_id: str | None
    publisher_id: str | None
    total_amount: int | None

# エビデンス情報
@dataclasses.dataclass
class EvidenceInfo:
    evidence_id: str
    owner_id: str
    pdf_name: str
    processed_ym: str
    pdf_handbook: str
    tran_detail: str
    file_path: str
    google_amount: int

# アップロードされたファイルを保存するパス
def sv_get_filepath(filename, rootfolder):
    abs_path = os.path.join(rootfolder, 'upload', filename).replace(os.sep,'/')
    if os.path.exists(os.path.dirname(abs_path)):
        pass
    else:
        logger.error(f'{abs_path} not exist!')
        abs_path = False
    return abs_path

# アップロードされたファイルをハンドルする
# ファイルを chunk_size に指定したサイズのチャンク ('chunk') づつ繰り返して読み出します。
# chunk_size のデフォルトサイズは 64KB です
def sv_handle_uploaded_file(f, name, rootfolder):
    path = sv_get_filepath(name, rootfolder)
    if path:
        try:
            chunk_size = 1024 * 1024
            with open(path, 'wb+') as destination:
                for chunk in f.chunks(chunk_size=chunk_size):
                    destination.write(chunk)
            logger.info(f'sv_handle_uploaded_file {path}')
        except Exception:
            path = False
            logger.exception(f'file write exception {name}')
    return path

def sv_delete_file(file):
    if file:
        try:
            if os.path.exists(file):
                os.remove(file)
        except Exception:
            logger.exception(f'sv_delete_file exception {file=}')

# 契約会社マスタ(sys_owner)からルートフォルダを取得
def get_rootfolder(owner_id):
    if owner_id:
        try:
            rootfolder = SysOwner.objects.get(owner_id=owner_id).root_folder
        except SysOwner.DoesNotExist:
            rootfolder = ''
            logger.exception(f'SysOwner DoesNotExist {owner_id=}')
    else:
        rootfolder = ''
        logger.error('get_rootfolder owner_id False')
    return rootfolder

# フォルダがなければ作成
def make_dir(path):
    if path:
        if not os.path.isdir(path):
            os.makedirs(path)   # 再帰的にディレクトリを作成する
            logger.debug(f'makedirs {path=}')

# アップロードファイル格納のためのフォルダ作成
def make_upload_dir(rootfolder):
    upload_path = os.path.join(rootfolder, 'upload').replace(os.sep,'/')
    make_dir(upload_path)   # rootfolderも作成する
    img_path = os.path.join(upload_path, 'img').replace(os.sep,'/')
    make_dir(img_path)
    json_path = os.path.join(upload_path, 'json').replace(os.sep,'/')
    make_dir(json_path)

# エビデンス画像ファイルを保存するフォルダ作成
def make_evidence_image_dir(rootfolder):
    json_path = os.path.join(rootfolder, 'evidence_image').replace(os.sep,'/')
    make_dir(json_path)
    try:
        today = ut_get_localtoday()
        yy = today.strftime('%Y')
        yy_dir = os.path.join(rootfolder, yy).replace(os.sep,'/')
        make_dir(yy_dir)
        for i in range(1,13):
            mm = f'{i:02d}'
            mm_dir = os.path.join(yy_dir, mm).replace(os.sep,'/')
            make_dir(mm_dir)
            img_dir = os.path.join(mm_dir, 'img').replace(os.sep,'/')
            make_dir(img_dir)
    except Exception:
        logger.exception(f'make_evidence_image_dir exception {rootfolder=}')
        return False
    return True

# jsonファイルを保存するフォルダ作成
def make_json_dir(rootfolder):
    json_path = os.path.join(rootfolder, 'json').replace(os.sep,'/')
    make_dir(json_path)

# カテゴリ別にファイルを保存するフォルダ作成
# def make_category_dir(owner_id):
#     try:
#         categorys = MtFolder.objects.filter(owner_id=owner_id)
#         if categorys:
#             for category in categorys:
#                 make_dir(category.folder_path)
#     except Exception:
#         logger.exception('MtFolder exception owner_id: ' + (owner_id or 'None'))
#     # カテゴリが一致しない場合にothersに保存するため作成
#     rootfolder = get_rootfolder(owner_id)
#     if rootfolder:
#         dest_dir = os.path.join(rootfolder, 'others').replace(os.sep,'/')
#         make_dir(dest_dir)

# 年月別にファイルを保存するフォルダ作成
def make_processed_ym_dir(rootfolder):
    try:
        today = ut_get_localtoday()
        yy = today.strftime('%Y')
        yy_dir = os.path.join(rootfolder, yy).replace(os.sep,'/')
        make_dir(yy_dir)
        for i in range(1,13):
            mm = f'{i:02d}'
            mm_dir = os.path.join(yy_dir, mm).replace(os.sep,'/')
            make_dir(mm_dir)
    except Exception:
        logger.exception(f'make_processed_ym_dir exception {rootfolder=}')
        return False
    return True

def get_imgfolder(rootfolder):
    abs_path = os.path.join(rootfolder, 'img').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''
# アップロード画像ファイル格納
def get_imgfolder_upload(rootfolder):
    abs_path = os.path.join(rootfolder, 'upload', 'img').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''

def get_evidence_image_dir(rootfolder):
    abs_path = os.path.join(rootfolder, 'evidence_image').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''

# webで画像を表示するために /media/ 配下
def get_media_image_dir():
    img_dir = getattr(settings, 'MEDIA_ROOT') / 'img'
    # img_dir = getattr(settings, 'MEDIA_ROOT').parent.parent / 'media/img'
    return img_dir
# jsonファイル保存（デバッグ用途）
def get_jsonfolder(rootfolder):
    abs_path = os.path.join(rootfolder, 'json').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''

def get_jsonfolder_upload(rootfolder):
    abs_path = os.path.join(rootfolder, 'upload', 'json').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''

# TextDatasデータを読み込み行ごとに文字列を連結
# page_no : -1 で全ページ
def sv_get_textlines(textdatas, page_no, area_no):
    if not textdatas:
        logger.error(f'textdatas False {page_no=}')
        return []
    textlines = []
    threshold = 8
    for pagedata in textdatas:
        if page_no == -1 or pagedata.page_no == page_no:
            if area_no != -1 and pagedata.area_no != area_no:
                continue
            # if pagedata.page_no and 1 < pagedata.page_no:
            #     textlines.append('\n*****  ' + str(pagedata.page_no) + ' ページ  *****\n')
            # if pagedata.area_no and 1 < pagedata.area_no:
            #     textlines.append('\n*****  分割エリア ' + str(pagedata.area_no) + '  *****\n')
            pre_y1 = -1
            pre_y2 = -1
            text = ''
            for textdata in pagedata.textdata_list:
                y1 = textdata.y1
                y2 = textdata.y2
                if pre_y1 == -1:
                    pre_y1 = y1
                    pre_y2 = y2
                elif pre_y1 - threshold <= y1 <= pre_y1 + threshold:
                # elif is_line(y1, y2, pre_y1, pre_y2):
                    pre_y1 = y1
                    pre_y2 = y2
                else:
                    pre_y1 = y1
                    pre_y2 = y2
                    textlines.append(text)
                    text = ''
                text += textdata.text
            textlines.append(text)
    return textlines
# TextDatasデータを読み込み行ごとに文字列を(改行コードで区切り)連結
def sv_get_textlines_lf(textdatas, page_no, area_no):
    if not textdatas:
        logger.error(f'textdatas False {page_no=}')
        return []
    textlines = []
    threshold = 8
    for pagedata in textdatas:
        if page_no == -1 or pagedata.page_no == page_no:
            if area_no != -1 and pagedata.area_no != area_no:
                continue
            pre_y1 = -1
            pre_y2 = -1
            text = ''
            for textdata in pagedata.textdata_list:
                y1 = textdata.y1
                y2 = textdata.y2
                if pre_y1 == -1:
                    pre_y1 = y1
                    pre_y2 = y2
                # elif pre_y - threshold <= y <= pre_y + threshold:
                elif is_line(y1, y2, pre_y1, pre_y2):
                    pre_y1 = y1
                    pre_y2 = y2
                else:
                    pre_y1 = -1
                    pre_y1 = y1
                    pre_y2 = y2
                    textlines.append(text)
                    text = ''
                # text += textdata.text + '\r\n'
                text += textdata.text + '\n'
            textlines.append(text)
    return textlines

def is_line(y1, y2, pre_y1, pre_y2):
    ret = False
    threshold = 8
    if (pre_y1 < y1 and pre_y2 < y2 and y1 < pre_y2
        and ((y1 - pre_y1) * 1.5 < pre_y2 - y1 and (y2 - pre_y2) * 1.5 < pre_y2 - y1)):
        # 重なり部分が重ならない部分の１．５倍以上
        ret = True
    elif (y1 < pre_y1 and y2 < pre_y2 and pre_y1 < y2
        and ((pre_y1 - y1) * 1.5 < y2 - pre_y1 and (pre_y2 - y2) * 1.5 < y2 - pre_y1)):
        # 重なり部分が重ならない部分の１．５倍以上
        ret = True
    elif pre_y1 - threshold <= y1 <= pre_y1 + threshold:
        # 上辺のずれがthreshold以下
        ret = True
    elif pre_y2 - threshold <= y2 <= pre_y2 + threshold:
        # 下辺のずれがthreshold以下
        ret = True
    elif pre_y1 <= y1 and y2 <= pre_y2:
        # 前の文字列の内にある
        ret = True
    elif y1 <= pre_y1 and pre_y2 <= y2:
        # 前の文字列が内にある
        ret = True
    return ret

# TextDatasデータを読み込む（行ごとに文字列を連結なし)
# page_no : -1 で全ページ
def sv_get_textdatas_area(textdatas, page_no, area_no):
    textdatas_area = []
    for pagedata in textdatas:
        if page_no == -1 or pagedata.page_no == page_no:
            if area_no != -1 and pagedata.area_no != area_no:
                continue
            # for textdata in pagedata.textdata_list:
            #     textdatas_area.append(textdata)
            textdatas_area.extend(pagedata.textdata_list)
    return textdatas_area

# ユーザ権限
def sv_get_user_authority(user_id):
    try:
        userobj = EvcUser.objects.get(user_id=user_id)
        return userobj.user_authority
    except Exception:
        pass
    return '一般'

# ユーザ名
def sv_get_user_name(user_id):
    try:
        userobj = EvcUser.objects.get(user_id=user_id)
        return userobj.user_name
    except Exception:
        pass
    return ''
# 選択可能契約会社のList
def sv_get_select_owner_list(user_id):
    owner_list = []
    owners = SysOwner.objects.none()
    if not user_id:
        return owner_list
    try:
        userobj = EvcUser.objects.get(user_id=user_id)
        if userobj.user_authority == 'スーパーバイザ':
            owners = SysOwner.objects.all().order_by('owner_id')
        elif userobj.user_authority == 'グループ管理者':
            owners = SysOwner.objects.filter(charge_email=user_id).order_by('owner_id')
            if (not owners or owners.count() == 0) and userobj.owner_id:
                owners = SysOwner.objects.filter(owner_id=userobj.owner_id)
        # elif userobj.user_authority == '管理者':
        else:
            if userobj.owner_id:
                owners = SysOwner.objects.filter(owner_id=userobj.owner_id)
    except Exception:
        pass
    if owners:
        for item in owners:
            owner_list.append((item.owner_id, item.owner_ryaku_name))
    # owners = MtOwnerUser.objects.none()
    # try:
    #     owners = MtOwnerUser.objects.filter(user_id=user_id).order_by('owner_id')
    # except Exception:
    #     pass
    # if owners:
    #     for item in owners:
    #         exists = any(item.owner_id == d[0] for d in owner_list)
    #         if not exists:
    #             owner_list.append((item.owner_id, sv_get_owner_ryaku_name(item.owner_id)))
    return owner_list

# # 選択可能契約会社のList
# def sv_get_selectable_owners(user_id):
#     owners = MtOwnerUser.objects.none()
#     if user_id:
#         try:
#             owners = MtOwnerUser.objects.filter(user_id=user_id).order_by('owner_id')
#             # userobj = EvcUser.objects.get(user_id=user_id)
#             # if userobj.user_authority == 'スーパーバイザ':
#             # elif userobj.user_authority == 'グループ管理者':
#             # elif userobj.user_authority == '管理者':
#         except Exception:
#             pass
#     return owners
# # 契約会社のList
# def sv_get_owner_list(user_id):
#     owners = SysOwner.objects.none()
#     if user_id:
#         try:
#             userobj = EvcUser.objects.get(user_id=user_id)
#             if userobj.user_authority == 'スーパーバイザ':
#                 owners = SysOwner.objects.all().order_by('owner_id')
#             elif userobj.user_authority == 'グループ管理者':
#                 owners = SysOwner.objects.filter(charge_email=user_id).order_by('owner_id')
#                 if (not owners or owners.count() == 0) and userobj.owner_id:
#                     owners = SysOwner.objects.filter(owner_id=userobj.owner_id)
#             elif userobj.user_authority == '管理者':
#                 if userobj.owner_id:
#                     owners = SysOwner.objects.filter(owner_id=userobj.owner_id)
#         except Exception:
#             pass
#     return owners

# 契約会社IDの取得
def get_owner_id(user_id):
    try:
        owner_id = EvcUser.objects.get(user_id=user_id).owner_id
    except Exception:
        user_id_hash = ut_get_hash(user_id)
        logger.exception(f'get_owner_id exception {user_id_hash=}')
        owner_id = None
    return owner_id
# 会社名（略称）の取得
def sv_get_owner_ryaku_name(owner_id):
    if owner_id:
        try:
            owner_ryaku_name = SysOwner.objects.get(owner_id=owner_id).owner_ryaku_name
        except Exception:
            logger.exception(f'get owner_ryaku_name exception {owner_id=}')
            owner_ryaku_name = ''
    else:
        owner_ryaku_name = ''
    return owner_ryaku_name
# 利用者数のチェック
def sv_can_add_user(owner_id):
    users_number = 0
    users_count = 0
    if owner_id:
        try:
            users_number = SysOwner.objects.get(owner_id=owner_id).users_number
        except Exception:
            logger.exception(f'get users_number exception {owner_id=}')
        try:
            users_count = EvcUser.objects.filter(owner_id=owner_id).exclude(delete_flg=1).count()
        except Exception:
            logger.exception(f'get EvcUser count exception {owner_id=}')
    if users_count < users_number:
        return True
    else:
        return False
# 管理者数のチェック
def sv_can_add_adminuser(owner_id):
    users_number = 2
    users_count = 0
    if owner_id:
        try:
            users_count = EvcUser.objects.filter(owner_id=owner_id,delete_flg=0).exclude(user_authority='一般').count()
        except Exception:
            logger.exception(f'get EvcUser count exception {owner_id=}')
    if users_count < users_number:
        return True
    else:
        return False
# カテゴリのList(フォルダ管理マスタ)
def sv_get_category_list(owner_id):
    categorys = []
    if owner_id:
        # lists = MtFolder.objects.filter(owner_id=owner_id).values_list('category_name', flat=True).order_by('folder_id')
        lists = MtFolder.objects.filter(owner_id=owner_id).values_list('category_name', flat=True).order_by('-use_count','-display_order','folder_id')
        for list in lists:
            # if list != 'その他' and list != 'other':
            categorys.append(list)
    if not categorys:
        categorys = ['契約書','納品書','請求書','領収書','その他']
    return categorys
# フォルダ(カテゴリ)IDの取得
def sv_get_folder_id(owner_id, category):
    #  get() が複数のオブジェクトを見つけた場合は、 Model.MultipleObjectsReturned 例外が発生します。
    # try:
    #     obj = MtFolder.objects.get(owner_id=owner_id, category_name=category)
    # except MtFolder.DoesNotExist:
    #     logger.exception('MtFolder get exception category: ' + (category or 'None'))
    #     return None
    obj = MtFolder.objects.filter(owner_id=owner_id, category_name=category).first()
    if obj:
        return obj.folder_id
    else:
        return ''
# カテゴリ名の取得
def sv_get_category_name(owner_id, folder_id):
    try:
        obj = MtFolder.objects.get(owner_id=owner_id, folder_id=folder_id)
    except MtFolder.DoesNotExist:
        logger.exception(f'MtFolder DoesNotExist {folder_id=}')
        return None
    return obj.category_name

# カテゴリのフォルダの絶対パス
# def sv_get_category_path(owner_id, category):
#     folderobj = MtFolder.objects.filter(owner_id=owner_id, category_name=category).first()
#     if folderobj:
#         dest_dir = folderobj.folder_path
#     else:
#         dest_dir = ''
#     if not dest_dir:
#         rootfolder = get_rootfolder(owner_id)
#         if rootfolder:
#             dest_dir = os.path.join(root_folder, category).replace(os.sep,'/')
# #             dest_dir = os.path.join(rootfolder, 'others').replace(os.sep,'/')
#     logger.debug('return category_path: ' + (category or 'None') + ' : ' + (dest_dir or 'None'))
#     return dest_dir

# 年月フォルダパス
def sv_get_processed_ym_path(rootfolder, processed_ym):
    if rootfolder and len(processed_ym) == 6:
        yy = processed_ym[:4]
        mm = processed_ym[4:]
        processed_dir = os.path.join(rootfolder, yy, mm).replace(os.sep,'/')
        dest_file = processed_dir
        # dest_file = os.path.join(processed_dir, filename).replace(os.sep,'/')
    else:
        dest_file = ''
    return dest_file

# エビデンス情報evidence_data(bytea型)からファイル名を取得
def sv_get_evidence_filename(evi_obj):
    b_pdf = evi_obj.evidence_data    #  PostgreSQLのbytea型はmemorybuffer型を返す
    if b_pdf:
        # filepath = b_pdf.tobytes().decode('utf-8')
        filepath = b_pdf.decode('utf-8')
    else:
        rootfolder = get_rootfolder(evi_obj.owner_id)
        dest_dir = sv_get_processed_ym_path(rootfolder, evi_obj.processed_ym)
        filepath = os.path.join(dest_dir, evi_obj.pdf_name).replace(os.sep,'/')
    return filepath
# エビデンス情報から画像ファイル名を取得
def sv_get_evidence_imagepath(evi_obj):
    rootfolder = get_rootfolder(evi_obj.owner_id)
    # img_dir = get_evidence_image_dir(rootfolder)
    # filepath = os.path.join(img_dir, evi_obj.evidence_id + '.jpg').replace(os.sep,'/')
    dest_dir = sv_get_processed_ym_path(rootfolder, evi_obj.processed_ym)
    filepath = os.path.join(dest_dir, 'img', evi_obj.evidence_id + '.jpg').replace(os.sep,'/')
    return filepath

# 会社名の略称を正式名称に変更
def sv_conv_company(name):
    name = name.replace('　', ' ')  # 全角を半角に
    name = name.replace('（株）', '株式会社').replace('(株)', '株式会社').replace('㈱', '株式会社')
    name = name.replace('（有）', '有限会社').replace('(有)', '有限会社').replace('㈲', '有限会社')
    name = name.replace('（同）', '合同会社').replace('(同)', '合同会社')
    name = name.replace('，', ',').replace('．', '.')   # 全角を半角に
    return name
# 取引先IDの取得
def sv_get_partner_id(name, owner_id):
    if not name or not owner_id:
        return None
    # owner_id = get_owner_id(user_id)
    name = sv_conv_company(name)
    partnerobj = MtPartner.objects.filter(owner_id=owner_id, partner_name=name).exclude(delete_flg=1).first()
    # 「get」で条件に合ったオブジェクトが複数個存在する場合、MultipleObjectsReturnedという例外が発生
    # partner_id = MtPartner.objects.get(partner_name=name).partner_id
    if partnerobj:
        partner_id = partnerobj.partner_id
    else:
        partner_id = None
    # b = name.encode('cp932', 'ignore')
    # s_after = b.decode('cp932')
    # logger.debug(f'partner_id {name} : {partner_id}')
    return partner_id
# 検出情報データ作成
def sv_save_detect(detect_partner_name, detect_publisher_name, user_id, evidence_id):
    # d = ut_get_localtoday().strftime('%y%m%d')
    # id = d + '0001'
    create_date = ut_get_timezone_now()
    obj = TtDetect(
        evidence_id=evidence_id,
        category_name=None,
        processed_date=None,
        partner_name=detect_partner_name,
        publisher_name=detect_publisher_name,
        total_amount=None,
        create_date=create_date,
        create_user=user_id,
        update_user=user_id,
        update_date=create_date,
    )
    try:
        obj.save()
        logger.info(f'save detect {evidence_id} : {detect_partner_name}')
        id = evidence_id
    except Exception:
        logger.exception(f'detect save Exception {evidence_id} : {detect_partner_name}')
        id = None

    return id
# 検出情報データ削除
def sv_delete_detect(evidence_id):
    if evidence_id:
        try:
            detect = TtDetect.objects.get(evidence_id=evidence_id)
            detect.delete()
        except TtDetect.DoesNotExist:
            pass
# 検出情報取引先名取得
def sv_get_detect_partner_name(evidence_id):
    partner = ''
    if evidence_id:
        try:
            partner = TtDetect.objects.get(evidence_id=evidence_id).partner_name
        except TtDetect.DoesNotExist:
            pass
    return partner
# 検出情報発行元名取得
def sv_get_detect_publisher_name(evidence_id):
    publisher = ''
    if evidence_id:
        try:
            publisher = TtDetect.objects.get(evidence_id=evidence_id).publisher_name
        except TtDetect.DoesNotExist:
            pass
    return publisher
# 取引先名取得
def sv_get_partner_name(partner_id):
    partner = ''
    if partner_id:
        try:
            partner = MtPartner.objects.get(partner_id=partner_id).partner_name
        except MtPartner.DoesNotExist:
            pass
    return partner
# 取引先名(略)取得
def sv_get_partner_ryaku_name(partner_id):
    partner_ryaku_name = ''
    if partner_id:
        try:
            partner_ryaku_name = MtPartner.objects.get(partner_id=partner_id).partner_ryaku_name
        except MtPartner.DoesNotExist:
            pass
    return partner_ryaku_name
# 発行元名取得
def sv_get_publisher_name(publisher_id):
    publisher_name = ''
    if publisher_id:
        try:
            publisher_name = SysOwner.objects.get(owner_id=publisher_id).owner_name
        except SysOwner.DoesNotExist:
            try:
                publisher_name = MtPartner.objects.get(partner_id=publisher_id).partner_name
            except MtPartner.DoesNotExist:
                pass
    return publisher_name
# 発行元IDの取得（契約会社マスタ）
def sv_get_publisher_id(name, user_id):
    if not name:
        return None
    name = sv_conv_company(name)
    ownerobj = SysOwner.objects.filter(owner_name=name).first()
    if ownerobj:
        publisher_id = ownerobj.owner_id
    else:
        publisher_id = None
    # logger.debug(f'publisher_id {name} : {publisher_id}')
    return publisher_id
# 法人番号取得
def sv_get_corporate_number(partner_id):
    corporate_number = ''
    if partner_id:
        try:
            corporate_number = MtPartner.objects.get(partner_id=partner_id).corporate_number
        except MtPartner.DoesNotExist:
            pass
    return corporate_number

# 取引先のList
def sv_get_partner_list(owner_id):
    partners = []
    lists = MtPartner.objects.filter(owner_id=owner_id).values('partner_id', 'partner_name').exclude(delete_flg=1).order_by('partner_name')
    for item in lists:
        partners.append((item.get('partner_id'), item.get('partner_name')))

    return partners

# 発行元のList
def sv_get_publisher_list(owner_id):
    publishers = []
    # if owner_id:
    #     ownerobj = SysOwner.objects.filter(owner_name=name).first()
    lists = SysOwner.objects.filter(owner_id=owner_id).values('owner_id', 'owner_name').order_by('owner_id')
    for item in lists:
        publishers.append((item.get('owner_id'), item.get('owner_name')))
    # lists = MtPartner.objects.filter(owner_id=owner_id).values('partner_id', 'partner_name').exclude(delete_flg=1).order_by('partner_id')
    # for item in lists:
    #     publishers.append((item.get('partner_id'), item.get('partner_name')))

    return publishers

# 新規partner_id取得
def get_new_partner_id():
    # d = ut_get_localtoday().strftime('%y%m%d')
    # id = d + '0001'
    prefix = 'AUTO_'
    try:
        num = get_next_value('partner')
    except Exception:   # ValueError
        pre_obj = MtPartner.objects.filter(partner_id__contains=prefix).order_by('-partner_id').first()
        if pre_obj:
            pre_id = pre_obj.partner_id
            num = int(pre_id[-5:]) + 1
        else:
            num = 1
    id = 'AUTO_00000'
    if num < 99999:
        id = prefix + f'{num:05d}'
    else:
        num = 1
        while num < 100000:
            id = prefix + f'{num:05d}'
            exists = MtPartner.objects.filter(partner_id=id).exists()
            if not exists:
                break
            num += 1
    logger.debug(f'new partner_id {id}')
    return id

# 取引先データ作成
def sv_create_partner_auto(name, user_id, owner_id):
    if not name or not owner_id:
        return None
    # d = ut_get_localtoday().strftime('%y%m%d')
    # id = d + '0001'
    id = get_new_partner_id()

    create_date = ut_get_timezone_now()
    obj = MtPartner(
        partner_id=id,
        partner_name=name,
        owner_id=owner_id,
        partner_type=0,
        delete_flg=0,
        create_date=create_date,
        create_user=user_id,
        update_user=user_id,
        update_date=create_date,
    )
    try:
        obj.save()
        logger.info(f'sv_create_partner_auto {id} : {name}')
    except Exception:
        logger.exception(f'sv_create_partner_auto save Exception {id} : {name}')
        id = None

    return id
# 取引先データ登録
def sv_save_partner(data, user_id, kubun):
    if kubun == 'new':
        partner_id = get_new_partner_id()
        create_date = ut_get_timezone_now()
        create_user = user_id
        update_date = create_date
        update_user = user_id
    else:
        partner_id = data.get('partner_id')
        try:
            partner_obj = MtPartner.objects.get(partner_id=partner_id)
        except MtPartner.DoesNotExist:
            logger.exception(f'MtPartner DoesNotExist {partner_id=}')
        # raise ValueError('取引先データ登録　取得エラー ' + partner_id)
            return False
        if partner_obj.create_date:
            create_date = ut_get_localdate(partner_obj.create_date)
        else:
            create_date = None
        create_user = partner_obj.create_user
        update_date = ut_get_timezone_now()
        update_user = user_id
    delete_flg = data.get('delete_flg')
    obj = MtPartner(
        partner_id=partner_id,
        partner_name = data.get('partner_name'),
        partner_type = data.get('partner_type'),
        partner_ryaku_name = data.get('partner_ryaku_name'),
        owner_id = data.get('owner_id'),
        corporate_number = data.get('corporate_number'),
        charge_dept = data.get('charge_dept'),
        charge_name = data.get('charge_name'),
        charge_email = data.get('charge_email'),
        zip_code = data.get('zip_code'),
        address1 = data.get('address1'),
        address2 = data.get('address2'),
        tel_no = data.get('tel_no'),
        fax_no = data.get('fax_no'),
        notes = data.get('notes'),
        delete_flg = delete_flg or 0,
        create_date=create_date,
        create_user=create_user,
        update_user=update_user,
        update_date=update_date,
    )
    try:
        obj.save()
        logger.info(f'MtPartner save {partner_id} : {obj.partner_name}')
        return partner_id
    except Exception:
        logger.exception(f'MtPartner save exception {partner_id} : {obj.partner_name}')
    return False

# 取引先データ削除
def sv_delete_partner(partner_id, user_id):
    try:
        partner_obj = MtPartner.objects.get(partner_id=partner_id)
    except MtPartner.DoesNotExist:
        logger.exception(f'MtPartner DoesNotExist {partner_id=}')
        # raise ValueError('取引先データ削除　取得エラー ' + partner_id)
        return False
    if partner_obj.create_date:
        partner_obj.create_date = ut_get_localdate(partner_obj.create_date)
    partner_obj.update_user = user_id
    partner_obj.update_date = ut_get_timezone_now()
    partner_obj.delete_flg = Decimal(1)

    try:
        partner_obj.save()
        logger.info(f'MtPartner delete {partner_id} : {partner_obj.partner_name}')
        return partner_id
    except Exception:
        logger.exception(f'MtPartner delete exception {partner_id} : {partner_obj.partner_name}')
    return False

# 科目のList
def sv_get_account_list(owner_id):
    accounts = []
    lists = MtAccount.objects.all().values('account_id', 'account_name').order_by('account_name')
    for item in lists:
        accounts.append((item.get('account_id'), item.get('account_name')))

    return accounts
# 科目IDの取得
def sv_get_account_id(name, user_id, owner_id, create):
    # if not name or not owner_id:
    if not name:
        return None
    accountobj = MtAccount.objects.filter(account_name=name).first()
    # 「get」で条件に合ったオブジェクトが複数個存在する場合、MultipleObjectsReturnedという例外が発生
    # partner_id = MtPartner.objects.get(partner_name=name).partner_id
    if accountobj:
        account_id = accountobj.account_id
    else:
        account_id = None
        # # 取引先データがなければ作成
        # if create:
        #     account_id = create_account_auto(name, user_id, owner_id)
        # else:
        #     account_id = None
    logger.debug(f'account_id  {name} : {account_id}')
    return account_id

# 科目データ登録
def sv_save_account(data, user_id, kubun):
    if kubun == 'new':
        account_id = get_new_account_id()
        create_date = ut_get_timezone_now()
        create_user = user_id
        update_date = create_date
        update_user = user_id
    else:
        account_id = data.get('account_id')
        try:
            account_obj = MtAccount.objects.get(account_id=account_id)
        except MtAccount.DoesNotExist:
            logger.exception(f'MtAccount DoesNotExist {account_id=}')
        # raise ValueError('取引先データ登録　取得エラー ' + account_id)
            return False
        if account_obj.create_date:
            create_date = ut_get_localdate(account_obj.create_date)
        else:
            create_date = None
        create_user = account_obj.create_user
        update_date = ut_get_timezone_now()
        update_user = user_id
    # delete_flg = data.get('delete_flg')
    obj = MtAccount(
        account_id=account_id,
        account_name = data.get('account_name'),
        # delete_flg = delete_flg or 0,
        create_date=create_date,
        create_user=create_user,
        update_user=update_user,
        update_date=update_date,
    )
    try:
        obj.save()
        logger.info(f'MtAccount save {account_id} : {obj.account_name}')
        return account_id
    except Exception:
        logger.exception(f'MtAccount save exception {account_id} : {obj.account_name}')
    return False
# 新規account_id取得
def get_new_account_id():
    # d = ut_get_localtoday().strftime('%y%m%d')
    # id = d + '0001'
    prefix = 'acct_'
    try:
        num = get_next_value('account')
    except Exception:   # ValueError
        pre_obj = MtAccount.objects.filter(account_id__contains=prefix).order_by('-account_id').first()
        if pre_obj:
            pre_id = pre_obj.account_id
            num = int(pre_id[-5:]) + 1
        else:
            num = 1
    id = 'acct_00000'
    if num < 99999:
        id = prefix + f'{num:05d}'
    else:
        num = 1
        while num < 100000:
            id = prefix + f'{num:05d}'
            exists = MtAccount.objects.filter(account_id=id).exists()
            if not exists:
                break
            num += 1
    logger.debug(f'new account_id: {id}')
    return id

# HTMLで表示するためのファイルのURLを取得
def sv_file2url(filepath):
    evc_url = getattr(settings, 'EVC_URL')
    evcpath = getattr(settings, 'EVC_ROOT')
    # エラー：'PosixPath' object has no attribute 'lower'
    # 解決策：str() で文字列に変換する
    # evc_dir = str(evcpath).lower()
    evc_dir = str(evcpath)
    # if not evc_dir.endswith('/'):
    #     evc_dir += '/'
    url_path = filepath.replace(os.sep,'/').replace(evc_dir, evc_url)
    # if not evc_dir.endswith('\\'):
    #     evc_dir += '\\'
    # url_path = filepath.lower().replace(evc_dir, evc_url).replace('\\', '/')
    # logger.debug(f'url_path: {url_path}')
    return url_path

# HTMLで表示するためのファイルのURLを取得
def sv_helpurl():
    evc_url = getattr(settings, 'EVC_HELP_URL')
    url_path = evc_url
    # if not evc_dir.endswith('\\'):
    #     evc_dir += '\\'
    # url_path = filepath.lower().replace(evc_dir, evc_url).replace('\\', '/')
    logger.debug(f'help_path: {url_path}')
    return url_path
