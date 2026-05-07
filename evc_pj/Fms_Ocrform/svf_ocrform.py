import os
import datetime
import shutil
import logging
import json
import subprocess

# import pypdf
# import math
# import threading

# from pdfminer.converter import PDFPageAggregator
# from pdfminer.layout import LAParams, LTContainer, LTTextBox
# from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
# from pdfminer.pdfpage import PDFPage

from django.conf import settings
# from django.utils import timezone
# from django.utils.timezone import make_aware
from sequences import get_next_value

from Fms_Ocrform.models import TtOcrform

from commons.utils import ut_get_localdate

from Evc_App.sv_file import (TextData,TextDatas,
    make_dir,get_imgfolder_upload,get_jsonfolder,sv_delete_file
)
from Evc_App.sv_create_image import sv_create_ocr_image
# from Evc_App.sv_extract_text import sv_extract_text
from Evc_App.sv_json import sv_save_json,sv_json2textdatas,sv_datas2json,sv_save_detect_json
from Evc_App.sv_get_image_shape import sv_get_contour_rect,sv_get_pdfpages

OCR_DPI = 200     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う
YTHRESHOLD = 8  # 1mm : 10 / 254 * 200
# OCR_DPI = 300     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う
# YTHRESHOLD = 12  # 1mm : 10 / 254 * 300

logger = logging.getLogger(__name__)

# EVCルートフォルダを取得(フォーム)
def get_ocrform_rootfolder():
    root_folder = getattr(settings, 'EVC_ROOT')#.lower()
    # root_folder = os.path.join(root_folder, 'Evc_Management').replace(os.sep,'/')

    logger.debug(f'ocrform rootfolder {root_folder}')
    return root_folder
# フォームファイルを保存するフォルダ作成
def make_ocrform_dir(rootfolder):
    path = os.path.join(rootfolder, 'ocrform_file').replace(os.sep,'/')
    make_dir(path)

# フォーム画像ファイルを保存するフォルダ作成
def make_ocrform_image_dir(rootfolder):
    path = os.path.join(rootfolder, 'ocrform_image').replace(os.sep,'/')
    make_dir(path)

# フォーム画像名：フォームID　+ _001(連番).jpg
def get_ocrform_imagefile(img_dir, ocrform_id, page_no):
    file_name =  os.path.join(img_dir, ocrform_id + '_{:03d}.jpg'.format(page_no)).replace(os.sep,'/')
    if not os.path.exists(file_name):
        page_no = 1
        file_name =  os.path.join(img_dir, ocrform_id + '_{:03d}.jpg'.format(page_no)).replace(os.sep,'/')
    return file_name

# フォームファイルを保存するフォルダ
def get_ocrform_file_dir(rootfolder):
    abs_path = os.path.join(rootfolder, 'ocrform_file').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''
# フォーム画像ファイルを保存するフォルダ
def get_ocrform_image_dir(rootfolder):
    abs_path = os.path.join(rootfolder, 'ocrform_image').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''

# フォームエリア情報から指定ページの枠座標を取得しjson文字列に
# [{ 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'text':text },{}...]
def svf_get_area_jsonstr(ocrform_area, page_no):
    dicts = []
    jsonareas = ''
    if ocrform_area:
        try:
            areadatas = sv_json2textdatas(ocrform_area)
            for pagedata in areadatas:
                if pagedata.page_no == page_no:
                    for textdata in pagedata.textdata_list:
                        x1 = textdata.x1
                        y1 = textdata.y1
                        x2 = textdata.x2
                        y2 = textdata.y2
                        text = textdata.text
                        if x2 != 0 and y2 != 0:
                            dicts.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'text':text})
            jsonareas = json.dumps(dicts)
            # logger.debug('sv_get_area_jsonstr  : ' + jsontext + ':' + ocrform_id)
        except Exception:
            logger.exception('svf_get_area_jsonstr exception ')
    return jsonareas
def svf_get_form_area(ocrform_id):
    try:
        ocrform_obj =  TtOcrform.objects.get(ocrform_id=ocrform_id)
        ocrform_area = ocrform_obj.ocrform_area
    except TtOcrform.DoesNotExist:
        ocrform_area = ''
    return ocrform_area
