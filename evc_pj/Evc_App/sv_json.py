import os
import datetime
import json
# import re   # 正規表現操作
import logging

from google.cloud import vision
from google.oauth2 import service_account
from django.conf import settings

from google.cloud.vision import AnnotateImageResponse

from commons.utils import ut_get_localtime
from Evc_App.sv_file import TextData,TextDatas,FullText,FullTexts

logger = logging.getLogger(__name__)

def obj_dict(obj):
    return obj.__dict__

# UploadFilesをjsonファイルに保存
def sv_save_upload_json(uploadfiles, json_dir):
    now = ut_get_localtime()
    time = now.strftime('_%Y%m%d-%H%M%S%f')
    name = 'uploadfiles' + time + '.json'

    # basename_without_ext = os.path.splitext(os.path.basename(pdffile))[0]
    jsonfile = os.path.join(json_dir, name).replace(os.sep,'/')
    try:
        with open(jsonfile, 'w', encoding='utf-8') as f:
            json.dump(uploadfiles, f, default=obj_dict, ensure_ascii=False, indent=2)
        logger.debug(f'json write {name=}')
    except Exception:
        logger.exception(f'json write exception {name=}')

# OCR取得結果を保存
def sv_save_responsetext(imagefile, fulltext, json_dir):
    basename_without_ext = os.path.splitext(os.path.basename(imagefile))[0]
    file_name =  basename_without_ext + '_responsetext.txt'
    path_fulltext = os.path.join(json_dir, file_name).replace(os.sep,'/')
    try:
        with open(path_fulltext, 'w', encoding='utf-8') as f:
            f.write(fulltext)
        logger.debug(f'json write {file_name=}')
    except Exception:
        logger.exception(f'json write exception {file_name=}')

