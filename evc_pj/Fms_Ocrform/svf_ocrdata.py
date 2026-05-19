import os
import datetime
import shutil
import logging
import json

# from PIL import Image

# from decimal import Decimal
from django.conf import settings
# from django.utils import timezone
# from django.utils.timezone import make_aware
# from django.http import HttpResponse
from django.db.models import Q
from sequences import get_next_value

from Fms_Ocrform.models import TtOcrform,TtEntry,TtOcrData,TtTimesheet,TtJafyame,TtAccessLog

from commons.utils import ut_get_localdate,ut_get_timezone_now,ut_get_localtoday

from Evc_App.sv_file import sv_delete_file,get_imgfolder_upload,get_jsonfolder

from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_json import sv_save_json,sv_save_detect_json,sv_datas2json
from Evc_App.sv_get_image_shape import sv_get_pdfpages

from Fms_Ocrform.svf_extract_text import svf_extract_text

from Fms_Ocrform.svf_common import (svf_get_ocrdata_rootfolder,svf_get_ocrdata_imagepath,
    svf_move_uploadfile_ymfolder,svf_move_uploadfile_jafyame,svf_get_jafyame_imagepath,
    svf_get_areas_dict,svf_draw_area,
    svf_adjust_image,svf_get_json_text_page
)

from Fms_Ocrform.svt_adjust_image import svt_adjust_image_trapezoid

from Fms_Ocrform.svf_extract_image import extract_image_from_pdf,pdf_to_image

MODEL_CLASSES = {	
    'entry': TtEntry,
    'ocrdata': TtOcrData,	
    'timesheet': TtTimesheet,	
    'jafyame': TtJafyame,	# JAふくおか八女
}
PAGE_MARK_IMAGE = '/data_root/evc_root/jafyame.jpg'   # OCRでテキストを抽出するページを判定する画像

logger = logging.getLogger(__name__)

# Ocr文書IDから画像ファイル名を取得
def get_ocrdata_imagefile(model_name, ocrdata_id, page_no):
    model_class = MODEL_CLASSES.get(model_name)
    if not model_class:
        return ''
    imagepath = ''
    try:
        q_objects = ''
        if model_name == 'ocrdata':
            q_objects = Q(ocrdata_id=ocrdata_id)
        elif model_name == 'timesheet':
            q_objects = Q(timesheet_id=ocrdata_id)
        elif model_name == 'entry':
            q_objects = Q(entry_id=ocrdata_id)
        elif model_name == 'jafyame':   # JAふくおか八女
            q_objects = Q(jafyame_id=ocrdata_id)
        obj = model_class.objects.get(q_objects)
        processed_ym = obj.processed_ym
    except model_class.DoesNotExist:
        return ''
    if obj:
        if model_name == 'jafyame': # JAふくおか八女 部課imgフォルダ
            imagepath = svf_get_jafyame_imagepath(obj.dept, obj.section, ocrdata_id, page_no)
        else:
            imagepath = svf_get_ocrdata_imagepath(model_name, processed_ym, ocrdata_id, page_no)

    return imagepath

