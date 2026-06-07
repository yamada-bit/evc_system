import base64
import logging
import os
from io import BytesIO

import cv2
import numpy as np

# import pandas as pd
# import matplotlib.pyplot as plt
import PIL.Image  # exifから回転情報取得
from django.conf import settings
from pypdf import PdfReader

from Evc_App.sv_file import TextData, TextDatas

logger = logging.getLogger(__name__)
pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.INFO)

# PDFファイルのページ数を取得
def sv_get_pdfpages(pdfpath):
    try:
        basename_without_ext, ext_name = os.path.splitext(os.path.basename(pdfpath))
        if ext_name.lower() == '.pdf':
            reader = PdfReader(pdfpath)
            return len(reader.pages)
        else:
            return 1
    except Exception:
        logger.exception(f'sv_get_pdfpages exception {pdfpath=}')
        return 0
# 画像の分割領域を取得
def sv_get_image_shape(file_path):
    areas = []
    # 画像処理のフラグ
    # flag_image_process = 'triangle' #  IMG-1 IMG-2602 test.pdf
    # flag_image_process = 'multy'    # タイトルなし.jpg  領収書test4分割.pdf
    flag_image_process = 'otsu' #  IMG-1 IMG-2602 test.pdf IMG-192(silver)

    # 画像をOpenCVで読み込む
    # img = cv2.imread(file_path)
    # OpenCVではファイル名やパスに日本語が含まれていると、画像ファイルが開けない
    # NumPyで画像ファイルを開く
    buf = np.fromfile(file_path, np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    height, width = img.shape[:2]
    # グレースケールに変換
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 閾値処理
    # cv2.THRESH_OTSU、cv2.THRESH_TRIANGLE を指定すると、閾値を画像から自動的に決める
    if flag_image_process == 'triangle':
        # THRESH_TRIANGLE しきい値は設定しても無視されるため、0を使用
        ret,dst = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_TRIANGLE)
    elif flag_image_process == 'otsu':
        ret,dst = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # 5x5のサイズのgaussianフィルタでノイズを抑制
        # blur = cv2.GaussianBlur(gray,(5,5),0)
        # ret,dst = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif flag_image_process == 'multy':
        # ヒストグラム平坦化
        dst = cv2.equalizeHist(gray)
        # 白黒反転
        dst = 255 - dst
        # パイラテラルフィルタ
        dst = cv2.bilateralFilter(dst, 5, 100, 100)
        # ノイズ除去
        dst = cv2.fastNlMeansDenoising(dst, h = 20)
        #dst = cv2.fastNlMeansDenoising(dst, None, 30, 10, 7)
        # しきい値調整（大津処理）
        retval, dst = cv2.threshold(dst, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        # エッジの抽出
        # Canny法
        # wkimg = cv2.Canny(image=gray, threshold1=100, threshold2=130)
        med_val = np.median(gray)
        sigma = 0.33  # 0.33
        min_val = int(max(0, (1.0 - sigma) * med_val))
        max_val = int(max(255, (1.0 + sigma) * med_val))
        wkimg = cv2.Canny(image=gray, threshold1=min_val, threshold2=max_val)

        # エッジの結合
        # 膨張:カーネル内に画素値が ‘1’ の画素が一つでも含まれれば，出力画像の注目画素の画素値を ‘1’ にします
        # 収縮:カーネルの領域に含まれる画素の画素値が全て1であれば1
        # 膨張の後に収縮

        no = 8 # 領収書test4分割.pdf
        # no = 10 # タイトルなし.jpg
        wkimg = cv2.morphologyEx(wkimg, cv2.MORPH_CLOSE, np.ones((10 * no, 10 * no), dtype=wkimg.dtype))

        # 二値画像の生成
        # threshを超えたピクセルにはmaxValueで指定した値が割り当てられます。
        # ret,thresh1 = cv2.threshold(wkimg2,95,255,cv2.THRESH_BINARY)
        # ret,thresh1 = cv2.threshold(wkimg2,127,255,cv2.THRESH_BINARY)

        ret,dst = cv2.threshold(wkimg, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_TRIANGLE)
        # dst = cv2.adaptiveThreshold(wkimg, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 255, 2)
    # median = cv2.medianBlur(thresh1, 3)

    # 輪郭検出
    contours, hierarchy = cv2.findContours(dst, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    for i in range(0, len(contours)):
        if 0 < len(contours[i]):
            # remove small objects
            if cv2.contourArea(contours[i]) < 40000:    # 50000 ピクセル未満のオブジェクトは無視
                continue
            rect = contours[i]
            x, y, w, h = cv2.boundingRect(rect)
            areas.append((x, y, x + w, y + h))
    areas = get_area(areas, width, height)
    return areas
# 画像サイズの領域と領域内の領域は除外
def get_area(areas, w, h):
    areas2 = []
    for area0 in areas:
        x01 = area0[0]
        y01 = area0[1]
        x02 = area0[2]
        y02 = area0[3]
        if x01 < 10 and w - 10 < x02 and y01 < 10 and h - 10 < y02:
            continue
        areas2.append(area0)
    areas3 = []
    for area0 in areas2:
        x01 = area0[0]
        y01 = area0[1]
        x02 = area0[2]
        y02 = area0[3]
        in_skip = False
        for area1 in areas2:
            if area0 != area1:
                x11 = area1[0]
                y11 = area1[1]
                x12 = area1[2]
                y12 = area1[3]
                if x11 <= x01 and x02 <= x12 and y11 <= y01 and y02 <= y12:
                    in_skip = True
                    break
        if not in_skip:
            areas3.append(area0)
    logger.debug(f'areas count : {len(areas)} -> {len(areas3)}')
    return areas3

# 回転角度を取得
def sv_get_image_angle(file_path):
    angle = 0
    orientation = get_exif_rotation(file_path)
    if orientation == 1:    # Normal image - nothing to do!
        pass
    elif orientation == 2:  # Mirrored left to right
        pass
    elif orientation == 3:  # Rotated 180 degrees
        angle = 180
    elif orientation == 4:  # Mirrored top to bottom
        angle = 180
    elif orientation == 5:  # Mirrored along top-left diagonal
        angle = 90
    elif orientation == 6:  # Rotated 90 degrees
        angle = 90
    elif orientation == 7:  # Mirrored along top-right diagonal
        angle = 270
    elif orientation == 8:  # Rotated 270 degrees
        angle = 270
    return angle
# exifから回転情報を取得
def get_exif_rotation(file_path):
    if not file_path:
        return 1
    exif_orientation_tag = 274
    img = PIL.Image.open(file_path)
    if hasattr(img, '_getexif') and isinstance(img._getexif(), dict) and exif_orientation_tag in img._getexif():
        exif_data = img._getexif()
        orientation = exif_data[exif_orientation_tag]
        return orientation
    else:
        return 1
# Base64に変換された画像データをデコードして保存
def sv_upload_file_base64(base64Data, path):
    if path:
        try:
            img_base64 = base64Data.replace('data:image/jpeg;base64,', '')  # 冒頭の部分を削除
            img_binary = base64.b64decode(img_base64)   # base64に変換された画像データを元のバイナリデータに変換

            # jpg = np.frombuffer(img_binary, dtype=np.uint8)
            # img = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
            # 画像を保存する
            # cv2.imwrite(path, img)    # OpenCVでは日本語エラー
            # カラー画像のときは、BGRからRGBへ変換する
            # if img.ndim == 3:
            #     img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            # # NumPyからPillowへ変換
            # pil_image = PIL.Image.fromarray(img)

            pil_image = PIL.Image.open(BytesIO(img_binary)) # PILのImageでメモリ上のバイナリデータを開く

            pil_image.save(path)    # Pillowで画像ファイルへ保存
            logger.debug(f'sv_upload_file_base64 {path=}')
        except Exception:
            logger.exception(f'b64decode exception {path=}')
            path = False
    return path
# 分割画像ファイル作成
def sv_get_cropped_image(imagefile, area, cropped_image_file, angle):
    # OpenCVではファイル名やパスに日本語が含まれていると、画像ファイルを開いてくれません。
    # NumPyで画像ファイルを開く

    try:
        buf = np.fromfile(imagefile, np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        # img = cv2.imread(imagefile)
        if area and len(area) == 4:
            start_x = area[0]
            start_y = area[1]
            end_x = area[2]
            end_y = area[3]
            cropped_image = img[start_y:end_y, start_x:end_x]
            # if angle == 90:
            #     # 時計回りに90度回転
            #     cropped_image = cv2.rotate(cropped_image,cv2.ROTATE_90_CLOCKWISE)
            # elif angle == 180:
            #     cropped_image = cv2.rotate(cropped_image,cv2.ROTATE_180)
            # elif angle == 270:
            #     cropped_image = cv2.rotate(cropped_image,cv2.ROTATE_90_COUNTERCLOCKWISE)
            cv2.imwrite(cropped_image_file, cropped_image)
        logger.debug(f'sv_get_cropped_image {cropped_image_file}')
    except Exception:   # ValueError
        logger.exception(f'sv_get_cropped_image exception {imagefile=}')
        return False
    return cropped_image_file
# def get_image_rotation(img, orientation):
#     if orientation == 1:
#         # Normal image - nothing to do!
#         pass
#     elif orientation == 2:
#         # Mirrored left to right
#         # img = img.transpose(PIL.Image.FLIP_LEFT_RIGHT)
#         img = cv2.flip(img, 1)
#     elif orientation == 3:
#         # Rotated 180 degrees
#         # img = img.rotate(180)
#         img = cv2.rotate(img, cv2.ROTATE_180)
#     elif orientation == 4:
#         # Mirrored top to bottom
#         # img = img.rotate(180).transpose(PIL.Image.FLIP_LEFT_RIGHT)
#         img = cv2.rotate(img, cv2.ROTATE_180)
#         img = cv2.flip(img, 1)
#     elif orientation == 5:
#         # Mirrored along top-left diagonal
#         # img = img.rotate(-90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
#         img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
#         img = cv2.flip(img, 1)
#     elif orientation == 6:
#         # Rotated 90 degrees
#         # img = img.rotate(-90, expand=True)
#         img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
#     elif orientation == 7:
#         # Mirrored along top-right diagonal
#         # img = img.rotate(90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
#         img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
#         img = cv2.flip(img, 1)
#     elif orientation == 8:
#         # Rotated 270 degrees
#         # img = img.rotate(90, expand=True)
#         img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

#     return img

# def binarize(img):
#     """画像を2値化する
#     """
#     gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     binary_img = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 255, 2)
#     cv2.imwrite('D:/EVC/Evc_root/owner3_root/upload/json/binary_img.png', binary_img)
#     return binary_img

# def noise_reduction(img):
#     """ノイズ処理(中央値フィルタ)を行う
#     """
#     median = cv2.medianBlur(img, 9)
#     cv2.imwrite('D:/EVC/Evc_root/owner3_root/upload/json/median.png', median)
#     return median

# def find_contours(img):
#     """輪郭の一覧を得る
#     """
#     contours, _ = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
#     return contours

# def approximate_contours(img, contours):
#     """輪郭を条件で絞り込んで矩形のみにする
#     """
#     height, width, _ = img.shape
#     img_size = height * width
#     approx_contours = []
#     for i, cnt in enumerate(contours):
#         arclen = cv2.arcLength(cnt, True)
#         area = cv2.contourArea(cnt)
#         if arclen != 0 and img_size*0.02 < area < img_size*0.9:
#             approx_contour = cv2.approxPolyDP(cnt, epsilon=0.05*arclen, closed=True)
#             if len(approx_contour) == 4:
#                 approx_contours.append(approx_contour)
#     return approx_contours

# def draw_contours(img, contours, file_name):
#     """輪郭を画像に書き込む
#     """
#     draw_contours = cv2.drawContours(img.copy(), contours, -1, (0, 0, 255, 255), 10)
#     cv2.imwrite('D:/EVC/Evc_root/owner3_root/upload/json/{}.png'.format(file_name), draw_contours)

# def get_receipt_contours(img):
#     """矩形検出までの一連の処理を行う
#     """
#     binary_img = binarize(img)
#     binary_img = noise_reduction(binary_img)
#     contours = find_contours(binary_img)
#     approx_contours = approximate_contours(img, contours)
#     draw_contours(img, contours, 'draw_all_contours')
#     draw_contours(img, approx_contours, 'draw_rectangle_contours')

# 矩形領域を抽出(左上からソート) フォームの項目領域取得
def sv_get_contour_rect(filepath, page_no):
    bounds = []
    textdatas = []
    try:
        # cv2_image = cv2.imread(filename)
        # OpenCVではファイル名やパスに日本語が含まれていると、画像ファイルが開けない NumPyで画像ファイルを開く
        buf = np.fromfile(filepath, np.uint8)
        cv2_image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        height, width = cv2_image.shape[:2]
        gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)

        # edge = cv2.Canny(gray, 1, 100, apertureSize=7)
        edge = cv2.Canny(gray, 100, 200)    # Canny 法でエッジを抽出する
        if settings.DEBUG:
            cv2.imwrite('../edge/edge.jpg', edge)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))  # カーネルの作成
        edge2 = cv2.dilate(edge, kernel)    # エッジ画像を膨張処理
        if settings.DEBUG:
            cv2.imwrite('../edge/edge2.jpg', edge2)
        # 輪郭上の座標を取得
        contours, hierarchy = cv2.findContours(edge2, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        # Contoursの情報から、必要なContourだけを抽出する
        rects = []
        # zip 複数のシーケンスをまとめてループ(一番短いリストに合わせて処理)
        for contour, hierarchy in zip(contours, hierarchy[0]):
            # 面積でフィルタリング
            if cv2.contourArea(contour) < 3000:
                continue  # 面積が小さいものは除く
            if hierarchy[3] == -1:
                continue  # ルートノードは除く
            # 輪郭の傾きを考慮した矩形領域を取得する。
            # rect = cv2.minAreaRect(contour)
            # points = cv2.boxPoints(rect).astype(int)
            # # rects.append(points)
            # x1 = min(points[0][0], points[1][0], points[2][0], points[3][0])
            # y1 = min(points[0][1], points[1][1], points[2][1], points[3][1])
            # x2 = max(points[0][0], points[1][0], points[2][0], points[3][0])
            # y2 = max(points[0][1], points[1][1], points[2][1], points[3][1])
            # bounds.append(TextData(x1, y1, x2, y2, ''))

            # 輪郭の外接矩形を取得
            x, y, w, h = cv2.boundingRect(contour)
            bounds.append(TextData(x, y, x + w, y + h, ''))
        # rects = sorted(rects, key=lambda x: (x[0][1], x[0][0]))
        # bounds = sorted(bounds, key=lambda x: (x.y1, x.x1))
        bounds = sort_bounds(bounds)    # y座標のずれを考慮
        bounds = check_bounds(bounds)
        textdatas.append(TextDatas(1, page_no, 1, width, height, bounds))

    except Exception:
        logger.exception(f'sv_get_contour_rect exception {filepath=}')
        # return textdatas, ''
    return textdatas
    # if not settings.DEBUG:
    #     return textdatas, ''
    # try:
    #     # 矩形を描画
    #     rect_image = cv2_image.copy()
    #     # for i, rect in enumerate(rects):
    #     #     color = np.random.randint(0, 255, 3).tolist()
    #     #     cv2.drawContours(rect_image, rects, i, color, 2)
    #     #     cv2.putText(rect_image, str(i), tuple(rect[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 3)

    #     #     print('rect:\n', rect)
    #     for i, bound in enumerate(bounds):
    #         # color = np.random.randint(0, 255, 3).tolist()
    #         color = (0, 255, 255)
    #         cv2.rectangle(rect_image,
    #             pt1=(bound.x1, bound.y1),
    #             pt2=(bound.x2, bound.y2),
    #             color=color,
    #             thickness=2,
    #             lineType=cv2.LINE_4,
    #             shift=0)
    #         cv2.putText(rect_image, str(i + 1), (bound.x1, bound.y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 3)
    #         # print('rect:\n', bound)

    #     out = filepath.replace('.jpg', '_rect.jpg')
    #     # cv2.imwrite(out, rect_image)    # 日本語ファイル名は文字化けのためNumPyかPillowで保存
    #     # 保存するときはPillowが速いので NumPyからPillowへ変換
    #     pil_image = PIL.Image.fromarray(rect_image)
    #     pil_image.save(out)
    # except Exception:
    #     logger.exception('sv_get_contour_rect image save exception : ' + filepath)
    #     out = ''
    # return textdatas, out

def sort_bounds(bounds):
    lines = []
    bounds.sort(key=lambda x: x.y1)
    pre_y = -1
    threshold = 8
    linebounds = []
    for bound in bounds:
        y = bound.y1
        if pre_y == -1:
            pre_y = y
        elif pre_y - threshold <= y <= pre_y + threshold:
            pre_y = y
        else:
            pre_y = -1
            if 0 < len(linebounds):
                linebounds.sort(key=lambda x: x.x1)
                for line in linebounds:
                    lines.append(line)
            linebounds = []
            pre_y = y
        linebounds.append(bound)
    if 0 < len(linebounds):
        linebounds.sort(key=lambda x: x.x1)
        for line in linebounds:
            lines.append(line)
    return lines
def check_bounds(bounds):
    lines = []
    idx = 0
    for bound in bounds:
        x1 = bound.x1
        x2 = bound.x2
        y1 = bound.y1
        y2 = bound.y2
        flag = False
        for line in bounds:
            if x1 < line.x1 and line.x2 < x2 and y1 < line.y1 and line.y2 < y2:
                flag = True # 内側に別の枠が含まれる
                break
        if not flag:    # 内側の枠のみ
            bound.text = str(idx + 1)
            lines.append(bound)
            idx += 1
    return lines

# def sv_get_area_angle(imgpath, areas):
#     angle = 0
#     angles = []
#     try:
#         buf = np.fromfile(imgpath, np.uint8)
#         img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
#         for area in areas:
#             if area and len(area) == 4:
#                 start_x = area[0]
#                 start_y = area[1]
#                 end_x = area[2]
#                 end_y = area[3]
#                 cropped_image = img[start_y:end_y, start_x:end_x]
#                 angle = get_image_angle(cropped_image)
#                 angles.append(angle)
#     except Exception:
#         logger.exception('sv_get_area_angle exception : ' + imgpath)
#     return angles

# def sv_get_angle(imgpath):
#     angle = 0
#     angles = []
#     try:
#         buf = np.fromfile(imgpath, np.uint8)
#         img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
#         angle = get_image_angle(img)
#         logger.debug('sv_get_angle : ' + str(angle))
#     except Exception:
#         logger.exception('sv_get_angle exception : ' + imgpath)
#     angles.append(angle)
#     return angles

# def get_image_angle(img):
#     angle = 0
#     try:
#         height, width = img.shape[:2]
#         center = (int(width/2), int(height/2))  # 中心座標設定
#         # グレースケールに変換
#         img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#         # ret, img_binary = cv2.threshold(img_gray, 180, 255, cv2.THRESH_BINARY)  # 輝度180を境界に二値化
#         ret, img_binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

#         contours, hierarchy = cv2.findContours(img_binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)  # 領域検出
#         # 輪郭の選択
#         # 面積が小さい輪郭削除 「3000」のところの数値より小さい輪郭は削除
#         # cnts = list(filter(lambda cnts: 3000 < cv2.contourArea(cnts), contours))
#         sum_arg = 0
#         count = 0
#         for contour in contours:
#             area = cv2.contourArea(contour)  # 各領域の面積
#             if 10000 < area:
#                 rect = cv2.minAreaRect(contour)  # 傾いた外接する矩形領域
#                 angle = rect[2]  # rectは中心座標(x,y), (width, height), 回転角度
#                 # [-90, 0] の範囲の値
#                 sum_arg += angle
#                 count += 1
#         if 0 < count:
#             angle = int(sum_arg / count)
#             if 45 < angle:
#                 angle = 90 - angle
#         logger.debug('get_image_angle : ' + str(angle))
#     except Exception:
#         logger.exception('get_image_angle exception')
#     return angle

# Python OpenCV の cv2.imwrite で日本語を含むファイルパスを取り扱う際の問題への対処
# cv2.imwrite を cv2.imencode + np.ndarray.tofile に分解して実行
def sv_imwrite(filename, img, params=None):
    try:
        ext = os.path.splitext(filename)[1]
        result, n = cv2.imencode(ext, img, params)
        if result:
            with open(filename, mode='w+b') as f:
                n.tofile(f)
            return True
        else:
            return False
    except Exception:
        logger.exception(f'sv_imwrite exception {filename=}')
        return False
