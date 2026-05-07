import os
# import dataclasses
import datetime
import shutil
import logging
import json
# import random
# import io
# import csv
import zipfile
# import configparser
# import re
import cv2
import numpy as np

from urllib.parse import quote

# from typing import List
# from decimal import Decimal
# from django.conf import settings
# from django.utils import timezone
# from django.utils.timezone import make_aware
from sequences import get_next_value
from django.http import HttpResponse
from django.conf import settings

from Fms_Ocrform.models import TtOcrform,TtEntry

from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_file import (sv_delete_file,
    get_imgfolder_upload,
)
from Evc_App.sv_json import sv_save_detect_json,sv_datas2json,sv_json2textdatas
from Evc_App.sv_get_image_shape import sv_get_image_angle,sv_imwrite

from Fms_Ocrform.svf_ocrform import get_ocrform_rootfolder,get_ocrform_image_dir
from Fms_Ocrform.svf_common import (str2int,isint,zen2han,check_large,check_digits,
    svf_get_areas_dict,svf_draw_area,svf_get_json_text_page
)
from Fms_Ocrform.svf_extract_text import svf_extract_text
from Fms_Ocrform.svt_adjust_image import svt_get_matrix,svt_adjust_image_trapezoid

logger = logging.getLogger(__name__)

def make_trasafolder(rootfolder):
    trasa_path = os.path.join(rootfolder, 'trasa').replace(os.sep,'/')
    if not os.path.isdir(trasa_path):
        os.makedirs(trasa_path)   # 再帰的にディレクトリを作成する
        logger.debug(f'makedirs {trasa_path}')

def get_trasafolder(rootfolder):
    abs_path = os.path.join(rootfolder, 'trasa').replace(os.sep,'/')
    if os.path.exists(abs_path):
        return abs_path
    return ''
# 生産者コードでファイル名作成
# 出力年月日時分秒-生産者コード(5桁以下はゼロ埋め)-ランダム数8桁
def get_tnw_filename(seisansya_code):
    now = datetime.datetime.now()
    time = now.strftime('%Y%m%d%H%M%S')
    ym = now.strftime('%Y%m')
    try:
        # シーケンス採番
        num = get_next_value('trasa'+ym)
    except Exception:   # ValueError
        num = 1
    # 出力年月日時分秒-生産者コード(5桁以下はゼロ埋め)-ランダム数8桁
    # num = random.randrange(10**8, 10**9) 
    # name = time + '-{:05d}'.format(seisansya_code) + '-{:08d}'.format(num)
    name = time + '-' + seisansya_code + '-{:08d}'.format(num)
    return name

def obj_dict(obj):
    return obj.__dict__