# OCR抽出情報Ocr文書テーブル登録
def svf_create_ocrdata(model_name, uploadfiles, user_id, owner_id):
    ok_list = []
    error_list = []
    rootfolder = svf_get_ocrdata_rootfolder(model_name)   # ルートフォルダを取得
    img_upload_dir = get_imgfolder_upload(rootfolder)
    if not img_upload_dir:
        logger.error(f'upload imgfolder error {rootfolder=}')
        return ok_list, error_list
    json_dir = get_jsonfolder(rootfolder)

    for uploadfile in uploadfiles:
        filename = uploadfile.get('name')
        path = uploadfile.get('path')
        ocrform_id = uploadfile.get('ocrform')
        # Ocr文書ファイルの年月フォルダに移動
        new_path = svf_move_uploadfile_ymfolder(path, rootfolder, filename).replace(os.sep,'/')
        if model_name == 'jafyame': # JAふくおか八女
            # pages_to_convert = extract_image_from_pdf(new_path, img_upload_dir, PAGE_MARK_IMAGE)
            pages_to_convert = [1]  # 先頭ページのみ
            # 指定ページの画像データを作成
            ocrimages = pdf_to_image(new_path, pages_to_convert, output_dir=img_upload_dir)
        else:
            # ページごとに画像データを作成
            ocrimages = sv_create_ocr_image(new_path, img_upload_dir, -1)
        if not ocrimages:   # パスワード設定などにより読み込めない
            logger.error(f'ocrimages False {filename=}')
            error_list.append(filename)
            sv_delete_file(new_path)    # アップロードファイル削除
            continue
        if model_name == 'entry':
            # 入力画像をフォーム画像に合わせる（射影変換）台形補正
            ocrimages = svt_adjust_image_trapezoid(ocrimages, ocrform_id)
        else:
            # 入力画像をフォーム画像に合わせる（射影変換）
            ocrimages = svf_adjust_image(ocrimages, ocrform_id)
        areas_dict = {}
        # フォーム情報を取得(分割領域・項目リスト)
        if not ocrform_id:
            try:
                result_first = TtOcrform.objects.all().first()
                if result_first:
                    ocrform_id = result_first.ocrform_id
            except Exception:
                pass
        ocrform_area = ''
        try:
            ocrform_obj =  TtOcrform.objects.get(ocrform_id=ocrform_id)
            ocrform_area = ocrform_obj.ocrform_area
            # 輪郭枠座標をjson文字列に変換(javascriptで処理)
            areas_dict = svf_get_areas_dict(ocrform_obj.ocrform_area)  
            # フォームの入力項目情報を取得
            if ocrform_obj.ocrform_text:
                ocrform_text_datas = json.loads(ocrform_obj.ocrform_text)
            else:
                ocrform_text_datas = None
        except TtOcrform.DoesNotExist:
            ocrform_text_datas = None
        if settings.DEBUG:
            svf_draw_area(ocrimages, ocrform_area)
        # # OCRは編集で領域位置調整後実行
        # textdatas = []
        # detecttext_list = []
        # google_cnt = 0

        # フォームが1ページで複数ページの文書に対応のため設定する
        for i in range(len(ocrimages)):
            areas = areas_dict.get(i)
            if not areas:
                if areas_dict.get(0):
                    areas_dict[i] = areas_dict.get(0)

        # OCR機能を使って、フォームの項目の領域ごとのTextDataデータを取得
        textdatas, detecttext_list, google_cnt, full_texts = svf_extract_text(ocrimages, areas_dict)
        logger.debug(f'extract text {filename=}')

        ocrdata_id = get_ocrdata_id(model_name)
        save_id = False
        page_count = len(ocrimages)
        lists = []
        fulltext = ''
        for page_no in range(1, page_count + 1):
            # フォームの項目の領域ごとに抽出テキストを取得
            if model_name == 'entry':
                pattern = 2 # 1: PDF 2: 写真
                param_dict = {
                    'model_name': model_name,
                    'textdatas': textdatas,
                    'page_no': page_no,
                    'ocrform_text_datas': ocrform_text_datas,
                    'areas_dict': areas_dict,
                    'ocrimages': ocrimages,
                    'pattern': pattern
                }
            else:
                param_dict = {
                    'model_name': model_name,
                    'textdatas': textdatas,
                    'page_no': page_no,
                    'ocrform_text_datas': ocrform_text_datas,
                }
            # **kwargs: 複数のキーワード引数を辞書として受け取る
            page_lists = svf_get_json_text_page(**param_dict)
            data = {
                'page_no': str(page_no),
                'page_list':page_lists
            }
            lists.append(data)
            # 全文テキストデータを作成
            if full_texts:
                sep = '\n' if fulltext else ''
                fulltext = f'{fulltext}{sep}{full_texts.get(page_no)}'
        # lists : [{'page_no': '1', 'page_list': [...]}, {'page_no': '2', 'page_list': [...]}]
        # dictのリストをJSON形式の文字列に変換
        json_str = sv_datas2json(lists)
        search = json.dumps(get_search_text(json_str, page_no)) # 辞書型のオブジェクトをJSON形式の文字列に変換
        create_param_dict = {
            'filepath': new_path,
            'page_no': -1,
            # 'page_no': page_no,
            'user_id': user_id,
            'owner_id': owner_id,
            'ocrform_id': ocrform_id,
            'formarea': ocrform_area,
            'json_str': json_str,
            'search': search,
            'fulltext': fulltext,
            'google_cnt': google_cnt
        }
        save_id = svf_create_ocrdata_page(model_name, ocrdata_id, create_param_dict)
        if save_id:
            ok_list.append(save_id)
            move_images(model_name, ocrimages, save_id)    # MOVE
            if settings.DEBUG:
                # jsonファイルを保存
                if textdatas:
                    sv_save_json(new_path, textdatas, json_dir)
                if detecttext_list:
                    basename_without_ext, ext_name = os.path.splitext(filename)
                    sv_save_detect_json(basename_without_ext, detecttext_list, json_dir)
        else:
            error_list.append(filename)
            logger.error(f'create ocrdata error {filename=}')
            sv_delete_file(new_path)    # アップロードファイル削除

    return ok_list, error_list
