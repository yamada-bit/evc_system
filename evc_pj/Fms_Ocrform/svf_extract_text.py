import logging
import math
import os
import re  # 正規表現操作

from django.conf import settings
from google.cloud import vision
from google.oauth2 import service_account

from commons.utils import ut_get_localtime, ut_get_localtoday
from Evc_App.sv_file import (
    DetectJson,
    TextData,
    TextDatas,
    sv_get_textlines,
)
from Evc_App.sv_json import (
    sv_load_detect_json,
    sv_save_detect_json,
)

# XTHRESHOLD=120   # 1cm : 100 / 254 * 300(DPI)
# YTHRESHOLD=12    # 1mm : 10 / 254 * 300
XTHRESHOLD = 80 # 1cm : 100 / 254 * 200(DPI)
YTHRESHOLD = 8  # 1mm : 10 / 254 * 200
# YTHRESHOLD = 20  # 2.5mm : 10 / 254 * 200
MAXTHRESHOLD = 80  # 1cm : 100 / 254 * 200
# XTHRESHOLD=60   # 1cm : 100 / 254 * 150(DPI)
# YTHRESHOLD=6    # 1mm : 10 / 254 * 150
# XTHRESHOLD = 120 # 1cm : 100 / 254 * 300(DPI)
# YTHRESHOLD = 12  # 1mm : 10 / 254 * 300
# MAXTHRESHOLD = 120  # 1cm : 100 / 254 * 300

GOOGLEOCR = True
# GOOGLEOCR = settings.GOOGLE_OCR

logger = logging.getLogger(__name__)