# フォーム情報作成
def svt_create_ocrform(uploadfiles, user_id, owner_id, rootfolder, data_type, analyze_pdf=False):
    lists = []
    error_lists = []
    evi_lists = []
    img_upload_dir = get_imgfolder_upload(rootfolder)
    if not img_upload_dir:
        logger.error(f'upload imgfolder error {rootfolder=}')
        return lists, error_lists, evi_lists
    # json_upload_dir = get_jsonfolder_upload(rootfolder)
    # if not json_upload_dir:
    #     return
    # img_dir = get_imgfolder(rootfolder)
    # img_dir = get_media_image_dir()
    json_dir = get_jsonfolder(rootfolder)

    areas = []
    area_textdatas = []
    # for path in files:
    for uploadfile in uploadfiles:
        filename = uploadfile.get('name')
        path = uploadfile.get('path')
        # フォームのフォルダに保存
        new_path = move_ocrform_file(path, rootfolder, filename).replace(os.sep, '/')
        # contour_json = ''
        # contour_images = []
        ocrimages = sv_create_ocr_image(new_path, img_upload_dir, -1)
        
        if ocrimages:
            area_textdatas = []
            # if analyze_pdf:
            #     # 矩形領域を抽出
            #     try:
            #         for i, imagepath in enumerate(ocrimages, start=1):
            #             page_textdatas = sv_get_contour_rect(imagepath, i)
            #             area_textdatas.extend(page_textdatas)
            #             # contour_images.append(rect_image)
            #         # if area_textdatas:
            #         #     areas = get_areas(area_textdatas)
            #         #     if settings.DEBUG:
            #         #       　basename_without_ext = os.path.splitext(os.path.basename(new_path))[0]
            #         #       　contour_json = basename_without_ext + '_contour.json'
            #         #         # TextDatasをjsonファイルに保存
            #         #         contour_json = sv_save_json(contour_json, area_textdatas, json_dir)
            #     except Exception:
            #         logger.exception(f'sv_get_contour_rect exception {new_path}')
        else:   # パスワード設定などにより読み込めない
            logger.error(f'ocrimages False {filename=}')
            error_lists.append(filename)
            sv_delete_file(new_path)    # アップロードファイル削除
            continue

        page_count = len(ocrimages) if ocrimages else 1
        detecttext_list = []
        textdatas = []
        # if analyze_pdf:
        #     # PDFファイルからテキスト情報を取得(別プロセスで処理する)
        #     textdatas = get_pdf_text(new_path, json_dir, page_count)
        # # else:
        # #     areas_dict = {}
        # #     # OCR機能を使って、テキスト抽出しTextDataデータに変換
        # #     textdatas, detecttext_list, google_cnt = sv_extract_text(ocrimages, areas_dict, None)
        # #     logger.debug('extract text : '  + filename)

        ocrform_id = get_ocrform_id(data_type)
        save_id = False
        if page_count == 1:
            imgfile = ocrimages[0] if ocrimages else None
            save_id = create_ocrform_page(new_path, area_textdatas, textdatas, -1, user_id, owner_id, ocrform_id, imgfile)
        else:
            for page_no in range(1, 2): # 先頭ページのみ
                imgfile = ocrimages[page_no - 1]
                id = create_ocrform_page(new_path, area_textdatas, textdatas, -1, user_id, owner_id, ocrform_id, imgfile)
                if id and not save_id:
                    save_id = id

        if save_id:
            lists.append(uploadfile)
            evi_lists.append(save_id)
            # logger.info('create evidence data : ' + save_id + ' : ' +  filename)
            move_image(owner_id, ocrimages, save_id)    # MOVE
            if settings.DEBUG:
                # move_contour_file(owner_id, contour_json, contour_images, save_id)
                # jsonファイルを保存
                if textdatas:
                    basename_without_ext = os.path.splitext(os.path.basename(new_path))[0]
                    file_name =  basename_without_ext + '.json'
                    sv_save_json(file_name, textdatas, json_dir)
                    # sv_save_fulltext(new_path, textdatas, json_dir)
                if detecttext_list:
                    sv_save_detect_json(ocrform_id, detecttext_list, json_dir)
        else:
            error_lists.append(filename)
            sv_delete_file(new_path)    # アップロードファイル削除
            delete_files(ocrimages)
            logger.error(f'create ocrform error {filename}')
        # OCR機能で使用した画像ファイルを削除
        # basename_without_ext, ext_name = os.path.splitext(os.path.basename(path))
        # if ocrimages and ext_name.lower() == '.pdf':
        #     delete_files(ocrimages)
    return lists, error_lists, evi_lists