# Ocr文書テーブル登録処理
def svf_create_ocrdata_page(model_name, ocrdata_id, param_dict):
    filepath = param_dict.get('filepath')
    basename = os.path.basename(filepath)
    basename_without_ext, ext_name = os.path.splitext(basename)

    page_no = param_dict.get('page_no')
    #  複数ページでページごとのエビデンスの場合、'_Page1'の形式でページ番号を追加
    if page_no == -1:
        pdf_name = basename_without_ext
        ocrdata_id = ocrdata_id + '_00000' # ページごとに分割しない
    else:
        pdf_name = basename_without_ext + '_Page{}'.format(page_no)
        page = page_no if 0 < page_no else 1
        area = 1
        ocrdata_id = ocrdata_id + '_{:03d}{:02d}'.format(page, area)
    # pdf_name = basename_without_ext + '_Page{}'.format(page_no) + '({}/{})'.format(area_no, area_count)
    # entry_id ：yyyymmdd_連番(00001～)_ページ番号(001)+領域番号(01)
    # ocrdata_id = ocrdata_id + '_00000' # ページごとに分割しない
    # if entry_kubun == 'file':
    #     entry_id = entry_id + '_00000' # ページごとに分割しない
    # else:
    #     page = page_no if 0 < page_no else 1
    #     area = 1
    #     entry_id = entry_id + '_{:03d}{:02d}'.format(page, area)
    param_dict['pdf_name'] = pdf_name

    if model_name == 'timesheet':
        save_id = save_timesheet(ocrdata_id, param_dict)
    elif model_name == 'ocrdata':
        save_id = save_ocrdata(ocrdata_id, param_dict)
    elif model_name == 'entry':
        save_id = save_entry(ocrdata_id, param_dict)
    elif model_name == 'jafyame':   # JAふくおか八女
        save_id = save_jafyame(ocrdata_id, param_dict)
    else:
        save_id = False
    return save_id

# 文字列(TextDatasのリスト)からキー情報を抽出（ページごと)
def get_search_text(json_str, page_no):
    search = {
    }
    if not json_str:
        logger.error(f'json_str False')
        return search
    try:
        object_list = json.loads(json_str) # JSONデータをPythonオブジェクト(list型)へ変換
        outs = []
        for pagedata in object_list:
            # if pagedata.get('page_no') == str(page_no):
                list = pagedata.get('page_list')
                for item in list:
                    item_no = item.get('item_no')
                    item_name = item.get('item_name')
                    item_json = item.get('item_json')
                    item_text = item.get('item_text')
                    area_no = item.get('area_no')
                    table_id = item.get('table_id')
                    search[item_json] = item_text
    except Exception:
        logger.exception(f'get_search_text exception')

    return search
# 画像データを保存フォルダに移動
def move_images(model_name, ocrimages, ocrdata_id):
    if not ocrimages or not ocrdata_id:
        return
    for i, imagepath in enumerate(ocrimages, start=1):
        if not imagepath or not os.path.exists(imagepath):
            continue
        try:
            file_name = get_ocrdata_imagefile(model_name, ocrdata_id, i)
            # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
            new_path = shutil.move(imagepath, file_name)
            logger.info(f'move imagefile {imagepath} --> {new_path}')
        except Exception:   # ValueError
            logger.exception(f'move_images exception {ocrdata_id=}')
# Ocr文書情報テーブルID取得
def get_ocrdata_id(model_name):
    # entry_id：yyyymmdd_連番(00001～)

    d = ut_get_localtoday().strftime('%Y%m%d')
    # lastobj = TtWorkSchedule.objects.all().order_by('-entry_id').first() # first():存在しない場合Noneを返す
    # if lastobj:
    #     pre_id = lastobj.entry_id
    #     try:
    #         last = int(pre_id[:8])
    #         if last < int(d):
    #             id = d + '_00001'
    #         else:
    #             # num = int(pre_id[-5:])
    #             num = int(pre_id[9:14])
    #             id = d + '_{:05d}'.format(num + 1)
    #     except Exception:   # ValueError
    #         id = d + '_00001'
    # else:
    #     id = d + '_00001'
    try:
        # シーケンス採番
        num = get_next_value(f'{model_name}_{d}')
        id = d + '_{:05d}'.format(num)
    except Exception:   # ValueError
        id = d + '_00001'

    return id