# 連携JSONファイル出力
def save_tnwjson(json_dir, entry_detail, filename):
    jsonfile = ''
    if entry_detail:
        try:
            object_list = json.loads(entry_detail) # JSONデータをPythonオブジェクト(list型)へ変換
            for pagedata in object_list:
                page_no = str2int(pagedata.get('page_no'))
                if page_no < 1:
                    page_no = 1
                seisansya_code = 0
                field = []
                hiryo = []
                table_list = []
                line_dict = {}
                out_dict = {}
                table_json = ''
                items = pagedata.get('page_list')
                out_dict['image_filename'] = ''
                for item in items:
                    item_name = item.get('item_name')
                    item_json = item.get('item_json')
                    table_id = item.get('table_id')
                    item_text = zen2han(item.get('item_text'))
                    if item_json == 'code_h':
                        item_text = check_large(item_text)
                    else:
                        item_text = check_digits(item_text)
                    if table_id:
                        # ids = table_id.split('__')   # hiryo__1__date_y
                        # json名に '_'が含まれるため区別できるように'__'
                        if not item_json:
                            continue
                        if item_json == table_id:
                            table_json = item_json
                        else:
                            # line_dict = table_dict.get(ids[1], False) 
                            # if not line_dict:
                            #     line_dict = {}
                            # line_dict[ids[2]] = item_text
                            # table_dict[ids[1]] = line_dict
                            add_item = False
                            for line in table_list:
                                if item_json in line.keys():
                                    continue
                                line[item_json] = item_text
                                add_item = True
                                break
                            if not add_item:
                                line = {}
                                line[item_json] = item_text
                                table_list.append(line)

                    elif item_json == 'field':
                        field.append(item_text)
                    elif item_json:
                        out_dict[item_json] = item_text
                    if item_json == 'syohin_code':
                        out_dict['field'] = field
                    # elif item_json == 'seisansya_code':
                    #     seisansya_code = str2int(item_text)
                    #     filename = get_tnw_filename(seisansya_code)
                out_dict['image_filename'] = filename + '-{}.jpg'.format(page_no)

                if table_json:
                    out_dict[table_json] = table_list
                json_outstr = json.dumps(out_dict, default=obj_dict, ensure_ascii=False, indent=2)
                jsonfile = os.path.join(json_dir, filename + '-{}.json'.format(page_no)).replace(os.sep,'/')

                with open(jsonfile, 'w', encoding='utf-8') as f:
                    f.write(json_outstr)
                logger.debug(f'json write {jsonfile}')
            return filename
        except Exception:
            logger.exception(f'json write exception {filename}')
    return ''