# def get_areas(contour_path, json_dir):
#     textdatas = sv_load_jsonfile(contour_path, json_dir)
# def get_areas(textdatas):
#     areas = []
#     try:
#         for pagedata in textdatas:
#             if pagedata.page_no == 1:
#                 for textdata in pagedata.textdata_list:
#                     x1 = textdata.x1
#                     y1 = textdata.y1
#                     x2 = textdata.x2
#                     y2 = textdata.y2
#                     if x2 != 0 and y2 != 0:
#                         areas.append((x1, y1, x2, y2))
#     except Exception:
#         logger.exception('exception get_areas ')
#     return areas

# 領域情報・項目情報を作成しフォーム情報登録
def create_ocrform_page(filepath, area_textdatas, textdatas, page_no, user_id, owner_id, ocrform_id, imgfile):
    save_id = False
    # 領域情報
    area_pagedatas = []
    if area_textdatas:
        for pagedata in area_textdatas:
            if page_no == -1 or pagedata.page_no == page_no:
                area_pagedatas.append(pagedata)
    # 項目情報
    pagedatas = []
    if textdatas:
        for pagedata in textdatas:
            if page_no == -1 or pagedata.page_no == page_no:
                pagedatas.append(pagedata)

    # json形式でフォーム情報を、DBに保存する
    if area_pagedatas:
        rect_str = sv_datas2json(area_pagedatas)
    else:
        rect_str = ''
    if pagedatas:
        json_str = get_ocrform_text(pagedatas)
    else:
        json_str = ''
    # フォーム情報テーブル登録
    id = svt_save_ocrform(user_id, owner_id, filepath, rect_str, json_str, ocrform_id)
    if id:
        save_id = id
    return save_id

# TextDatasからフォーム情報をjson文字列で取得
def get_ocrform_text(textdatas):
    lists = []
    json_str = ''
    try:
        item_no = 1
        text = ''
        for pagedata in textdatas:
            # area_no = pagedata.area_no
            # if area_no % 2 == 0:
            #     area = str(area_no)
            #     data = {
            #         'item_no': str(item_no),
            #         'item_name': text,
            #         'area_no': area,
            #         'result': '',
            #     }
            #     lists.append(data)
            #     item_no += 1
            #     text = ''
            # else:
            #     if pagedata.textdata_list:
            #         for textdata in pagedata.textdata_list:
            #             text += textdata.text
            pagelists = []
            area_no = 0
            if pagedata.textdata_list:
                for textdata in pagedata.textdata_list:
                    text = textdata.text
                    area = str(area_no)
                    data = {
                        'item_no': str(item_no),
                        'item_name': text,
                        'area_no': '',  # area,
                        'item_json': '',
                        'table_id': '',
                    }
                    pagelists.append(data)
                    item_no += 1
            data = {
                'page_no': str(pagedata.page_no),
                'page_list':pagelists
            }
            lists.append(data)
        json_str = sv_datas2json(lists) # リストをjsonデータに
        # logger.debug('get_image_shape  : ' + jsontext + ':' + ocrform_id)
    except Exception:
        logger.exception('get_ocrform_text exception')
    return json_str
# 複数ファイルを削除
def delete_files(files):
    if files:
        for file in files:
            if file:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                except Exception:
                    logger.exception(f'sv_delete_file exception {file=}')
            