# Ocr文書テーブル保存
def save_ocrdata(ocrdata_id, param_dict):
    user_id = param_dict.get('user_id')
    owner_id = param_dict.get('owner_id')
    filepath = param_dict.get('filepath')
    pdf_name = param_dict.get('pdf_name')
    fulltext = param_dict.get('fulltext')
    ocrform_id = param_dict.get('ocrform_id')
    # formarea = param_dict.get('formarea')
    json_str = param_dict.get('json_str')
    search_text = param_dict.get('search')
    fulltext = param_dict.get('fulltext')
    google_cnt = param_dict.get('google_cnt')
    try:
        d = ut_get_localtoday().strftime('%Y%m%d')
        create_date = ut_get_timezone_now()
        create_user_id = user_id
        id = ocrdata_id    # get_entry_id()
        processed_ym = ut_get_localtoday().strftime('%Y%m')
        search_text = search_text
        google_amount = google_cnt
        name = d + '_' + '' + '_'
        obj = TtOcrData(
            ocrdata_id=id,
            owner_id=owner_id,
            processed_ym=processed_ym,
            pdf_name=pdf_name,
            file_path=filepath,
            pdf_handbook=fulltext,
            ocrform_id=ocrform_id,
            # form_area=formarea,
            form_detail=json_str,
            search_text=search_text,
            google_amount=google_amount,
            create_date=create_date,                # DateTimeField
            create_user=create_user_id,
            update_user=user_id,
            update_date=ut_get_timezone_now()     # DateTimeField
        )
        obj.save()
        logger.info(f'TtOcrData save {id} : {pdf_name}')
    except Exception:
        logger.exception(f'TtOcrData save exception {pdf_name}')
        return False
    return id

# 勤務表情報テーブル保存
def save_timesheet(ocrdata_id, param_dict):
    user_id = param_dict.get('user_id')
    owner_id = param_dict.get('owner_id')
    filepath = param_dict.get('filepath')
    pdf_name = param_dict.get('pdf_name')
    fulltext = param_dict.get('fulltext')
    ocrform_id = param_dict.get('ocrform_id')
    # formarea = param_dict.get('formarea')
    json_str = param_dict.get('json_str')
    search = param_dict.get('search')
    search_text = json.loads(search)
    fulltext = param_dict.get('fulltext')
    google_cnt = param_dict.get('google_cnt')
    try:
        d = ut_get_localtoday().strftime('%Y%m%d')
        create_date = ut_get_timezone_now()
        create_user_id = user_id
        id = ocrdata_id    # get_entry_id()
        processed_ym = ut_get_localtoday().strftime('%Y%m')
        target_year = search_text.get('target_year')
        target_month = search_text.get('target_month')
        if target_year and target_month and 0 < len(target_year) and 0 < len(target_month):
            target_date = datetime.date(int(target_year), int(target_month), 1)
        else:
            target_date = None
        emp_name = search_text.get('emp_name')
        emp_id = search_text.get('emp_id')
        office_name = search_text.get('office_name')
        google_amount = google_cnt
        name = d + '_' + '' + '_'
        obj = TtTimesheet(
            timesheet_id=id,
            owner_id=owner_id,
            processed_ym=processed_ym,
            pdf_name=pdf_name,
            file_path=filepath,
            pdf_handbook=fulltext,
            ocrform_id=ocrform_id,
            # form_area=formarea,
            form_detail=json_str,
            target_date=target_date,
            emp_name=emp_name,
            emp_id=emp_id,
            office_name=office_name,
            google_amount=google_amount,
            create_date=create_date,                # DateTimeField
            create_user=create_user_id,
            update_user=user_id,
            update_date=ut_get_timezone_now()     # DateTimeField
        )
        obj.save()
        logger.info(f'TtTimesheet save {id} : {pdf_name}')
    except Exception:
        logger.exception(f'TtTimesheet save exception {pdf_name}')
        return False
    return id