def sv_save_detect_as_json(response, filename):
    data = AnnotateImageResponse.to_json(response)
    with open(filename, mode='wt', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        
def sv_load_detect_from_json(filename):
    with open(filename, mode='r', encoding='utf-8') as file:
        temp = json.load(file)
    response = AnnotateImageResponse.from_json(temp)
    return response

def sv_save_detect_json(evi_id, detecttext_list, json_dir):
    jsonfile = os.path.join(json_dir, evi_id + '_detect.json').replace(os.sep,'/')
    try:
        json_string = json.dumps(detecttext_list, default=obj_dict, ensure_ascii=False, indent=2)
        with open(jsonfile, 'w', encoding='utf-8') as f:
            f.write(json_string)
        logger.debug(f'json detect write {evi_id=}')
    except Exception:
        logger.exception(f'json detect write exception {evi_id=}')

def sv_load_detect_json(evi_id, json_dir, page_no):
    jsonfile = os.path.join(json_dir, evi_id + '_detect.json').replace(os.sep,'/')
    with open(jsonfile, mode='r', encoding='utf-8') as file:
        detectlist = json.load(file)
    response = None
    for data in detectlist:
        data_page_no = data.get('page_no')
        if page_no == data_page_no:
            data_text = data.get('text')
            response = AnnotateImageResponse.from_json(data_text)
            break
    return response
# def sv_save_detect_json(pdffile, response, json_dir):
#     basename_without_ext = os.path.splitext(os.path.basename(pdffile))[0]
#     jsonfile = os.path.join(json_dir, basename_without_ext + '_detect.json').replace(os.sep,'/')
#     try:
#         data = AnnotateImageResponse.to_json(response)
#         with open(jsonfile, 'w', encoding='utf-8') as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)
#         logger.debug('json detect write : ' + basename_without_ext)
#     except Exception:
#         logger.exception('json detect write exception : ' + basename_without_ext)

# def sv_load_detect_json(pdffile, json_dir):
#     basename_without_ext = os.path.splitext(os.path.basename(pdffile))[0]
#     jsonfile = os.path.join(json_dir, basename_without_ext + '_detect.json').replace(os.sep,'/')
#     with open(jsonfile, mode='r', encoding='utf-8') as file:
#         temp = json.load(file)
#     response = AnnotateImageResponse.from_json(temp)
#     return response

# Pythonオブジェクト(辞書・リストなど)をJSON形式の文字列に変換
def sv_datas2json(datas):
    json_str = ''
    try:
        json_str = json.dumps(datas, default=obj_dict, ensure_ascii=False, indent=2)
        # logger.debug('json : ' + json_str)
    except Exception:
        logger.exception('json exception')
    return json_str
# TextDatasをjsonデータに変換
def sv_textdatas2json(textdatas):
    json_str = ''
    try:
        json_str = json.dumps(textdatas, default=obj_dict, ensure_ascii=False, indent=2)
        # logger.debug('json : ' + json_str)
    except Exception:
        logger.exception('json exception')
    return json_str

# 文字列からTextDatasデータに変換
def sv_json2textdatas(json_str):
    textdatas = []
    try:
        data = json.loads(json_str) # 文字列を辞書型に変換
        textdatas = dic_to_class(data)
    except Exception:
        logger.exception('json exception' )
    return textdatas

# TextDatasをjsonファイルに保存
def sv_save_json(pdffile, textdatas, json_dir):
    basename_without_ext = os.path.splitext(os.path.basename(pdffile))[0]
    jsonfile = os.path.join(json_dir, basename_without_ext + '.json').replace(os.sep,'/')
    try:
        with open(jsonfile, 'w', encoding='utf-8') as f:
            json.dump(textdatas, f, default=obj_dict, ensure_ascii=False, indent=2)
        logger.debug(f'json write {basename_without_ext}')
    except Exception:
        logger.exception(f'json write exception {basename_without_ext}')
    return jsonfile

# jsonファイルからTextDatasデータを読み込む
def sv_load_jsonfile(pdffile, json_dir):
    textdatas = []
    basename_without_ext = os.path.splitext(os.path.basename(pdffile))[0]
    jsonfile = os.path.join(json_dir, basename_without_ext + '.json').replace(os.sep,'/')
    if os.path.exists(jsonfile):
        try:
            with open(jsonfile, 'r', encoding='utf-8') as f:
                dict_list = json.load(f)
            textdatas = dic_to_class(dict_list)
            logger.debug(f'json read {basename_without_ext}')
        except Exception:
            logger.exception(f'json read exception {basename_without_ext}')


    # jsonfile = str(json_path) + '_outtextdatas.json'
    # with open(jsonfile, 'w', encoding='utf-8') as f:
    #     json.dump(textdatas, f, default=obj_dict, ensure_ascii=False, indent=2)

    return textdatas

# 辞書型のデータからTextDatasクラスオブジェクトに 
def dic_to_class(dictdatas):
    textdatas = []
    for pagedata in dictdatas:
        # textdatas.append(TextDatas(**pagedata))
        page_no = pagedata.get('page_no')
        area_no = pagedata.get('area_no',0)
        page_w =  pagedata.get('page_width',0)
        page_h =  pagedata.get('page_height',0)

        list = pagedata.get('textdata_list')
        page_textdatas = []
        for data in list:
            page_textdatas.append(TextData(**data))
        textdatas.append(TextDatas(1, page_no, area_no, page_w, page_h, page_textdatas))
    return textdatas

# 全文データをjsonで読み込む
def sv_load_fulltext(jsonfile):
    fulltext_lists = []
    if os.path.exists(jsonfile):
        with open(jsonfile, 'r', encoding='utf-8') as f:
            dict_list = json.load(f)
        for fulltexts in dict_list:
            # textdatas.append(TextDatas(**pagedata))
            filename = fulltexts['filename']
            pdfpath = fulltexts['pdfpath']
            list = fulltexts['fulltext_list']
            fulltext_list = []
            for data in list:
                fulltext_list.append(FullText(**data))
            fulltext_lists.append(FullTexts(filename, pdfpath, fulltext_list))
    return fulltext_lists
# 全文データをjsonで保存
def sv_save_fulltext(pdffile, textdatas, json_dir):
    jsonfile = os.path.join(json_dir, 'fullTextLists.json').replace(os.sep,'/')

    fulltext_lists = textdatas_to_fulltexts(pdffile, textdatas, jsonfile)

    try:
    # with open(jsonfile, 'w', encoding='utf-8') as f:
    #     json.dump(fulltext_lists, f, default=obj_dict, ensure_ascii=False, indent=2)
        json_string = json.dumps(fulltext_lists, default=obj_dict, ensure_ascii=False, indent=2)
        with open(jsonfile, 'w', encoding='utf-8') as f:
            f.write(json_string)
        logger.debug('json write : fullTextLists.json')

        jsonjsfile = os.path.join(json_dir, 'fullTextLists.json.js').replace(os.sep,'/')
        with open(jsonjsfile, 'w', encoding='utf-8') as f:
            f.write('var list = ' + json_string + ';')
    except Exception:
        logger.exception('fulltext json write exception : fullTextLists.json')

# TextDatasを連結して全文データを作成
# 既存の同一PDFファイルのデータは削除して追加
def textdatas_to_fulltexts(pdffile, textdatas, jsonfile):
    basename_without_ext = os.path.splitext(os.path.basename(pdffile))[0]
    fulltext_lists = sv_load_fulltext(jsonfile)
    for fulltexts in fulltext_lists:
        if fulltexts.pdfpath.lower() == pdffile.lower():
        # if basename_without_ext == fulltexts.filename:
            fulltext_lists.remove(fulltexts) 
            break
    fulltext_list = []
    for pagedata in textdatas:
        fulltext = ''
        for textdata in pagedata.textdata_list:
            fulltext += textdata.text
        fulltext_list.append(FullText(pagedata.page_no, fulltext))
    fulltext_lists.append(FullTexts(basename_without_ext, pdffile, fulltext_list))
    return fulltext_lists
# 全文データのファイル名を変更
def sv_replace_fulltext_pdfpath(json_dir, pdfname, old, new):
    jsonfile = os.path.join(json_dir, 'fullTextLists.json').replace(os.sep,'/')
    fulltext_lists = sv_load_fulltext(jsonfile)
    for fulltexts in fulltext_lists:
        if fulltexts.pdfpath.lower() == old.lower():
            fulltexts.pdfpath = new
            break
    try:
        json_string = json.dumps(fulltext_lists, default=obj_dict, ensure_ascii=False, indent=2)
        with open(jsonfile, 'w', encoding='utf-8') as f:
            f.write(json_string)
        logger.debug('json write : fullTextLists.json')
    except Exception:
        logger.exception('fulltext json write exception : fullTextLists.json')
            
# 全文データを変更
def sv_replace_fulltext(json_dir, fulltext, pdfpath):
    jsonfile = os.path.join(json_dir, 'fullTextLists.json').replace(os.sep,'/')
    fulltext_lists = sv_load_fulltext(jsonfile)
    for fulltexts in fulltext_lists:
        if fulltexts.pdfpath.lower() == pdfpath.lower():
            for list in fulltexts.fulltext_list:
                if list.page_no == 1:
                    list.text = fulltext
                    break
            break
    try:
        json_string = json.dumps(fulltext_lists, default=obj_dict, ensure_ascii=False, indent=2)
        with open(jsonfile, 'w', encoding='utf-8') as f:
            f.write(json_string)
        logger.debug('json write : fullTextLists.json')
    except Exception:
        logger.exception('fulltext json write exception : fullTextLists.json')

# 全文データから指定ファイルのデータを削除
def sv_delete_fulltext(json_dir, pdfpath):
    jsonfile = os.path.join(json_dir, 'fullTextLists.json').replace(os.sep,'/')
    fulltext_lists = sv_load_fulltext(jsonfile)
    if not fulltext_lists:
        logger.debug('fulltext json empty')
        return
    for fulltexts in fulltext_lists:
        if fulltexts.pdfpath.lower() == pdfpath.lower():
            fulltext_lists.remove(fulltexts) 
            break
    try:
        json_string = json.dumps(fulltext_lists, default=obj_dict, ensure_ascii=False, indent=2)
        with open(jsonfile, 'w', encoding='utf-8') as f:
            f.write(json_string)
        logger.debug('json write : fullTextLists.json')
    except Exception:
        logger.exception('fulltext json write exception : fullTextLists.json')