# 画像ファイルをフォーム画像フォルダにファイル名を設定して移動
def move_image(owner_id, ocrimages, ocrform_id):
    if not ocrimages or not ocrform_id:
        return
    for i, imagepath in enumerate(ocrimages, start=1):
        if not imagepath or not os.path.exists(imagepath):
            continue
        try:
            # rootfolder = get_rootfolder(owner_id)
            rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
            img_dir = get_ocrform_image_dir(rootfolder)
            # フォーム画像名
            file_name = os.path.join(img_dir, ocrform_id + '_{:03d}.jpg'.format(i)).replace(os.sep,'/')

        # logger.debug('dest_dir  : ' +  (dest_dir or 'False'))
        # new_path = shutil.move(file, dest_dir)
        # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
        # basename = os.path.basename(file)
            new_path = shutil.move(imagepath, file_name)
            logger.debug(f'move imagefile {imagepath} --> {new_path}')
        except Exception:   # ValueError
            logger.exception(f'move_image exception {ocrform_id=} page={i}')
# フォームのフォルダに保存
def move_ocrform_file(filepath, rootfolder, basename):
    new_path = filepath
    if not os.path.exists(filepath):
        return new_path
    try:
        if rootfolder:
            ocrform_dir = get_ocrform_file_dir(rootfolder)
            dest_file = os.path.join(ocrform_dir, basename).replace(os.sep,'/')
        else:
            dest_file = False

        logger.debug(f'{dest_file=}')

        if dest_file:
        # new_path = shutil.move(file, dest_dir)
        # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
            # basename = os.path.basename(file)
            if dest_file != filepath:
                dest_file = check_filename(dest_file)
                new_path = shutil.move(filepath, dest_file)
        logger.info(f'move file {filepath} --> {new_path}')
    except Exception:
        logger.exception(f'move_ocrform_file exception {filepath}')

    return new_path

# 同じファイル名が存在する場合　'(連番)'　追加
def check_filename(file):
    if os.path.exists(file):
        # dt = datetime.datetime.fromtimestamp(os.path.getmtime(file))
        # dt_now = datetime.datetime.now()
        # if dt.year != dt_now.year or dt.month != dt_now.month or dt.day != dt_now.day:
        filepath, ext = os.path.splitext(file)
        i = 1
        while i < 100000:
            new_path = '{}({}){}'.format(filepath, i, ext)
            if not os.path.exists(new_path):
                return new_path
            i += 1
        logger.error(f'same file over 100000 {file}')
    return file
# フォーム情報テーブルIDを取得
def get_ocrform_id(data_type):
    # ocrform_id：ofrm_連番(00001～)

    d = datetime.date.today().strftime('%Y%m%d')
    try:
        # シーケンス採番
        # num = get_next_value(d)
        if data_type == 1:
            num = get_next_value('ocrform_seq')
            id = 'ofrm' + '_{:05d}'.format(num)
        else:
            num = get_next_value('fmsform_seq')
            id = 'fmsf' + '_{:05d}'.format(num)
    except Exception:   # ValueError
        if data_type == 1:
            id = 'ofrm' + '_00001'
        else:
            id = 'fmsf' + '_00001'
        logger.exception('get_next_value exception')

    return id
# フォーム情報テーブル登録
def svt_save_ocrform(user_id, owner_id, filepath, jsonpos, jsontext, ocrform_id):
    # basename_without_ext, ext_name = os.path.splitext(os.path.basename(pdffile))
    try:
        basename = os.path.basename(filepath)
        # d = datetime.date.today().strftime('%Y%m%d')
        create_date = datetime.datetime.now()
        create_user_id = user_id
        id = ocrform_id    # get_ocrform_id()

        obj = TtOcrform(
            ocrform_id=id,
            ocrform_name=basename,
            owner_id=owner_id,
            ocrform_path=filepath,
            ocrform_area=jsonpos,
            ocrform_text=jsontext,
            create_date=create_date,    # DateTimeField
            create_user=create_user_id,
            update_user=create_user_id,
            update_date=create_date     # DateTimeField
        )
        obj.save()
        logger.info(f'TtOcrform save {id} : {basename}')
    except Exception:
        logger.exception(f'TtOcrform save exception {filepath}')
        return False
    return id