# JAふくおか八女 文書テーブル保存
def save_jafyame(ocrdata_id, param_dict):
    user_id = param_dict.get('user_id')
    owner_id = param_dict.get('owner_id')
    filepath = param_dict.get('filepath')
    pdf_name = param_dict.get('pdf_name')
    fulltext = param_dict.get('fulltext')
    ocrform_id = param_dict.get('ocrform_id')
    # formarea = param_dict.get('formarea')
    json_str = param_dict.get('json_str')
    search = param_dict.get('search')
    search_text = json.loads(search)
    fulltext = param_dict.get('fulltext')
    google_cnt = param_dict.get('google_cnt')
    try:
        d = ut_get_localtoday().strftime('%Y%m%d')
        create_date = ut_get_timezone_now()
        create_user_id = user_id
        id = ocrdata_id    # get_entry_id()
        processed_ym = ut_get_localtoday().strftime('%Y%m')
        # processed_date = search_text.get('processed_date')
        target_year = search_text.get('date_y')
        target_month = search_text.get('date_m')
        target_day = search_text.get('date_d')
        if target_year and target_month and target_day\
                and 0 < len(target_year) and 0 < len(target_month) and 0 < len(target_day):
            processed_date = datetime.date(int(target_year), int(target_month), int(target_day))
        else:
            processed_date = None
        dept = search_text.get('dept')
        section = search_text.get('sect')
        spine = search_text.get('spine')
        username = search_text.get('name')
        google_amount = google_cnt
        name = d + '_' + '' + '_'
        filepath = svf_move_uploadfile_jafyame(filepath, dept, section) # JAふくおか八女 部課フォルダに移動
        obj = TtJafyame(
            jafyame_id=id,
            owner_id=owner_id,
            processed_ym=processed_ym,
            pdf_name=pdf_name,
            file_path=filepath,
            pdf_handbook=fulltext,
            ocrform_id=ocrform_id,
            form_detail=json_str,
            processed_date=processed_date,
            dept=dept,
            section=section,
            spine=spine,
            username=username,
            google_amount=google_amount,
            create_date=create_date,                # DateTimeField
            create_user=create_user_id,
            update_user=user_id,
            update_date=ut_get_timezone_now()     # DateTimeField
        )
        obj.save()
        logger.info(f'TtJafyame save {id} : {pdf_name}')
    except Exception:
        logger.exception(f'TtJafyame save exception {pdf_name}')
        return False
    return id
# OCR抽出情報エントリーテーブル登録
def save_entry(ocrdata_id, param_dict):
    user_id = param_dict.get('user_id')
    owner_id = param_dict.get('owner_id')
    filepath = param_dict.get('filepath')
    pdf_name = param_dict.get('pdf_name')
    fulltext = param_dict.get('fulltext')
    ocrform_id = param_dict.get('ocrform_id')
    formarea = param_dict.get('formarea')
    json_str = param_dict.get('json_str')
    search = param_dict.get('search')
    search_text = json.loads(search)
    fulltext = param_dict.get('fulltext')
    google_cnt = param_dict.get('google_cnt')
    try:
        d =ut_get_localtoday().strftime('%Y%m%d')
        create_date = ut_get_timezone_now()
        create_user_id = user_id
        id = ocrdata_id    # get_entry_id()
        processed_ym = ut_get_localtoday().strftime('%Y%m')
        google_amount = google_cnt
        entry_detail = json_str
        name = d + '_' + '' + '_'
        obj = TtEntry(
            entry_id=id,
            entry_name=name,
            owner_id=owner_id,
            ocrform_id=ocrform_id,
            pdf_name=pdf_name,
            file_path=filepath,
            processed_ym=processed_ym,
            entry_area=formarea,
            entry_detail=entry_detail,                # TextField
            google_amount = google_amount,
            create_date=create_date,                # DateTimeField
            create_user=create_user_id,
            update_user=user_id,
            update_date=ut_get_timezone_now()     # DateTimeField
        )
        obj.save()
        logger.info(f'TtEntry save {id} : {pdf_name}')
    except Exception:
        logger.exception(f'TtEntry save exception {pdf_name}')
        return False
    return id

# Ocr文書情報テーブル更新
def svf_update_ocrdata(ocrdata_id, data_dict, user_id):
    # owner_id = get_owner_id(user_id)
    try:
        ocrdata_obj = TtOcrData.objects.get(ocrdata_id=ocrdata_id)
    except TtOcrData.DoesNotExist:
        logger.exception(f'TtOcrData DoesNotExist {ocrdata_id=}')
        return False

    search_text = json.dumps(data_dict) # 辞書型のオブジェクトをJSON形式の文字列に変換

    ocrdata_obj.search_text = search_text
    ocrdata_obj.create_date = ut_get_localdate(ocrdata_obj.create_date)
    ocrdata_obj.update_user = user_id
    ocrdata_obj.update_date = ut_get_timezone_now()
    try:
        ocrdata_obj.save()
        logger.info(f'Ocr文書情報テーブル更新 {ocrdata_id} : {ocrdata_obj.pdf_name}')
    except Exception:
        logger.exception(f'TtEvidence update exception {ocrdata_id} : {ocrdata_obj.pdf_name}')
        return False
    return ocrdata_id