# Google Cloud Vision APIのOCR機能を使ってテキスト抽出
# symbolテキストをareaで抽出
# TextDatasの配列で返す
def svf_extract_text(imagefiles, areas_dict):
# 身元証明書のjson読み込み
    path = os.path.join(settings.BASE_DIR, settings.GOOGLE_CLOUD_VISION_KEY).replace(os.sep,'/')
    textdatas = []
    try:
        logger.debug(f'vision.ImageAnnotatorClient {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
        credentials = service_account.Credentials.from_service_account_file(path)
        client = vision.ImageAnnotatorClient(credentials=credentials)
    except Exception:
        logger.exception('vision exception')
        return textdatas

    detecttext_list = []
    full_textdatas = []
    full_texts = {}
    google_cnt = 0
    page_count = len(imagefiles) if imagefiles else 1
    for i, imagefile in enumerate(imagefiles):
        input_file = imagefile
        try:
            page_no = i + 1

            # if 1 < page_count and specif_page_list and page_no not in specif_page_list:
            #     continue
            with open(input_file, 'rb') as image_file:
                content = image_file.read()
            if GOOGLEOCR:
                logger.debug(f'vision.Image {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
                image = vision.Image(content=content)
                # logger.debug('text_detection' + ut_get_localtime().strftime('%Y/%m/%d %H:%M:%S'))
                # response = client.text_detection(image=image)
                response = client.document_text_detection(
                    image=image,
                    image_context={'language_hints': ['ja']}
                )
                logger.debug(f'document_text_detection {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
                google_cnt += 1
                if settings.DEBUG:
                    detecttext = vision.AnnotateImageResponse.to_json(response)
                    detecttext_list.append(DetectJson(page_no, detecttext))
            else:
                basename = os.path.basename(imagefiles[0])
                now = ut_get_localtoday()
                time = now.strftime('_%Y%m%d-')
                idx = basename.find(time)
                if 0 < idx:
                    file_name =  basename[:idx]
                else:
                    file_name =  basename[:-7]
                response = sv_load_detect_json(file_name, '/data_root/evc_root/_test/detect', page_no)

            # if settings.DEBUG:
            #     # OCRした結果を表示
            #     # print(response.full_text_annotation.text)
            #     # json_dir = 'C:\\Evc_root\\SO23120001_root\\json'
            #     json_dir = 'C:\\Evc_root\\json'
            #     sv_save_responsetext(input_file, response.full_text_annotation.text, json_dir)
            #     # sv_save_responsetext(input_file, response.text_annotation.text, json_dir)

            # full_textdatas.extend(get_lines(page_no, response, None))
            full_textdatas = get_lines(page_no, response, None)
            # 全文テキストデータを作成
            if full_textdatas:
                textlines = sv_get_textlines(full_textdatas, page_no, -1)
                full_texts[page_no] = '\n'.join(textlines)

            symbol_textdatas,page_width,page_height = get_symbols_textdatas(page_no, response)
            areas = areas_dict.get(i)
            page_textdatas = get_area_textdatas(page_no, symbol_textdatas,
                                                 page_width, page_height, areas)

            textdatas.extend(page_textdatas)
            logger.debug(f'get_area_textdatas {input_file} : {page_no}')
        except Exception:
            logger.exception(f'OCR response exception {input_file}')
    # # 全文テキストデータを作成
    # if full_textdatas:
    #     textlines = sv_get_textlines(full_textdatas, -1, -1)
    #     full_text = '\n'.join(textlines)
    # else:
    #     full_text = ''

    return textdatas, detecttext_list, google_cnt, full_texts

# symbolテキストを抽出
def get_symbols_textdatas(page_no, response):
    sp = ' '
    sure_sp = ' '
    eol = '\n'
    hyphen = '-\n'
    linebreak = '\n'
    unk = ''
    symbol_list = []
    for page in response.full_text_annotation.pages:
        page_width = page.width
        page_height = page.height
        # min_width = page_width / 300
        rotate_angle = get_rotate_angle(page)

        degrees = []
        angleps= []
        anglems = []
        symbols = []
        for block in page.blocks:
            # bounding_box:「左上」「右上」「右下」「左下」の順
            x11 = block.bounding_box.vertices[0].x
            y11 = block.bounding_box.vertices[0].y
            x22 = block.bounding_box.vertices[2].x
            y22 = block.bounding_box.vertices[2].y
            # if y22 < y11:
            if y22 < y11 and abs(x22 - x11) * 2 < abs(y22 - y11):
                continue
            for paragraph in block.paragraphs:
                x1 = paragraph.bounding_box.vertices[0].x
                y1 = paragraph.bounding_box.vertices[0].y
                x2 = paragraph.bounding_box.vertices[2].x
                y2 = paragraph.bounding_box.vertices[2].y
                # if y2 < y1:
                #     continue
                for word in paragraph.words:
                    x1 = word.bounding_box.vertices[0].x
                    y1 = word.bounding_box.vertices[0].y
                    x2 = word.bounding_box.vertices[2].x
                    y2 = word.bounding_box.vertices[2].y
                    # if y2 < y1:
                    #     continue
                    degree = get_bounding_degree(word)
                    degrees.append(degree)
                    if 0 < degree:
                        angleps.append(degree)
                    elif degree < 0:
                        anglems.append(degree)
                    # if degree:
                    #     degrees.append(degree)
                    # else:
                    #     angle0s.append(0)
                    # wx11 = word.bounding_box.vertices[0].x
                    # wy11 = word.bounding_box.vertices[0].y
                    # wx22 = word.bounding_box.vertices[2].x
                    # wy22 = word.bounding_box.vertices[2].y
                    # text = [symbol.text for symbol in word.symbols]
                    for symbol in word.symbols:
                        # x1 = symbol.bounding_box.vertices[0].x
                        # y1 = symbol.bounding_box.vertices[0].y
                        # x2 = symbol.bounding_box.vertices[2].x
                        # y2 = symbol.bounding_box.vertices[2].y
                        # # if x2 < x1 or y2 < y1:
                        # if y2 < y1:
                        #     continue
                        pos = get_pos(symbol, page_width, page_height, rotate_angle)
                        pre = ''
                        post = ''
                        # if symbol.property.detected_break:
                        #     # DetectedBreakがあるとき
                        #     break_str = unk
                        #     typ = symbol.property.detected_break.type_
                        #     if typ == vision.TextAnnotation.DetectedBreak.BreakType.SPACE:
                        #         break_str = sp
                        #     elif typ == vision.TextAnnotation.DetectedBreak.BreakType.SURE_SPACE:
                        #         break_str = sure_sp
                        #     # elif typ == vision.TextAnnotation.DetectedBreak.BreakType.EOL_SURE_SPACE:
                        #     #     break_str = eol
                        #     # elif typ == vision.TextAnnotation.DetectedBreak.BreakType.HYPHEN:
                        #     #     break_str = hyphen
                        #     # elif typ == vision.TextAnnotation.DetectedBreak.BreakType.LINE_BREAK:
                        #     #     break_str = linebreak
                        #     # is_prefiexの時、シンボルの前に追加。それ以外は後ろへ
                        #     if symbol.property.detected_break.is_prefix:
                        #         pre = break_str
                        #     else:
                        #         post = break_str
                        wx1 = min(pos[0], pos[2])
                        wy1 = min(pos[1], pos[3])
                        wx2 = max(pos[0], pos[2])
                        wy2 = max(pos[1], pos[3])
                        symbols.append(TextData(wx1, wy1, wx2, wy2, pre + symbol.text + post))
                        # if settings.DEBUG:
                        #     data = {
                        #         'text': symbol.text,
                        #         'block': [block.bounding_box.vertices[0].x,block.bounding_box.vertices[0].y,
                        #                         block.bounding_box.vertices[2].x,block.bounding_box.vertices[2].y],
                        #         'paragraph': [paragraph.bounding_box.vertices[0].x,paragraph.bounding_box.vertices[0].y,
                        #                         paragraph.bounding_box.vertices[2].x,paragraph.bounding_box.vertices[2].y],
                        #         'word': [word.bounding_box.vertices[0].x,word.bounding_box.vertices[0].y,
                        #                         word.bounding_box.vertices[2].x,word.bounding_box.vertices[2].y],
                        #         'symbol': [symbol.bounding_box.vertices[0].x,symbol.bounding_box.vertices[0].y,
                        #                         symbol.bounding_box.vertices[2].x,symbol.bounding_box.vertices[2].y],
                        #     }
                        #     symbol_list.append(data)
        # if degrees:
        #     adjust_angle = int(sum(degrees)/len(degrees))
        #     if 0 < abs(adjust_angle):
        #         lines = rotate_bounds(lines, adjust_angle, center_x, center_y)
        #     adjust_angle = 0    # 傾きを補正したので　0 にする
        # else:
        #     adjust_angle = 0
    # if settings.DEBUG:
    #     data = {
    #         'page_no': page_no,
    #         'page_list':symbol_list
    #     }
    #     json_dir = 'C:\\Evc_root\\json'
    #     jsonfile = os.path.join(json_dir, 'symbol_list'+ '_{:02d}.json'.format(page_no)).replace(os.sep,'/')
    #     try:
    #         with open(jsonfile, 'w', encoding='utf-8') as f:
    #             json.dump(data, f, ensure_ascii=False, indent=2)
    #     except Exception:
    #         logger.exception('json write exception ')

    return symbols,page_width,page_height
# symbolテキストをareaに
def get_area_textdatas(page_no, sysmbol_textdatas, page_width, page_height, areas):
    textdatas = []
    symbol_list = []
    if not areas:
        areas = [{ 'x1': 0, 'y1': 0, 'x2': page_width, 'y2': page_height, 'text':'1' }]
    area_dict = {}
    # symbols.append(TextData(wx1, wy1, wx2, wy2, pre + symbol.text + post))
    for symbol in sysmbol_textdatas:
        cx = (symbol.x1 + symbol.x2) / 2
        cy = (symbol.y1 + symbol.y2) / 2
        area_no = 0
        for area in areas:
            area_no += 1
            # if area_no == 84:
            #     area_no = 84
            start_x = int(area.get('x1','0'))
            start_y = int(area.get('y1','0'))
            end_x = int(area.get('x2','0'))
            end_y = int(area.get('y2','0'))
            area_no = int(area.get('text','0'))
            if start_x < cx and cx < end_x and start_y < cy and cy < end_y:
                if area_no not in area_dict:
                    area_dict[area_no] = [symbol]
                else:
                    exist = checkexist(area_dict[area_no], symbol)
                    if not exist:
                        area_dict[area_no].append(symbol)
                break
    for key, area_symbols in area_dict.items():
        area_symbols.sort(key=lambda x: x.x1)
        bounds = []
        strline = ''
        x1 = -1
        for symbol in area_symbols:
            if x1 == -1:
                x1 = symbol.x1
                x2 = symbol.x2
                y1 = symbol.y1
                y2 = symbol.y2
            else:
                if symbol.y1 < y1:
                    y1 = symbol.y1  # 最小値
                x2 = symbol.x2
                if y2 < symbol.y2:
                    y2 = symbol.y2  # 最大値
            strline += symbol.text
        # strline = remove_all_whitespace(strline)
        if x1 != -1:
            bounds.append(TextData(x1, y1, x2, y2, strline))
            area_no = key
            textdatas.append(TextDatas(1, page_no, area_no, page_width, page_height, bounds))
    textdatas.sort(key=lambda x: x.area_no)

    return textdatas

def checkexist(area_symbols, symbol):
    sx1 = symbol.x1
    sx2 = symbol.x2
    sy1 = symbol.y1
    sy2 = symbol.y2
    cx = (sx1 + sx2) / 2
    cy = (sy1 + sy2) / 2
    w = abs(sx2 - sx1) / 5
    for item in area_symbols:
        if item.x1 - w < cx and cx < item.x2 + w:
            if symbol.text == item.text:
                return True
            if abs(item.y2 - item.y1) < abs(sy2 - sy1):
                item.x1 = sx1
                item.y1 = sy1
                item.x2 = sx2
                item.y2 = sy2
                item.text = symbol.text
                return True
            return True
    return False

def checkexist0(area_symbols, symbol):
    cx = (symbol.x1 + symbol.x2) / 2
    cy = (symbol.y1 + symbol.y2) / 2
    for item in area_symbols:
        if item.x1 < cx and cx < item.x2 and item.y1 < cy and cy < item.y2:
            if symbol.text == item.text:
                return True
            if item.x1 <= symbol.x1 and symbol.x2 <= item.x2:
                item.x1 = symbol.x1
                item.y1 = symbol.y1
                item.x2 = symbol.x2
                item.y2 = symbol.y2
                item.text = symbol.text
                return True
            else:
                if symbol.x1 <= item.x1 and item.x2 <= symbol.x2:
                    return True
    return False

# block内でsymbolデータをy座標でソートして行ごとにx座標でソート
def get_lines(page_no, response, areas):
    textdatas = []
    sp = ' '
    sure_sp = ' '
    eol = '\n'
    hyphen = '-\n'
    linebreak = '\n'
    unk = ''
    symbol_list = []
    for page in response.full_text_annotation.pages:
        page_width = page.width
        page_height = page.height
        # min_width = page_width / 300
        rotate_angle = get_rotate_angle(page)
        if not areas:
            areas = [{ 'x1': 0, 'y1': 0, 'x2': page_width, 'y2': page_height, 'text':'1' }]
        area_no = 0
        for area in areas:
            area_no += 1
            start_x = int(area.get('x1','0'))
            start_y = int(area.get('y1','0'))
            end_x = int(area.get('x2','0'))
            end_y = int(area.get('y2','0'))
            area_no = int(area.get('text','0'))
            # start_x = area[0]
            # start_y = area[1]
            # end_x = area[2]
            # end_y = area[3]
            center_x = (start_x + end_x) / 2
            center_y = (start_y + end_y) / 2

            lines = []
            degrees = []
            angleps= []
            anglems = []
            for block in page.blocks:
                # bounding_box:「左上」「右上」「右下」「左下」の順
                    # bounds = []
                x11 = block.bounding_box.vertices[0].x
                y11 = block.bounding_box.vertices[0].y
                x22 = block.bounding_box.vertices[2].x
                y22 = block.bounding_box.vertices[2].y
                # x1 = min(x11, x22)
                # y1 = min(y11, y22)
                # x2 = max(x11, x22)
                # y2 = max(y11, y22)
                x1 = x11 # min(x11, x22)
                y1 = y11 # min(y11, y22)
                x2 = x22 # max(x11, x22)
                y2 = y22 # max(y11, y22)
                if end_x < x1 or x2 < start_x or end_y < y1 or y2 < start_y:
                    continue
                for paragraph in block.paragraphs:
                    # x1 = paragraph.bounding_box.vertices[0].x
                    # y1 = paragraph.bounding_box.vertices[0].y
                    # x2 = paragraph.bounding_box.vertices[2].x
                    # y2 = paragraph.bounding_box.vertices[2].y
                    # if end_x < x1 or x2 < start_x or end_y < y1 or y2 < start_y:
                    #     continue
                    pre_wx1 = -1
                    pre_wx2 = -1
                    pre_wy1 = -1
                    pre_wy2 = -1
                    symbols = []
                    for word in paragraph.words:
                        degree = get_bounding_degree(word)
                        degrees.append(degree)
                        if 0 < degree:
                            angleps.append(degree)
                        elif degree < 0:
                            anglems.append(degree)
                        # if degree:
                        #     degrees.append(degree)
                        # else:
                        #     angle0s.append(0)
                        wx11 = word.bounding_box.vertices[0].x
                        wy11 = word.bounding_box.vertices[0].y
                        wx22 = word.bounding_box.vertices[2].x
                        wy22 = word.bounding_box.vertices[2].y
                        # wx1 = min(wx11, wx22)
                        # wy1 = min(wy11, wy22)
                        # wx2 = max(wx11, wx22)
                        # wy2 = max(wy11, wy22)
                        wx1 = wx11 # min(wx11, wx22)
                        wy1 = wy11 # min(wy11, wy22)
                        wx2 = wx22 # max(wx11, wx22)
                        wy2 = wy22 # max(wy11, wy22)

                        # text = [symbol.text for symbol in word.symbols]
                        if end_x < wx1 or wx2 < start_x or end_y < wy1 or wy2 < start_y:
                            continue
                        pos = get_pos(word, page_width, page_height, rotate_angle)
                        wx1 = min(pos[0], pos[2])
                        wy1 = min(pos[1], pos[3])
                        wx2 = max(pos[0], pos[2])
                        wy2 = max(pos[1], pos[3])
                        # paragraphs内でy座標でword連結
                        if pre_wy1 == -1:
                            pre_wx1 = wx1
                            pre_wx2 = wx2
                            pre_wy1 = wy1
                            pre_wy2 = wy2
                        elif pre_wx2 < wx2 and pre_wy1 <= wy1 <= pre_wy2:
                            pre_wx1 = wx1
                            pre_wx2 = wx2
                            pre_wy1 = wy1
                            pre_wy2 = wy2
                        elif pre_wx2 < wx2 and pre_wy1 <= wy2 <= pre_wy2:
                            pre_wx1 = wx1
                            pre_wx2 = wx2
                            pre_wy1 = wy1
                            pre_wy2 = wy2
                        elif pre_wx2 < wx2 and wy1 <= pre_wy1 and pre_wy2 <= wy2:
                            pre_wx1 = wx1
                            pre_wx2 = wx2
                            pre_wy1 = wy1
                            pre_wy2 = wy2
                        else:
                            pre_wx1 = -1
                            pre_wx2 = -1
                            pre_wy1 = -1
                            pre_wy2 = -1
                            lines.append(symbols)
                            symbols = []
                            pre_wx1 = wx1
                            pre_wx2 = wx2
                            pre_wy1 = wy1
                            pre_wy2 = wy2
                        for symbol in word.symbols:
                            pos = get_pos(symbol, page_width, page_height, rotate_angle)
                            pre = ''
                            post = ''
                            if symbol.property.detected_break:
                                # DetectedBreakがあるとき
                                break_str = unk
                                typ = symbol.property.detected_break.type_
                                if typ == vision.TextAnnotation.DetectedBreak.BreakType.SPACE:
                                    break_str = sp
                                elif typ == vision.TextAnnotation.DetectedBreak.BreakType.SURE_SPACE:
                                    break_str = sure_sp
                                # elif typ == vision.TextAnnotation.DetectedBreak.BreakType.EOL_SURE_SPACE:
                                #     break_str = eol
                                # elif typ == vision.TextAnnotation.DetectedBreak.BreakType.HYPHEN:
                                #     break_str = hyphen
                                # elif typ == vision.TextAnnotation.DetectedBreak.BreakType.LINE_BREAK:
                                #     break_str = linebreak
                                # is_prefiexの時、シンボルの前に追加。それ以外は後ろへ
                                if symbol.property.detected_break.is_prefix:
                                    pre = break_str
                                else:
                                    post = break_str
                            wx1 = min(pos[0], pos[2])
                            wy1 = min(pos[1], pos[3])
                            wx2 = max(pos[0], pos[2])
                            wy2 = max(pos[1], pos[3])
                            # if wx2 - wx1 < min_width:
                            #     continue
                            cx = (wx1 + wx2) / 2
                            cy = (wy1 + wy2) / 2
                            # symbols.append(TextData(wx1, wy1, wx2, wy2, pre + symbol.text + post))
                            # if start_x <= wx1 and wx2 <= end_x and start_y <= wy1 and  wy2 <= end_y:    # 全体が含まれているか
                            # if start_x <= wx1 and wx2 <= end_x and start_y <= cy and cy <= end_y:    # 横全体が含まれているか
                            if start_x <= cx and cx <= end_x and start_y <= cy and cy <= end_y:    # 中心が含まれているか
                                symbols.append(TextData(wx1, wy1, wx2, wy2, pre + symbol.text + post))
                                if settings.DEBUG:
                                    data = {
                                        'area_no': area_no,
                                        'text': symbol.text,
                                        'block': [block.bounding_box.vertices[0].x,block.bounding_box.vertices[0].y,
                                                      block.bounding_box.vertices[2].x,block.bounding_box.vertices[2].y],
                                        'paragraph': [paragraph.bounding_box.vertices[0].x,paragraph.bounding_box.vertices[0].y,
                                                      paragraph.bounding_box.vertices[2].x,paragraph.bounding_box.vertices[2].y],
                                        'word': [word.bounding_box.vertices[0].x,word.bounding_box.vertices[0].y,
                                                      word.bounding_box.vertices[2].x,word.bounding_box.vertices[2].y],
                                        'symbol': [symbol.bounding_box.vertices[0].x,symbol.bounding_box.vertices[0].y,
                                                      symbol.bounding_box.vertices[2].x,symbol.bounding_box.vertices[2].y],
                                    }
                                    symbol_list.append(data)
                    lines.append(symbols)
            if degrees:
                adjust_angle = int(sum(degrees)/len(degrees))
                if 0 < abs(adjust_angle):
                    lines = rotate_bounds(lines, adjust_angle, center_x, center_y)
                adjust_angle = 0    # 傾きを補正したので　0 にする
            else:
                adjust_angle = 0

            block_lines = join_bounds(lines)
            page_lines = sort_bounds(block_lines, adjust_angle)
            page_textdatas = bounds_to_textdata(page_lines)
            textdatas.append(TextDatas(1, page_no, area_no, page_width, page_height, page_textdatas))
    # if settings.DEBUG:
    #     data = {
    #         'page_no': page_no,
    #         'page_list':symbol_list
    #     }
    #     json_dir = 'C:\\Evc_root\\json'
    #     jsonfile = os.path.join(json_dir, 'symbol_list'+ '_{:02d}.json'.format(page_no)).replace(os.sep,'/')
    #     try:
    #         with open(jsonfile, 'w', encoding='utf-8') as f:
    #             json.dump(data, f, ensure_ascii=False, indent=2)
    #     except Exception:
    #         logger.exception('json write exception')

    return textdatas
# wordの傾き角度を取得
def get_bounding_degree(word):
    degree = 0
    x = []
    y = []
    try:
        for d in word.bounding_box.vertices:
            x.append(d.x)
            y.append(d.y)
        if len(x) == 4 and len(y) == 4:
            if (x[1] - x[0]) == 0:
                tan = 0
            else:
                tan = (y[0] - y[1]) / (x[1] - x[0])
            deg = math.atan(tan) * 180 / math.pi
            if deg and abs(deg) < 30:   # 30度未満を有効とする
                degree = int(deg)
    except Exception:
        logger.exception(f'get_bounding_degree exception {word=}')
    return degree

# 取得データの回転角度を取得
def get_rotate_angle(page):
    rotate_flgs = [0, 0, 0, 0]
    rotate_angles = [0, -90, 90, 180]
    for block in page.blocks:
        for paragraph in block.paragraphs:
            for word in paragraph.words:
                if word.symbols:
                    if 1 < len(word.symbols):
                        symbol = word.symbols[0]
                        x1 = symbol.bounding_box.vertices[0].x
                        y1 = symbol.bounding_box.vertices[0].y
                        symbol = word.symbols[-1]
                        x2 = symbol.bounding_box.vertices[0].x
                        y2 = symbol.bounding_box.vertices[0].y
                        if abs(x1 - x2) > abs(y1 - y2):
                            if 0 < x2 - x1:
                                rotate_flgs[0] += 1
                            elif x2 - x1 < 0:
                                rotate_flgs[3] += 1
                        elif abs(x1 - x2) < abs(y1 - y2):
                            if 0 < y2 - y1:
                                rotate_flgs[2] += 1
                            elif y2 - y1 < 0:
                                rotate_flgs[1] += 1
    max_value = max(rotate_flgs)
    max_index = rotate_flgs.index(max_value)
    rotate_angle = rotate_angles[max_index]
    return rotate_angle
# 回転角度で座標データを調整
def get_pos(symbol, w, h, a):
    pos = []
    if a == -90:
        x1 = h - symbol.bounding_box.vertices[0].y
        y1 = symbol.bounding_box.vertices[0].x
        x2 = h - symbol.bounding_box.vertices[2].y
        y2 = symbol.bounding_box.vertices[2].x
    elif a == 90:
        x1 = symbol.bounding_box.vertices[0].y
        y1 = w - symbol.bounding_box.vertices[0].x
        x2 = symbol.bounding_box.vertices[2].y
        y2 = w - symbol.bounding_box.vertices[2].x
    elif a == 180:
        x1 = w - symbol.bounding_box.vertices[0].x
        y1 = h - symbol.bounding_box.vertices[0].y
        x2 = w - symbol.bounding_box.vertices[2].x
        y2 = h - symbol.bounding_box.vertices[2].y
    else:
        x1 = symbol.bounding_box.vertices[0].x
        y1 = symbol.bounding_box.vertices[0].y
        x2 = symbol.bounding_box.vertices[2].x
        y2 = symbol.bounding_box.vertices[2].y
    pos += [x1, y1, x2, y2]
    return pos
# 傾きを補正
def rotate_bounds(lines, angle, cx, cy):
    d_rad = math.radians(angle)
    for symbols in lines:
        for symbol in symbols:
            x1 = symbol.x1 - cx
            x2 = symbol.x2 - cx
            y1 = symbol.y1 - cy
            y2 = symbol.y2 - cy
            x1_rotated = x1 * math.cos(d_rad) - y1 * math.sin(d_rad)
            y1_rotated = x1 * math.sin(d_rad) + y1 * math.cos(d_rad)
            x2_rotated = x2 * math.cos(d_rad) - y2 * math.sin(d_rad)
            y2_rotated = x2 * math.sin(d_rad) + y2 * math.cos(d_rad)
            symbol.x1 = int(x1_rotated + cx)
            symbol.x2 = int(x2_rotated + cx)
            symbol.y1 = int(y1_rotated + cy)
            symbol.y2 = int(y2_rotated + cy)
    return lines
# symbolデータをparagraphs内で行ごとに連結
def join_bounds(lines):
    bounds = []
    for symbols in lines:
        strline = ''
        x1 = -1
        for symbol in symbols:
            if x1 == -1:
                x1 = symbol.x1
                x2 = symbol.x2
                y1 = symbol.y1
                y2 = symbol.y2
            else:
                if symbol.y1 < y1:
                    y1 = symbol.y1  # 最小値
                x2 = symbol.x2
                if y2 < symbol.y2:
                    y2 = symbol.y2  # 最大値
            strline += symbol.text
        # strline = remove_all_whitespace(strline)
        if x1 != -1:
            bounds.append(TextData(x1, y1, x2, y2, strline))
    return bounds

# paragraphsが違うデータを行ごとにまとめる処理
# bounds : paragraphsごとに行ごとに連結されたデータ
# y座標で並べ替えて高さが近いデータを同じ行のデータとしx座標で並べ替え
def sort_bounds(bounds, angle):
    lines = []
    bounds.sort(key=lambda x: x.y1)
    linebounds = []
    others = []
    adjust = 0
    if angle:
        rad = math.radians(angle)
        adjust = math.tan(rad)
    others = bounds
    while 0 < len(others):
        linebounds,others = sort_bounds_y(others, adjust)
        if 0 < len(linebounds):
            linebounds.sort(key=lambda x: x.x1)
            lines.append(linebounds)
    return lines

# y座標が近いデータを同じ行のデータとする
def sort_bounds_y(bounds, adjust):
    pre_x1 = -1
    pre_x2 = -1
    pre_y1 = -1
    pre_y2 = -1
    firstLoop = True
    threshold = YTHRESHOLD
    linebounds = []
    others = []
    h1 = 0
    h2 = 0
    for bound in bounds:
        x1 = bound.x1
        x2 = bound.x2
        y1 = bound.y1
        y2 = bound.y2
        if firstLoop:
            firstLoop = False
            pre_x1 = x1
            pre_x2 = x2
            pre_y1 = y1
            pre_y2 = y2
            linebounds.append(bound)
        else:
            if adjust:  # 傾きがある場合には調整する
                h1 = (x1 - pre_x1) * adjust
                h2 = (x2 - pre_x2) * adjust
                y1 += h1
                y2 += h2
            # if (pre_y1 < y1 and pre_y2 < y2 and y1 < pre_y2
            #     and ((y1 - pre_y1) * 2 < pre_y2 - y1 or (y2 - pre_y2) * 2 < pre_y2 - y1)):
            #     linebounds.append(bound)
            # elif (y1 < pre_y1 and y2 < pre_y2 and pre_y1 < y2
            #     and ((pre_y1 - y1) * 2 < y2 - pre_y1 or (pre_y2 - y2) * 2 < y2 - pre_y1)):
            #     linebounds.append(bound)
            if (pre_y1 < y1 and pre_y2 < y2 and y1 < pre_y2
                and ((y1 - pre_y1) * 1.5 < pre_y2 - y1 and (y2 - pre_y2) * 1.5 < pre_y2 - y1)):
                linebounds.append(bound)
            elif (y1 < pre_y1 and y2 < pre_y2 and pre_y1 < y2
                and ((pre_y1 - y1) * 1.5 < y2 - pre_y1 and (pre_y2 - y2) * 1.5 < y2 - pre_y1)):
                linebounds.append(bound)
            elif pre_y1 - threshold <= y1 <= pre_y1 + threshold:
                linebounds.append(bound)
            elif pre_y2 - threshold <= y2 <= pre_y2 + threshold:
                linebounds.append(bound)
            elif pre_y1 <= y1 and y2 <= pre_y2:
                linebounds.append(bound)
            elif y1 <= pre_y1 and pre_y2 <= y2:
                linebounds.append(bound)
            else:
                others.append(bound)
    return linebounds, others
# paragraphsが違うデータを行ごとにまとめる処理
# bounds : paragraphsごとに行ごとに連結されたデータ
# y座標で並べ替えて高さが近いデータを同じ行のデータとしx座標で並べ替え
# 傾き調整なし
def sort_bounds_non(bounds):
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

        linebounds.append(bound)
    # pre_x1 = -1
    # pre_y1 = -1
    # pre_y2 = -1
    # for bound in bounds:
    #     x1 = bound.x1
    #     y1 = bound.y1
    #     y2 = bound.y2
    #     if pre_y1 == -1:
    #         pre_x1 = x1
    #         pre_y1 = y1
    #         pre_y2 = y2
    #     # elif pre_y - threshold < y < pre_y + threshold:
    #     elif pre_x1 < x1 and (pre_y2 - threshold < y1 < pre_y2 + threshold):
    #         pre_y1 = y1
    #         pre_y2 = y2
    #     elif x1 < pre_x1 and (pre_y1 - threshold < y2 < pre_y1 + threshold):
    #         pre_y1 = y1
    #         pre_y2 = y2
    #     else:
    #         pre_y1 = -1
    #         if 0 < len(linebounds):
    #             linebounds.sort(key=lambda x: x.x1)
    #             lines.append(linebounds)
    #         linebounds = []
    #         pre_y1 = y1
    #         pre_y2 = y2
    #     linebounds.append(bound)
    if 0 < len(linebounds):
        linebounds.sort(key=lambda x: x.x1)
        lines.append(linebounds)
    return lines
# TextDatasを作成
def bounds_to_textdata(lines):
    page_textdatas = []
    for line in lines:
        for bound in line:
            x1 = bound.x1
            y1 = bound.y1
            x2 = bound.x2
            y2 = bound.y2
            strline = bound.text
            page_textdatas.append(TextData(x1, y1, x2, y2, strline))
    return page_textdatas

def remove_all_whitespace(strtext):
    charArray = []
    for ch in strtext:
        if (ch == '\u0009' or
            ch == '\u000A' or
            ch == '\u000B' or
            ch == '\u000C' or
            ch == '\u000D' or
            ch == '\u0020' or
            ch == '\u00A0' or
            ch == '\u1680' or
            ch == '\u180e' or
            ch == '\u2000' or
            ch == '\u2001' or
            ch == '\u2002' or
            ch == '\u2003' or
            ch == '\u2004' or
            ch == '\u2005' or
            ch == '\u2006' or
            ch == '\u2007' or
            ch == '\u2008' or
            ch == '\u2009' or
            ch == '\u200A' or
            ch == '\u200B' or
            ch == '\u2028' or
            ch == '\u2029' or
            ch == '\u202F' or
            ch == '\u205F' or
            ch == '\u3000' or
            ch == '\u0085' or
            ch == '\uFEFF'):
              pass
        else:
            charArray.append(ch)
    return ''.join(charArray)

# Google Cloud Vision APIのOCR機能を使ってテキスト抽出
# おもて・うらの判別
def sv_detect_trasa(imagefiles):
# 身元証明書のjson読み込み
    path = os.path.join(settings.BASE_DIR, settings.GOOGLE_CLOUD_VISION_KEY).replace(os.sep,'/')
    textdatas = []
    try:
        logger.debug(f'vision.ImageAnnotatorClient {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
        credentials = service_account.Credentials.from_service_account_file(path)
        client = vision.ImageAnnotatorClient(credentials=credentials)
    except Exception:
        logger.exception('vision exception')
        return textdatas

    detecttext_list = []
    files = []
    google_cnt = 0
    for i, imagefile in enumerate(imagefiles):
        input_file = imagefile
        try:
            page_no = i + 1
            with open(input_file, 'rb') as image_file:
                content = image_file.read()
            basename_without_ext = os.path.basename(input_file)
            if GOOGLEOCR:
                logger.debug(f'vision.Image {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
                image = vision.Image(content=content)
                # logger.debug('text_detection' + ut_get_localtime().strftime('%Y/%m/%d %H:%M:%S'))
                # response = client.text_detection(image=image)
                response = client.document_text_detection(
                    image=image,
                    image_context={'language_hints': ['ja']}
                )
                logger.debug(f'document_text_detection {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
                google_cnt += 1
                if settings.DEBUG:
                    detecttext = vision.AnnotateImageResponse.to_json(response)
                    detecttext_list.append(DetectJson(page_no, detecttext))
            else:
                now = ut_get_localtoday()
                time = now.strftime('_%Y%m%d-')
                basename = os.path.basename(imagefiles[0])
                idx = basename.find(time)
                if 0 < idx:
                    file_name =  basename[:idx]
                else:
                    file_name =  basename[:-7]
                response = sv_load_detect_json(file_name, '/data_root/evc_root/_test/detect', page_no)

            # OCRした結果を表示
            # print(response.full_text_annotation.text)
            # json_dir = 'C:\\Evc_root\\SO23120001_root\\json'
            # sv_save_responsetext(input_file, response.full_text_annotation.text, json_dir)

            # 画像の表裏を判別する
            side = get_matched_trasa_text(response.full_text_annotation.text)
            files.append({'name':basename_without_ext, 'res':response, 'image':imagefile, 'side':side})

            logger.debug(f'get_matched_trasa_text {input_file} : {page_no}')
        except Exception:
            logger.exception(f'OCR response exception {input_file}')

    if settings.DEBUG:
        # jsonファイルを保存
        if detecttext_list:
            json_dir = '/data_root/evc_root/json'
            basename = os.path.basename(imagefiles[0])
            now = ut_get_localtoday()
            time = now.strftime('_%Y%m%d-')
            idx = basename.find(time)
            if 0 < idx:
                file_name =  basename[:idx]
            else:
                file_name =  basename[:-7]
            sv_save_detect_json(file_name, detecttext_list, json_dir)

    # 表裏を判別した結果で画像の表裏を一致させる
    detect_dict, images = check_side(files)

    return detect_dict, images, google_cnt
# 表裏を判別した結果で画像の表裏を一致させる
def check_side(files):
    detect_dict = {}
    images = []
    side1 = 0
    side2 = 0
    if 1 < len(files):
        side1 = files[0].get('side')
        side2 = files[1].get('side')
    else:
        if len(files) == 1:
            detect_dict[0] = files[0].get('res')
            images.append(files[0].get('image'))
        return detect_dict, images
    pat = 1
    if side1 == 0 and (side2 == 1 or side2 == 3):
        pat = 2
    if side1 == 2 and side2 != 2:
        pat = 2
    if side1 == 3 and side2 == 1:
        pat = 2
    if pat == 1:
        detect_dict[0] = files[0].get('res')
        detect_dict[1] = files[1].get('res')
        images.append(files[0].get('image'))
        images.append(files[1].get('image'))
    else:   # 表裏が逆
        detect_dict[0] = files[1].get('res')
        detect_dict[1] = files[0].get('res')
        images.append(files[1].get('image'))
        images.append(files[0].get('image'))
    return detect_dict, images

def get_matched_trasa_text(string):
    lists1 = ['生産',
             '商品']
    lists2 = ['農薬登録番号']
    side = 0
    pattern1 = '|'.join(lists1)
    matched_string = get_matched_string(pattern1, string)
    if matched_string:
        side = 1
    pattern2 = '|'.join(lists2)
    matched_string = get_matched_string(pattern2, string)
    if matched_string:
        side += 2
    logger.debug(f'matched side {side=}')
    return side
def get_matched_string(pattern, string):
    try:
        regex = re.compile(pattern)  # 正規表現パターンをコンパイル
        result = regex.search(string)
        if result:
            return result.group()   # マッチした部分を文字列として取得(最初のパターンのみ)
        else:
            return False
    except Exception:
        logger.exception(f'get_matched_string exception {pattern}')
        return False
# Google Cloud Vision APIのOCR機能を使って検出したテキスト
# OCR検出テキストをフォームの領域で抽出しTextDataデータに変換
def sv_extract_trasa_text(detect_dict, areas_dict, page_cnt):
    textdatas = []
    for page_no in range(1, page_cnt + 1):
        try:
            # page_textdatas = get_lines(page_no, detect_dict.get(page_no - 1), areas_dict.get(page_no - 1))

            symbol_textdatas,page_width,page_height = get_symbols_textdatas(page_no, detect_dict.get(page_no - 1))
            page_textdatas = get_area_textdatas(page_no, symbol_textdatas,
                                                 page_width, page_height, areas_dict.get(page_no - 1))

            textdatas.extend(page_textdatas)
        except Exception:
            logger.exception(f'sv_extract_trasa_text exception {page_no=}')
    return textdatas