# フォーム情報テーブル更新
def svt_update_ocrform(ocrform_id, user_id, form_pages):
    try:
        # lists = sv_json2textdatas(json_str)
        # lists = json.loads(json_str)

        ocrform_obj = TtOcrform.objects.get(ocrform_id=ocrform_id)
    except TtOcrform.DoesNotExist:
        logger.exception(f'TtOcrform DoesNotExist {ocrform_id=}')
        return False
    
    json_area = get_jsonareas(ocrform_obj.ocrform_area, form_pages)
    json_text = get_jsontext(ocrform_obj.ocrform_text, form_pages)

    ocrform_obj.ocrform_area = json_area
    ocrform_obj.ocrform_text = json_text
    ocrform_obj.create_date = ut_get_localdate(ocrform_obj.create_date)
    ocrform_obj.update_user = user_id
    ocrform_obj.update_date = datetime.datetime.now()

    try:
        ocrform_obj.save()
        logger.info(f'TtoOrform update {ocrform_id} : {ocrform_obj.ocrform_name}')
    except Exception:
        logger.exception(f'TtOcrform update exception {ocrform_id} : {ocrform_obj.ocrform_name}')
        return False
    return ocrform_id
# 編集内容を領域情報にマージ
def get_jsonareas(ocrform_area, form_pages):
    areadatas = sv_json2textdatas(ocrform_area)
    lists = []
    for i, file in enumerate(form_pages):
        area = file.get('area')
        bounds = []
        textdatas = []
        page_no = i + 1
        if area:
            try:
                postext = json.loads(area)
                # dict { 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'text': text }
                for pos in postext:
                    x1 = int(pos.get('x1','0'))
                    y1 = int(pos.get('y1','0'))
                    x2 = int(pos.get('x2','0'))
                    y2 = int(pos.get('y2','0'))
                    text = pos.get('text')
                    if x2 != 0 and y2 != 0:
                        bounds.append(TextData(x1, y1, x2, y2, text))
                textdatas.append(TextDatas(1, page_no, 1, 100, 100, bounds))
            except Exception:
                logger.exception(f'jsonpos exception {area}')
            if textdatas:
                if areadatas:
                    for pagedata in areadatas:
                        if pagedata.page_no == page_no:
                            pagedata.textdata_list = textdatas[0].textdata_list
                else:
                    data = {
                        'page_no': page_no,
                        'textdata_list':textdatas[0].textdata_list
                    }
                    lists.append(data)
                
    # jsonデータでフォーム情報を、DBに保存する
    if areadatas:
        rect_str = sv_datas2json(areadatas)
    else:
        if lists:
            rect_str = sv_datas2json(lists)
        else:
            rect_str = ''
    return rect_str
# 編集内容をテキスト情報にマージ
def get_jsontext(ocrform_text, form_pages):
    # json.loads 関数 JSON 形式の文字列データから、Python オブジェクト(dict, list)を作成 
    if ocrform_text:
        object_list = json.loads(ocrform_text) # JSONデータをPythonオブジェクト(list型)へ変換
    else:
        object_list = None
    if object_list:
        try:
            for i, file in enumerate(form_pages):
                text = file.get('text')
                page_no = i + 1
            # lists = []
                if text:
                    for pagedata in object_list:
                        if pagedata.get('page_no') == str(page_no):
                            pagedata['page_list'] = text
            #         data = {
            #             'page_no': str(page_no),
            #             'page_list':json.loads(jsontext)
            #         }
            #         lists.append(data)
            #     else:
            #         lists.append(pagedata)
            # object_list = lists
        except Exception:
            logger.exception('jsontext exception')
    else:
        try:
            lists = []
            for i, file in enumerate(form_pages):
                text = file.get('text')
                page_no = i + 1
                if text:
                    data = {
                        'page_no': str(page_no),
                        'page_list':text
                    }
                    lists.append(data)
            #     else:
            #         lists.append(pagedata)
            object_list = lists
        except Exception:
            logger.exception('jsontext exception')
    json_str = sv_datas2json(object_list) # リストをjsonデータに

    return json_str