# 勤務表情報テーブル更新
def svf_update_timesheet(timesheet_id, data_dict, user_id):
    try:
        timesheet_obj = TtTimesheet.objects.get(timesheet_id=timesheet_id)
    except TtTimesheet.DoesNotExist:
        logger.exception(f'TtTimesheet DoesNotExist {timesheet_id=}')
        return False
    timesheet_obj.target_date = data_dict.get('target_date')
    timesheet_obj.office_name = data_dict.get('office_name')
    timesheet_obj.emp_name = data_dict.get('emp_name')
    timesheet_obj.emp_id = data_dict.get('emp_id')
    timesheet_obj.create_date = ut_get_localdate(timesheet_obj.create_date)
    timesheet_obj.update_user = user_id
    timesheet_obj.update_date = ut_get_timezone_now()
    try:
        timesheet_obj.save()
        logger.info(f'勤務表情報テーブル更新 {timesheet_id} : {timesheet_obj.pdf_name}')
    except Exception:
        logger.exception(f'TtEvidence update exception {timesheet_id} : {timesheet_obj.pdf_name}')
        return False
    return timesheet_id

# JAふくおか八女 文書情報テーブル更新
def svf_update_jafyame(jafyame_id, data_dict, user_id):
    try:
        jafyame_obj = TtJafyame.objects.get(jafyame_id=jafyame_id)
    except TtJafyame.DoesNotExist:
        logger.exception(f'TtJafyame DoesNotExist {jafyame_id=}')
        return False
    new_dept =  data_dict.get('dept')
    new_section = data_dict.get('section')
    pre_dept = jafyame_obj.dept
    pre_section = jafyame_obj.section
    if new_dept != pre_dept or new_section != pre_section:
        filepath = jafyame_obj.file_path
        pdf_name = jafyame_obj.pdf_name,
        # JAふくおか八女 部課フォルダに移動
        filepath = svf_move_uploadfile_jafyame(filepath, new_dept, new_section)
        jafyame_obj.file_path = filepath

    jafyame_obj.processed_date = data_dict.get('processed_date')
    jafyame_obj.dept = data_dict.get('dept')
    jafyame_obj.section = data_dict.get('section')
    jafyame_obj.spine = data_dict.get('spine')
    jafyame_obj.username = data_dict.get('username')
    jafyame_obj.create_date = ut_get_localdate(jafyame_obj.create_date)
    jafyame_obj.update_user = user_id
    jafyame_obj.update_date = ut_get_timezone_now()
    try:
        jafyame_obj.save()
        if new_dept != pre_dept or new_section != pre_section:
            images = [svf_get_jafyame_imagepath(pre_dept, pre_section, jafyame_id, 1)]
            move_images('jafyame', images, jafyame_id)  # JAふくおか八女 部課imgフォルダに移動

        logger.info(f'JAふくおか八女文書情報テーブル更新 {jafyame_id} : {jafyame_obj.pdf_name}')
    except Exception:
        logger.exception(f'TtEvidence update exception {jafyame_id} : {jafyame_obj.pdf_name}')
        return False
    return jafyame_id
# エントリー テキストデータ更新
def svf_update_entry(entry_id, entry_pages, user_id):
    try:
        entry = TtEntry.objects.get(entry_id=entry_id)
    except TtEntry.DoesNotExist:
        logger.exception(f'TtEntry DoesNotExist {entry_id=}')
        return False
        # raise ValueError('エントリー テキストデータ更新エラー!')
    json_text = get_jsontext(entry.entry_detail, entry_pages)
    # json_text = get_jsontext(ocrform_obj.ocrform_text, entry_pages)

    entry.entry_detail = json_text
    # entry.entry_detail = json_str
    entry.create_date = ut_get_localdate(entry.create_date)
    entry.update_user = user_id
    entry.update_date = ut_get_timezone_now()

    try:
        entry.save()
        logger.info(f'update entry_detail {entry_id} : {entry.pdf_name}')
    except Exception:
        logger.exception(f'update entry_detail exception {entry_id} : {entry.pdf_name}')
        return False

    return entry_id
