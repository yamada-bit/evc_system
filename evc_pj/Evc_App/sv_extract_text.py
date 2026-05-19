import os
import io
import logging
import datetime
import math
from google.cloud import vision
from google.oauth2 import service_account

from django.conf import settings
from commons.utils import ut_get_localtime

from Evc_App.sv_file import TextData,TextDatas,DetectJson
from Evc_App.sv_json import sv_save_responsetext,sv_save_detect_json,sv_load_detect_json

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

# GOOGLEOCR = True
GOOGLEOCR = settings.GOOGLE_OCR

logger = logging.getLogger(__name__)

# Google Cloud Vision APIのOCR機能を使ってテキスト抽出
# TextDatasの配列で返す
def sv_extract_text(imagefiles, areas_dict, specif_page_list):
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
    google_cnt = 0
    page_count = len(imagefiles) if imagefiles else 1
    for i, imagefile in enumerate(imagefiles):
        input_file = imagefile
        page_no = i + 1
        try:
            if 1 < page_count and specif_page_list and page_no not in specif_page_list:
                continue
            with io.open(input_file, 'rb') as image_file:
                content = image_file.read()
            if GOOGLEOCR:
                logger.debug(f'vision.Image {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
                image = vision.Image(content=content)
                response = client.document_text_detection(
                    image=image,
                    image_context={'language_hints': ['ja']}
                )
                logger.debug(f'document_text_detection {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
                google_cnt += 1
                if settings.DEBUG:
                    # デバッグ用にjsonファイルで保存するためのデータ
                    detecttext = vision.AnnotateImageResponse.to_json(response)
                    detecttext_list.append(DetectJson(page_no, detecttext))
            else:
                # デバッグではGoogleOCRは呼び出さずjsonファイルからデータを取り出す。
                basename_without_ext = os.path.basename(input_file)
                now = ut_get_localtime()
                time = now.strftime('_%Y%m%d-')
                idx = basename_without_ext.find(time)
                if 0 < idx:
                    file_name =  basename_without_ext[:-29]
                else:
                    file_name =  basename_without_ext[:-7]
                response = sv_load_detect_json(file_name, '/data_root/evc_root/_test/detect', page_no)
                # response = sv_load_detect_json(file_name, 'C:\\Evc_root\\_test\\detect\\202311', page_no)

            # OCRした結果を表示
            # print(response.full_text_annotation.text)
            # json_dir = 'C:\\Evc_root\\SO23120001_root\\json'
            # sv_save_responsetext(file_name, response.full_text_annotation.text, json_dir)
            # logger.debug('sv_extract_text pages : ' + input_file + ' ' + str(len(response.full_text_annotation.pages)))

            textdatas.extend(get_lines(page_no, response, areas_dict.get(i)))
            logger.debug(f'get textdatas {input_file} : {page_no}')

        except Exception:
            logger.exception(f'OCR response exception {input_file} : {page_no}')
    return textdatas, detecttext_list, google_cnt

# jsonファイルに保存したGoogle Cloud Vision APIのOCR機能を使って抽出したデータを読込
# 領域ごとに分割して抽出しTextDatasの配列で返す
def sv_get_detecttext_from_json(evidence_id, json_dir, page_no, areas):
    textdatas = []
    response = sv_load_detect_json(evidence_id, json_dir, page_no)
    try: 
        textdatas.extend(get_lines(page_no, response, areas))
    except Exception:
        logger.exception(f'sv_get_detecttext exception {evidence_id=}')
    return textdatas

# block内でsymbolデータをy座標でソートして行ごとにx座標でソート
def get_lines(page_no, response, areas):
    textdatas = []
    sp = ' '
    sure_sp = ' '
    eol = '\n'
    hyphen = '-\n'
    linebreak = '\n'
    unk = ''

    for page in response.full_text_annotation.pages:
        page_width = page.width
        page_height = page.height
        rotate_angle = get_rotate_angle(page)
        if not areas:
            areas = [(0, 0, page_width, page_height)]
        area_no = 0
        for area in areas:
            area_no += 1
            start_x = area[0]
            start_y = area[1]
            end_x = area[2]
            end_y = area[3]
            center_x = (start_x + end_x) / 2
            center_y = (start_y + end_y) / 2

            lines = []
            degrees = []
            angleps= []
            anglems = []
            for block in page.blocks:
                    # bounds = []
                x11 = block.bounding_box.vertices[0].x
                y11 = block.bounding_box.vertices[0].y
                x22 = block.bounding_box.vertices[2].x
                y22 = block.bounding_box.vertices[2].y
                x1 = min(x11, x22)
                y1 = min(y11, y22)
                x2 = max(x11, x22)
                y2 = max(y11, y22)
                if end_x < x1 or x2 < start_x or end_y < y1 or y2 < start_y:
                    continue
                for paragraph in block.paragraphs:
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
                        wx1 = min(wx11, wx22)
                        wy1 = min(wy11, wy22)
                        wx2 = max(wx11, wx22)
                        wy2 = max(wy11, wy22)

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
                            symbols.append(TextData(wx1, wy1, wx2, wy2, pre + symbol.text + post))
                            # if start_x <= wx1 and wx2 <= end_x and start_y <= wy1 and  wy2 <= end_y:    # 全体が含まれているか
                            #     symbols.append(TextData(wx1, wy1, wx2, wy2, pre + symbol.text + post))
                            # pre_wx1 = wx1
                            # pre_wx2 = wx2
                            # pre_wy1 = wy1
                            # pre_wy2 = wy2

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