# フォーム情報削除
def svt_delete_ocrform(ocrform_id, user_id, owner_id):
    # if not owner_id:
    #     # raise ValueError('フォーム削除 owner_id エラー! ' + ocrform_id)
    #     logger.error('owner_id error: ' + (owner_id or 'None'))
    #     return False
    try:
        ocrform_obj = TtOcrform.objects.get(ocrform_id=ocrform_id)
    except TtOcrform.DoesNotExist:
        logger.exception(f'TtOcrform DoesNotExist {ocrform_id=}')
        return False
        # raise ValueError('フォーム情報削除　取得エラー ' + ocrform_id)
    try:
        page_cnt = 1
        cnt = sv_get_pdfpages(ocrform_obj.ocrform_path)
        if cnt and 0 < cnt:
            page_cnt = cnt

        sv_delete_file(ocrform_obj.ocrform_path)   # ファイルを削除
        # rootfolder = get_rootfolder(owner_id)
        rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
        img_dir = get_ocrform_image_dir(rootfolder)
        for i in range(1, page_cnt + 1):
            file_name =  os.path.join(img_dir, ocrform_id + '_{:03d}.jpg'.format(i)).replace(os.sep,'/')
            sv_delete_file(file_name)   # フォーム画像ファイルを削除
            # file_name =  os.path.join(img_dir, ocrform_id + '_{:02d}_contour.jpg'.format(i)).replace(os.sep,'/')
            # sv_delete_file(file_name)   # フォーム画像ファイルを削除
        # jsonファイル
        if rootfolder:
            json_dir = get_jsonfolder(rootfolder)
            if json_dir:
                jsonfile = os.path.join(json_dir, ocrform_id + '.json').replace(os.sep,'/')
                sv_delete_file(jsonfile)   # jsonファイルの削除
                # jsonfile = os.path.join(json_dir, ocrform_id + '_contour.json').replace(os.sep,'/')
                # sv_delete_file(jsonfile)   # jsonファイルの削除
    except Exception:
        logger.exception(f'exception {ocrform_id=}')
    filename = ocrform_obj.ocrform_name
    try:
        ocrform_obj.delete()    # フォーム情報テーブルから削除
        logger.info(f'フォーム情報削除 {ocrform_id=} : {filename}')
    except Exception:
        logger.exception(f'object delete exception {ocrform_id=}')
        filename = False
    return filename

# フォーム情報テーブルエリア読込
# def sv_get_ocrform_areadatas(ocrform_id):
#     logger.debug('フォーム情報テーブエリア読込  : ' + ocrform_id)
#     textdatas = []
#     try:
#         ocrform_obj = TtOcrform.objects.get(ocrform_id=ocrform_id)
#     except TtOcrform.DoesNotExist:
#         ocrform_obj = None
#     if ocrform_obj:
#         if ocrform_obj.ocrform_area:
#             textdatas = sv_json2textdatas(ocrform_obj.ocrform_area)
#     return textdatas
# フォーム情報テーブル読込
# def sv_get_ocrform_textdatas(ocrform_id):
#     logger.debug('フォーム情報テーブル読込  : ' + ocrform_id)
#     textdatas = []
#     try:
#         ocrform_obj = TtOcrform.objects.get(ocrform_id=ocrform_id)
#     except TtOcrform.DoesNotExist:
#         ocrform_obj = None
#     if ocrform_obj:
#         if ocrform_obj.ocrform_text:
#             textdatas = sv_json2textdatas(ocrform_obj.ocrform_text)
#     return textdatas

# PDFファイルからテキストと情報を取得 
def get_pdf_text(pdf_file, json_dir, page_count):
    textdatas = []
    """
    別プロセスで処理する
    """
    # print('start'+ datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'))
    logger.debug(f'get pdf text start {datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")}')
    basename_without_ext = os.path.splitext(os.path.basename(pdf_file))[0]
    jsonfile = os.path.join(json_dir, basename_without_ext + '_sub.json').replace(os.sep,'/')
    # cmd = 'python Fms_Ocrform/sample.py --path ' + pdf_file
    # cmd = '..\\venv\\scripts\\python Fms_Ocrform/sample.py --path "' + pdf_file + '" --json "' + jsonfile + '"'
    cmd = ['..\\venv\\scripts\\python', 'Fms_Ocrform/sample.py']
    cmd.append(pdf_file)
    cmd.append(jsonfile)

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # print(f'returncode: {result.returncode},stdout: {result.stdout},stderr: {result.stderr}')
    # print('end'+ datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'))
    logger.debug(f'get pdf text end {datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")}')
    if result.returncode == 0:
        if os.path.exists(jsonfile):
            try:
                with open(jsonfile, 'r', encoding='utf-8') as f:
                    json_str = f.read()
                    if json_str:
                        textdatas = sv_json2textdatas(json_str)
                        if textdatas:
                            textdatas = sort_textdatas(textdatas, page_count)

                logger.debug(f'json read {basename_without_ext} : {len(textdatas)}')
            except Exception:
                logger.exception(f'json read exception {basename_without_ext}')
    else:
        logger.info(f'subprocess return {result.returncode}')
    sv_delete_file(jsonfile)

    """
    別スレッドで処理する
    時間がかかる
    """
    # results = dict()
    # thread = threading.Thread(target=get_pdf_text_thread,
    #                     args=(pdf_file, results), name='evc_pdfthread')
    # print('start'+ datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'))
    # thread.start()  # エビデンス情報作成(別スレッド)
    # thread.join()
    # print('end'+ datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'))
    # print(results)
    return textdatas