# ブラウザでの編集内容をテキスト情報にマージ
def get_jsontext(ocrform_text, ocrdata_pages):
    # json.loads 関数 JSON 形式の文字列データから、Python オブジェクト(dict, list)を作成 
    object_list = json.loads(ocrform_text) # JSONデータをPythonオブジェクト(list型)へ変換
    if object_list:
        try:
            for i, file in enumerate(ocrdata_pages):
                texts = file.get('text') # ページごとの編集内容
                page_no = i + 1
                if texts:
                    for pagedata in object_list:
                        if pagedata.get('page_no') == str(page_no):
                            list = pagedata.get('page_list')
                            for text in texts:
                                item_name = text.get('item_name')
                                item_json = text.get('item_json')
                                for item in list:
                                    if item_name == item.get('item_name') and item_json == item.get('item_json'):
                                        item['item_text'] = text.get('item_text')   # ブラウザからの内容を設定
                                        break
        except Exception:
            logger.exception('jsontext exception')
    json_str = sv_datas2json(object_list) # リストをjsonデータに

    return json_str

# Ocr文書 テキストデータ更新
def svf_update_shiori(model_name, ocrdata_id, fulltext, user_id):
    model_class = MODEL_CLASSES.get(model_name)
    if not model_class:
        return False
    try:
        q_objects = ''
        if model_name == 'ocrdata':
            q_objects = Q(ocrdata_id=ocrdata_id)
        elif model_name == 'timesheet':
            q_objects = Q(timesheet_id=ocrdata_id)
        elif model_name == 'entry':
            q_objects = Q(entry_id=ocrdata_id)            
        elif model_name == 'jafyame':   # JAふくおか八女
            q_objects = Q(jafyame_id=ocrdata_id)
        ocrdata_obj = model_class.objects.filter(q_objects).first()
    except model_class.DoesNotExist:
        logger.exception(f'{model_name=} DoesNotExist {ocrdata_id}')
        return False
    if not ocrdata_obj:
        return False
        # raise ValueError('Ocr文書 テキストデータ更新エラー!')
    # json_text = get_jsontext(ocrdata.form_detail, ocrdata_pages)

    # ocrdata.form_detail = json_text
    ocrdata_obj.pdf_handbook = fulltext
    ocrdata_obj.create_date = ut_get_localdate(ocrdata_obj.create_date)
    ocrdata_obj.update_user = user_id
    ocrdata_obj.update_date = ut_get_timezone_now()

    try:
        ocrdata_obj.save()
        logger.info(f'update {model_name=} detail {ocrdata_id} : {ocrdata_obj.pdf_name}')
    except Exception:
        logger.exception(f'update {model_name=} detail exception {ocrdata_id} : {ocrdata_obj.pdf_name}')
        return False

    return ocrdata_id
# Ocr文書情報削除
def svf_delete_ocrdata(model_name, ocrdata_id, user_id, owner_id):
    # owner_id = get_owner_id(user_id)
    if not owner_id:
        # raise ValueError('Ocr文書削除 owner_id エラー! ' + entry_id)
        logger.error(f'owner_id error {model_name=} {owner_id=}')
        return False
    model_class = MODEL_CLASSES.get(model_name)
    if not model_class:
        return False
    try:
        q_objects = ''
        if model_name == 'ocrdata':
            q_objects = Q(ocrdata_id=ocrdata_id)
        elif model_name == 'timesheet':
            q_objects = Q(timesheet_id=ocrdata_id)
        elif model_name == 'entry':
            q_objects = Q(entry_id=ocrdata_id)
        elif model_name == 'jafyame':   # JAふくおか八女
            q_objects = Q(jafyame_id=ocrdata_id)
        ocrdata_obj = model_class.objects.get(q_objects)
    except model_class.DoesNotExist:
        logger.exception(f'{model_name=} DoesNotExist {ocrdata_id}')
        return False
        # raise ValueError('Ocr文書情報削除　取得エラー ' + entry_id)
    try:
        page_cnt = 1
        cnt = sv_get_pdfpages(ocrdata_obj.file_path)
        if cnt and 0 < cnt:
            page_cnt = cnt

        dest_file = ocrdata_obj.file_path
        other_obj = model_class.objects.filter(file_path=ocrdata_obj.file_path).exclude(q_objects).first()

        # rootfolder = get_rootfolder(owner_id)
        for i in range(1, page_cnt + 1):
            if model_name == 'jafyame': # JAふくおか八女 部課imgフォルダ
                file_name = svf_get_jafyame_imagepath(ocrdata_obj.dept, ocrdata_obj.section, ocrdata_id, i)
            else:
                file_name = svf_get_ocrdata_imagepath(model_name, ocrdata_obj.processed_ym, ocrdata_id, i)
            sv_delete_file(file_name)   # 画像ファイルを削除

        if dest_file and not other_obj:
            sv_delete_file(dest_file)   # ファイルを削除
            # jsonファイル
            rootfolder = svf_get_ocrdata_rootfolder(model_name)   # ルートフォルダを取得
            if rootfolder:
                json_dir = get_jsonfolder(rootfolder)
                if json_dir:
                    # sv_delete_fulltext(json_dir, dest_file)    # json全文データから削除
                    basename_without_ext = os.path.splitext(os.path.basename(dest_file))[0]
                    jsonfile = os.path.join(json_dir, basename_without_ext + '.json').replace(os.sep,'/')
                    sv_delete_file(jsonfile)   # jsonファイルの削除
    except Exception:
        logger.exception(f' exception {model_name=} {ocrdata_id=}')
    filename = ocrdata_obj.pdf_name
    ocrdata_obj.delete()    # Ocr文書情報テーブルから削除
    logger.info(f'Ocr文書情報削除 {model_name=} {ocrdata_id} : {filename}')

    return filename