# CSVダウンロードリクエスト
def svt_export_zip(request, entry_id, zip=False):
    object_list = []
    basename_without_ext = ''
    filename = get_tnw_filename('00000')
    try:
        entry =  TtEntry.objects.get(entry_id=entry_id)
        if entry.entry_detail:
            object_list = json.loads(entry.entry_detail) # JSONデータをPythonオブジェクト(list型)へ変換
        if entry.pdf_name:
            basename_without_ext, ext_name = os.path.splitext(os.path.basename(entry.pdf_name))
        if entry:
            # rootfolder = get_rootfolder(entry.owner_id)   # 契約会社のルートフォルダを取得
            rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
            make_trasafolder(rootfolder)    # ファイル出力フォルダ作成
            trasaimg_dir = get_trasafolder(rootfolder)
            trasajson_dir = get_trasafolder(rootfolder)
            # 連携JSONファイル出力
            filename = save_tnwjson(trasajson_dir, entry.entry_detail, filename)

            entryimg_dir = get_ocrform_image_dir(rootfolder)
            imagepath1 =  os.path.join(entryimg_dir, entry_id + '_{:03d}.jpg'.format(1)).replace(os.sep,'/')
            imagepath2 =  os.path.join(entryimg_dir, entry_id + '_{:03d}.jpg'.format(2)).replace(os.sep,'/')
            jpgfile1 = os.path.join(trasaimg_dir, filename + '-{}.jpg'.format(1)).replace(os.sep,'/')
            jpgfile2 = os.path.join(trasaimg_dir, filename + '-{}.jpg'.format(2)).replace(os.sep,'/')
            shutil.copy2(imagepath1, jpgfile1)
            shutil.copy2(imagepath2, jpgfile2)
            if not zip:
                return filename
            jsonfile1 = os.path.join(trasajson_dir, filename + '-{}.json'.format(1)).replace(os.sep,'/')
            jsonfile2 = os.path.join(trasajson_dir, filename + '-{}.json'.format(2)).replace(os.sep,'/')
            zip_filename = (filename or 'download') + '.zip'
            response = HttpResponse(content_type='application/zip')
            response['Content-Disposition'] = "attachment;filename*=utf-8''{}".format(
                quote(zip_filename, safe=''))
            # Django's Response was a File like object.
            # 一時ファイルを作成する代わりに、ZipFileの最初のパラメーターとして使用できます
            with zipfile.ZipFile(response, 'w',
                                compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(jsonfile1, arcname=filename + '-{}.json'.format(1))
                zf.write(jsonfile2, arcname=filename + '-{}.json'.format(2))
                zf.write(jpgfile1, arcname=filename + '-{}.jpg'.format(1))
                zf.write(jpgfile2, arcname=filename + '-{}.jpg'.format(2))
            sv_delete_file(jsonfile1)
            sv_delete_file(jsonfile2)
            sv_delete_file(jpgfile1)
            sv_delete_file(jpgfile2)
            return response
    except TtEntry.DoesNotExist:
        logger.exception(f'TtEntry DoesNotExist {entry_id=}')
    except Exception:
        logger.exception(f'svt_export_zip exception {entry_id=}')
    return False

# 連携ファイル出力
def create_trasa_file(json_str, ocrimages, trasadir, filename):
    try:
        if json_str:
            json_dir = trasadir
            img_dir = trasadir
            # JSONファイル出力
            filename = save_tnwjson(json_dir, json_str, filename)
            if not filename:
                return ''
            for i, imagepath in enumerate(ocrimages, start=1):
                if not imagepath or not os.path.exists(imagepath):
                    continue
                jpgfile = os.path.join(img_dir, filename + '-{}.jpg'.format(i)).replace(os.sep,'/')
                # JPGファイルを連携ファイルに
                shutil.move(imagepath, jpgfile)
            return filename
    except Exception:
        logger.exception('create_trasa_file exception')
    return ''

# バッチ処理でコール management/commands/tnwcommand.py
# ファイル画像からテキストをOCR抽出し連携ファイルに保存
# フォームIDの指定・google利用枚数の保存 ???
def sv_save_trasa_file(path, user_id):
    if not path or not os.path.exists(path):
        return ''
    # try:
    #     userobj = TnwUser.objects.get(user_id=user_id)
    #     folder_path = userobj.folder_path
    #     form_id = userobj.ocrform_id
    #     if not os.path.isdir(folder_path):
    #         os.makedirs(folder_path)   # 再帰的にディレクトリを作成する
    #         logger.debug('makedirs trasa : ' + folder_path)
    # except Exception:
    #     logger.exception('user_id error : ' + (user_id or 'None'))
    #     return ''
    # try:
    #     userobj = EvcUser.objects.get(user_id=user_id)
    #     owner_id = userobj.owner_id
    # except Exception:
    #     logger.exception('user_id error : ' + (user_id or 'None'))
    #     return ''
    
    # rootfolder = get_rootfolder(owner_id)   # 契約会社のルートフォルダを取得
    rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
    if not rootfolder:
        logger.error('rootfolder error')
        return ''
    form_id = 'ofrm_00001'
    make_trasafolder(rootfolder)    # ファイル出力フォルダ作成
    folder_path = get_trasafolder(rootfolder)
    ocrimage_dir = get_imgfolder_upload(rootfolder)
    formimage_dir = get_ocrform_image_dir(rootfolder)
    # config = configparser.ConfigParser()
    # config.read('tnwocr.ini', 'UTF-8')

    # trasadir = config.get('settings', 'trasadir')
    # ocrimage_dir = config.get('settings', 'ocrimgdir')
    # form_dir = config.get('settings', 'formdir')
    # formimage_dir = config.get('settings', 'formimgdir')
    
    # config_data = {
    #     'trasadir': trasadir,
    #     'ocrimage_dir': ocrimage_dir,
    #     'form_dir': form_dir,
    #     'formimage_dir': formimage_dir
    # }
    # if not trasadir or not ocrimage_dir or not formimage_dir:
    #     logger.error('tnwocr.ini folder error ')
    #     return ''
    # if not os.path.isdir(trasadir):
    #     os.makedirs(trasadir)   # 再帰的にディレクトリを作成する
    #     logger.debug('makedirs trasa : ' + trasadir)
    # if not os.path.isdir(ocrimage_dir):
    #     os.makedirs(ocrimage_dir)   # 再帰的にディレクトリを作成する
    #     logger.debug('makedirs ocrimage : ' + ocrimage_dir)

    # print(trasadir)
    # print(ocrimage_dir)

    # OCR抽出情報取得
    basename = os.path.basename(path)
    # ページごとに画像データを作成
    ocrimages = sv_create_ocr_image(path, ocrimage_dir, -1)
    if not ocrimages:   # パスワード設定などにより読み込めない
        logger.error(f'ocrimages False {basename}')
        return ''
    json_str = sv_extract_entry_text(ocrimages, formimage_dir, form_id, user_id)
    if json_str:
        # 連携ファイル出力
        filename = get_tnw_filename('00000')
        filename = create_trasa_file(json_str, ocrimages, folder_path, filename)
        if filename:
            logger.info(f'バッチ処理 ファイル出力に成功しました。{user_id=}')
        else:
            logger.error(f'create_trasa_file False {basename}')
    else:
        logger.error(f'sv_extract_entry_text False {basename}')
        return ''
    return filename
# 入力画像からOCR抽出しフォーム領域のテキストをJSONで取得
# バッチ処理(PDFファイル)
def sv_extract_entry_text(ocrimages, formimage_dir, ocrform_id, user_id):
    json_str = ''
    areas_dict = {}
    # フォーム情報を取得(分割領域・項目リスト)
    if not ocrform_id:
        try:
            result_first = TtOcrform.objects.all().first()
            if result_first:
                ocrform_id = result_first.ocrform_id
        except Exception:
            return json_str
    trapezoid = False   # true:台形補正
    if trapezoid:
        # 入力画像をフォーム画像に合わせる（射影変換）台形補正はこちら
        ocrimages = svt_adjust_image_trapezoid(ocrimages, ocrform_id)

    ocrform_text_datas = None
    try:
        ocrform_obj =  TtOcrform.objects.get(ocrform_id=ocrform_id)
        # フォームの領域情報を取得
        ocrform_area = ocrform_obj.ocrform_area
        # ファイルからフォームの領域情報を取得
        # jsonfile = os.path.join(form_dir, 'form_area.json').replace(os.sep,'/')
        # with open(jsonfile, 'r', encoding='utf-8') as f:
        #     ocrform_area = f.read() # 文字列でファイルを読み込み
        if trapezoid:
        # 台形補正はこちら
            areas_dict = svf_get_areas_dict(ocrform_area)  # 輪郭枠座標をjson文字列に変換(javascriptで処理)
        else:
        # PDFファイルは領域の調整なし
        # フォームの領域座標を入力画像に合わせて変換（アフィン変換）平行四辺形への変換
            areas_dict, ocrform_area = adjust_area(ocrimages, formimage_dir, ocrform_id, ocrform_area)

        # フォームの入力項目情報を取得
        if ocrform_obj.ocrform_text:
            ocrform_text_datas = json.loads(ocrform_obj.ocrform_text)   # 文字列を辞書型に変換

    except TtOcrform.DoesNotExist:
        return json_str
    if settings.DEBUG:
        svf_draw_area(ocrimages, ocrform_area)

    # OCR機能を使って、TextDataデータに変換
    textdatas, detecttext_list, google_cnt, full_texts = svf_extract_text(ocrimages, areas_dict)

    page_count = len(ocrimages)
    pattern = 1 # 1: PDF 2: 写真
    lists = []
    for page_no in range(1, page_count + 1):
        param_dict = {
            'model_name': 'entry',
            'textdatas': textdatas,
            'page_no': page_no,
            'ocrform_text_datas': ocrform_text_datas,
            'areas_dict': areas_dict,
            'ocrimages': ocrimages,
            'pattern': pattern
        }
        # フォームの項目の領域ごとに抽出テキストを取得
        page_lists = svf_get_json_text_page(**param_dict)

        data = {
            'page_no': str(page_no),
            'page_list':page_lists
        }
        lists.append(data)
    json_str = sv_datas2json(lists) # リストをjsonデータに
    if settings.DEBUG:
        # jsonファイルを保存
        if detecttext_list:
            json_dir = '/data_root/evc_root/json'
            basename = os.path.basename(ocrimages[0])
            basename_without_ext, ext_name = os.path.splitext(basename)
            sv_save_detect_json(basename_without_ext, detecttext_list, json_dir)

    return json_str

# フォームの領域座標を入力画像に合わせてアフィン変換
def adjust_area(ocrimages, formimage_dir, ocrform_id, ocrform_area):
    dicts = {}
    if not ocrform_area:
        return dicts, ''
    # 対応点を探索しアフィン行列の取得
    # matrixs = get_matrix(ocrimages, formimage_dir, ocrform_id)
    # 画像上の四角形マーク座標からアフィン行列の推定
    matrixs = svt_get_matrix(ocrimages, formimage_dir, ocrform_id)
    # matrixs = svt_get_trapezoid_matrix(ocrimages, formimage_dir, ocrform_id)
    
    rect_str = ocrform_area
    try:
        areadatas = sv_json2textdatas(ocrform_area) # [TextDatas,TextDatas...]
        for i, pagedata in enumerate(areadatas):
            matrix = matrixs[i] if i < len(matrixs) else np.array([])
            areas = []
            for textdata in pagedata.textdata_list:
                x1 = textdata.x1
                y1 = textdata.y1
                x2 = textdata.x2
                y2 = textdata.y2
                text = textdata.text
                if x2 != 0 and y2 != 0:
                    if 0 < matrix.size:
                        point = np.array([x1, y1, 1])
                        transformed_point = np.dot(matrix, point)   # 行列の積の結果が返されます。
                        pt = transformed_point.astype(int)
                        x1 = pt[0].item()   # numpy.int -> pythonのintに変換
                        y1 = pt[1].item()
                        point = np.array([x2, y2, 1])
                        transformed_point = np.dot(matrix, point)
                        pt = transformed_point.astype(int)
                        x2 = pt[0].item()
                        y2 = pt[1].item()
                    areas.append({ 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'text':text })
                textdata.x1 = x1
                textdata.y1 = y1
                textdata.x2 = x2
                textdata.y2 = y2
            dicts[i] = areas
        rect_str = sv_datas2json(areadatas)
        logger.debug(f'adjust_area {ocrform_id=}')
    except Exception:
        logger.exception('adjust_area exception ')

    return dicts, rect_str

# デバッグのため座標変換した領域を描画した画像を出力（単ページ）
def draw_adjust_area(imagepath, areas):
    try:
        rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
        img_upload_dir = get_imgfolder_upload(rootfolder)

        file_name = os.path.basename(imagepath)
        fname, ext = os.path.splitext(file_name)
        out_name =  os.path.join(img_upload_dir, 'areas_' + file_name).replace(os.sep,'/')

        buf = np.fromfile(imagepath, np.uint8)
        cv2_image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        rect_image = cv2_image.copy()
        angle = sv_get_image_angle(imagepath)
        if angle == 90:
            # 時計回りに90度回転
            rect_image = cv2.rotate(rect_image,cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            rect_image = cv2.rotate(rect_image,cv2.ROTATE_180)
        elif angle == 270:
            rect_image = cv2.rotate(rect_image,cv2.ROTATE_90_COUNTERCLOCKWISE)

        for area in areas:
            start_x = int(area.get('x1','0'))
            start_y = int(area.get('y1','0'))
            end_x = int(area.get('x2','0'))
            end_y = int(area.get('y2','0'))
            cv2.rectangle(rect_image, (start_x, start_y), (end_x, end_y), (0, 0, 255), 5)
        # cv2.imwrite(out_name, rect_image)
        # 日本語を含むファイルパスを取り扱う際の問題への対処
        sv_imwrite(out_name, rect_image)
    except Exception:
        logger.exception(f'draw_adjust_area exception {imagepath}')