def sort_textdatas(textdatas, page_count):
    datas = textdatas
    for page_no in range(1, page_count + 1):
        try:
            for pagedata in datas:
                if pagedata.page_no == page_no:
                    pagedata.textdata_list = sort_bounds(pagedata.textdata_list)
        except Exception:
            logger.exception('sort_textdatas exception')
    return datas

def sort_bounds(bounds):
    lines = []
    bounds.sort(key=lambda x: x.y1)
    pre_y = -1
    firstLoop = True
    threshold = YTHRESHOLD
    linebounds = []
    for bound in bounds:
        y1 = bound.y1
        if firstLoop:
            firstLoop = False
            pre_y = y1
        else:
            if pre_y - threshold <= y1 <= pre_y + threshold:
                pre_y = y1
            else:
                if 0 < len(linebounds):
                    linebounds.sort(key=lambda x: x.x1)
                    lines.append(linebounds)
                linebounds = []
                pre_y = y1
        linebounds.append(TextData(bound.x1, bound.y1, bound.x2, bound.y2, bound.text))
    if 0 < len(linebounds):
        linebounds.sort(key=lambda x: x.x1)
        lines.append(linebounds)
    page_textdatas = []
    for line in lines:
        for bound in line:
            page_textdatas.append(bound)
    return page_textdatas

"""
別スレッドで処理する
時間がかかる
def get_pdf_text_thread(pdf_file, results):
    pdf_reader = pypdf.PdfReader(pdf_file)
    page_num = len(pdf_reader.pages)
    page_width = 0
    page_height = 0
 
    for p in pdf_reader.pages:
        p_size = p.mediabox
        p_width = p_size.width
        p_height = p_size.height
        page_width = math.ceil(p_width / 72 * 200)
        page_height = math.ceil(p_height / 72 * 200)
        break
    
    textdatas = []
    with open(pdf_file, "rb") as f:
        pdfPages = PDFPage.get_pages(f)
        # #文字読み取りのルール指定
        # laParams = LAParams(line_overlap = 0.5,
        #                     word_margin  = 0.1,
        #                     char_margin  = 2,
        #                     line_margin  = 0.5,
        #                     detect_vertical = True)
        laParams = LAParams(detect_vertical=True)
        resourceManager = PDFResourceManager()
        device = PDFPageAggregator(resourceManager, laparams=laParams)
        interpreter = PDFPageInterpreter(resourceManager, device)
        #ページごとに処理
        data = []
        for page in pdfPages:
            interpreter.process_page(page)
            layout = device.get_result()
            boxes = find_textboxes(layout)
            # dPoint / 72.0L * 96
            # dPoint / 72.0L * 200 DPI
            #テキストひとまとまりごとに処理
            for box in boxes:
                x0 = int(box.x0 / 72 * 200)
                x1 = int(box.x1 / 72 * 200)
                y0 = page_height - int(box.y1 / 72 * 200)
                y1 = page_height - int(box.y0 / 72 * 200)
                text = box.get_text().strip()
                data.append(TextData(x0, y0, x1, y1, text))
            break
        textdatas.append(TextDatas(1, 1, 1, page_width, page_height, data))
    return textdatas

def find_textboxes(layout):
    if isinstance(layout, LTTextBox):
        return [layout]
    elif isinstance(layout, LTContainer):
        boxes = []
        for child in layout:
            boxes.extend(find_textboxes(child))
        return boxes
    else:
        return []
"""