# 検索条件で絞り込み
def svf_filter_timesheet(request, queryset):
    try:
        office_name = request.GET.get('office_name')
        if office_name:
            queryset = queryset.filter(office_name__contains=office_name)
        emp_id = request.GET.get('emp_id')
        if emp_id and 0 < len(emp_id):
            queryset = queryset.filter(emp_id=emp_id)
        emp_name = request.GET.get('emp_name')
        if emp_name:
            queryset = queryset.filter(emp_name__contains=emp_name)
        # 取引日: yyyy/mm/dd
        date_from = request.GET.get('process_date1')
        date_to = request.GET.get('process_date2')
        if date_from and date_to:
            queryset = queryset.filter(target_date__range=[date_from, date_to]).order_by('target_date')
        elif date_from:
            queryset = queryset.filter(target_date__gte=date_from).order_by('target_date')
        elif date_to:
            queryset = queryset.filter(target_date__lte=date_to).order_by('target_date')
    except Exception:
        logger.exception('svf_filter_timesheet exception')
    return queryset
# JAふくおか八女 検索条件で絞り込み
def svf_filter_jafyame(request, queryset):
    try:
        dept = request.GET.get('dept')
        if dept:
            queryset = queryset.filter(dept__contains=dept)
        section = request.GET.get('section')
        if section:
            queryset = queryset.filter(section__contains=section)
        spine = request.GET.get('spine')
        if spine:
            queryset = queryset.filter(spine__contains=spine)
        username = request.GET.get('username')
        if username:
            queryset = queryset.filter(username__contains=username)
        # if emp_id and 0 < len(emp_id):
        #     queryset = queryset.filter(emp_id=emp_id)
        # 取引日: yyyy/mm/dd
        date_from = request.GET.get('process_date1')
        date_to = request.GET.get('process_date2')
        if date_from and date_to:
            queryset = queryset.filter(processed_date__range=[date_from, date_to]).order_by('processed_date')
        elif date_from:
            queryset = queryset.filter(processed_date__gte=date_from).order_by('processed_date')
        elif date_to:
            queryset = queryset.filter(processed_date__lte=date_to).order_by('processed_date')
    except Exception:
        logger.exception('svf_filter_jafyame exception')
    return queryset

# アクセスログ記録	
def svf_create_access_log(owner_id, user_id, doc_id, action):
    # TtAccessLog.objects.create(user_id=user_id, document_id=doc_id, action='download')	
    try:
        now = ut_get_timezone_now()
        obj = TtAccessLog(
            owner_id = owner_id,
            access_user = user_id,
            document_id = doc_id,
            # accessed_at = create_date,  # auto_now_add
            action = action,
            create_date = now,
            create_user = user_id,
            update_user = user_id,
            update_date = now
        )
        obj.save()
        logger.info(f'TtAccessLog save {id} : {doc_id=}')
    except Exception:
        logger.exception(f'TtAccessLog save exception {doc_id=}')
        return False
