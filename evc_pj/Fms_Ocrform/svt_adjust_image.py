import logging
import os
import shutil

import cv2
import numpy as np
from django.conf import settings

from Evc_App.sv_file import get_imgfolder_upload
from Evc_App.sv_get_image_shape import sv_get_image_angle, sv_imwrite
from Fms_Ocrform.svf_ocrform import (
    get_ocrform_image_dir,
    get_ocrform_imagefile,
    get_ocrform_rootfolder,
)

logger = logging.getLogger(__name__)

# 同じファイル名がある場合に（連番）追加
def check_filename(file):
    if os.path.exists(file):
        filepath, ext = os.path.splitext(file)
        i = 1
        while i < 100000:
            new_path = f'{filepath}({i}){ext}'
            if not os.path.exists(new_path):
                return new_path
            i += 1
    return file
# 入力画像をフォーム画像に合わせる（射影変換）台形補正はこちら
# 四角形マーク座標で比較
def svt_adjust_image_trapezoid(ocrimages, ocrform_id):
    adjusts = []
    for i, imagepath in enumerate(ocrimages, start=1):
        if not imagepath or not os.path.exists(imagepath):
            continue
        try:
            rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
            formimg_dir = get_ocrform_image_dir(rootfolder)
            file_name = get_ocrform_imagefile(formimg_dir, ocrform_id, i)
            img_dir = get_imgfolder_upload(rootfolder)

            # NumPyで画像ファイルを開く
            # buf = np.fromfile(file_name, np.uint8)   # フォーム
            # form_image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
            # height, width = form_image.shape[:2]
            width = 1654    # フォーム画像の幅
            height = 2339   # フォーム画像の高さ
            # apt1 = svt_get_nparray(file_name)   # フォームの四角形マーク座標
            if i == 1:  # フォームのおもての四角形マーク座標
                apt1 = np.array([[86,129],[1526,129],[1526,2241],[86,2241]])
                # apt1 = np.array([[96,139],[1520,139],[1520,2241],[96,2241]])
                # apt1 = np.array([[84,129],[1474,129],[1474,2241],[84,2241]])
                # apt1 = np.array([[110,152],[1550,152],[1550,2264],[110,2264]])
            else:       # フォームのうらての四角形マーク座標
                apt1 = np.array([[86,129],[1526,129],[1526,2229],[86,2229]])
            # if i == 1:
            #     apt1 = np.array([[86,129],[134,128],[135,175],[87,176],
            #             [1526,129],[1574,128],[1575,175],[1527,176],
            #             [86,2241],[134,2240],[135,2287],[87,2288]])
            # else:
            #     apt1 = np.array([[86,129],[134,128],[135,175],[87,176],
            #             [1526,129],[1574,128],[1575,175],[1527,176],
            #             [86,2229],[134,2228],[135,2275],[87,2276]])
            # 射影変換で入力画像を変換しフォーム画像に合わせる
            img = get_adjust_trapezoid(imagepath, width, height, apt1)

            basename = os.path.basename(imagepath)
            file_name =  os.path.join(img_dir, 'adjust_' + basename).replace(os.sep,'/')
            # cv2.imwrite(file_name, img)
            # 射影変換で変換した入力画像をファイルに出力
            sv_imwrite(file_name, img)
            # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
             # ファイルに出力した変換画像にアップロード画像を入れ替える
            shutil.move(file_name, imagepath)
            adjusts.append(imagepath)
            # adjusts.append(file_name)
        except Exception:   # ValueError
            logger.exception(f'svt_adjust_image_trapezoid exception {imagepath=}')
    return adjusts

# 射影変換で任意の四角形から別の任意の四角形への変換。台形補正はこちら
def get_adjust_trapezoid(image_path, width, height, apt1):
    buf = np.fromfile(image_path, np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    angle = sv_get_image_angle(image_path)
    if angle == 90:
        # 時計回りに90度回転
        img = cv2.rotate(img,cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        img = cv2.rotate(img,cv2.ROTATE_180)
    elif angle == 270:
        img = cv2.rotate(img,cv2.ROTATE_90_COUNTERCLOCKWISE)
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # 写真に影が映りこむと正しく判定できない場合がありHSVを使用
    # RGBからHSVに変換
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # 色相の範囲による閾値処理・色抽出
    # 白黒の画像を作成(2値化)する
    # 指定された範囲内にあるピクセルが白に、範囲外のピクセルが黒に設定された2値のマスク
    hsv_img = cv2.inRange(hsv, (0, 0, 0), (179, 255, 70))   # パターン1
    # hsv_img = cv2.inRange(hsv, (0, 0, 0), (179,196,70))

    apt2,rimage = get_mark_nparray(hsv_img, img.copy())
    rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
    img_upload_dir = get_imgfolder_upload(rootfolder)

    if settings.DEBUG:
        match_img = os.path.join(img_upload_dir, 'bin-1-hsv.jpg').replace(os.sep,'/')
        match_img = check_filename(match_img)
        # inRange による 2 値化した画像を出力
        cv2.imwrite(match_img, hsv_img)
        match_img = os.path.join(img_upload_dir, 'mark-1-hsv.jpg').replace(os.sep,'/')
        match_img = check_filename(match_img)
        # 元の画像に赤枠描画
        cv2.imwrite(match_img, rimage)
    if len(apt2) < 4:   # 4点取得できない場合
        hsv_img2 = cv2.inRange(hsv, (0, 0, 0), (179,128,120))   # パターン2
        apt22,rimage2 = get_mark_nparray(hsv_img2, img.copy())
        # apt22,rimage2 = get_mark_nparray_polygon(hsv_img2, img.copy())
        if settings.DEBUG:
            match_img = os.path.join(img_upload_dir, 'bin-2-hsv.jpg').replace(os.sep,'/')
            match_img = check_filename(match_img)
            # inRange による 2 値化した画像を出力
            cv2.imwrite(match_img, hsv_img2)
            match_img = os.path.join(img_upload_dir, 'mark-2-hsv.jpg').replace(os.sep,'/')
            match_img = check_filename(match_img)
            # 元の画像に赤枠描画
            cv2.imwrite(match_img, rimage2)
        logger.debug(f'get_mark_nparray apt2={len(apt2)}:apt22={len(apt22)}')
        if len(apt2) < len(apt22):
            apt2 = apt22
            rimage = rimage2
        # if len(apt2) < 4:
        #     apt23, rimage3 = get_mark_nparray_polygon(hsv_img, img.copy())
        #     if len(apt23) < 4:
        #         apt24, rimage4 = get_mark_nparray_polygon(hsv_img2, img.copy())
        #         if len(apt23) < len(apt24):
        #             apt2 = apt24
        #     else:
        #         apt2 = apt23

    # 用紙の四隅の座標を取得する

    # 用紙枠の抽出には cv2.COLOR_BGR2GRAY を使う
    # BGRをグレースケールに変換
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 大津の2値化でグレースケール画像を2値化
    _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    img_height, img_width = bin_img.shape[:2]
    contours, _ = cv2.findContours(bin_img, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    # max_contour = None
    max_approx = None
    max_area = img_height * img_width * 0.7
    for contour in contours:
        # area = cv2.contourArea(contour)
        # if max_area < area:
            # max_area = area
            # max_contour = contour
        # 輪郭線の長さを計算
        arclen = cv2.arcLength(contour, True)
        # 長さの10%の精度を持つように輪郭線を近似
        approx = cv2.approxPolyDP(contour, 0.1 * arclen, True)
        # cnt = approx.shape[0]   # 座標数が４でない場合に対処のため未使用
        area = abs(cv2.contourArea(approx))
        if max_area < area:
            max_area = area
            max_approx = approx
    # arc_len = cv2.arcLength(max_contour, True)
    # approx_contour = cv2.approxPolyDP(max_contour, epsilon=0.1 * arc_len, closed=True)
    # approx = approx_contour.tolist()
    if max_approx is None:
        # 入力画像の四隅の座標を使う
        logger.debug('max_approx None')
        left_down = [[0, 0]]
        left_up = [[0, img_height]]
        right_down = [[img_width, 0]]
        right_up = [[img_width, img_height]]
    else:
        approx = max_approx.tolist()
        # 座標数が４でない場合に用紙枠の座標を使う
        lefts = []
        rights = []
        for pt in approx:
            if pt[0][0] < img_width / 2:
                lefts.append(pt)
            else:
                rights.append(pt)
        # lefts = sorted(approx, key=lambda x: x[0])[:2]
        # rights = sorted(approx, key=lambda x: x[0])[2:]
        left_down = sorted(lefts, key=lambda x: x[0][1])[0]
        left_up = sorted(lefts, key=lambda x: x[0][1])[len(lefts)-1]
        right_down = sorted(rights, key=lambda x: x[0][1])[0]
        right_up = sorted(rights, key=lambda x: x[0][1])[len(rights)-1]

    if len(apt2) == 4:
        # 4個の四角形マークの左上座標を使う
        perspective = np.float32([apt1[0], apt1[1], apt1[2], apt1[3]])  # フォーム
        perspective_base = np.float32([apt2[0], apt2[1], apt2[2], apt2[3]])
        # perspective_base = np.float32([apt2[0], apt2[8],  [2852, 3531], apt2[4]])
    elif len(apt2) == 3:
        # 3個の四角形マークの左上座標と用紙の右下座標を使う
        perspective = np.float32([apt1[0], apt1[1], [width, height], apt1[3]])  # フォーム
        perspective_base = np.float32([apt2[0], apt2[1], right_up[0], apt2[2]])
    else:   # 用紙の四隅の座標を使う
        logger.debug(f'get_mark_nparray failed apt2={len(apt2)}')
        # フォームの四隅の座標
        perspective = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
        # 入力画像の四隅の座標
        perspective_base = np.float32([left_down, right_down, right_up, left_up])

    if settings.DEBUG:
        if len(apt2) != 4:
            match_img = os.path.join(img_upload_dir, 'bin-gray.jpg').replace(os.sep,'/')
            match_img = check_filename(match_img)
            # 大津の2値化でグレースケール画像を2値化した画像を出力
            cv2.imwrite(match_img, bin_img)
            match_img = os.path.join(img_upload_dir, 'paper-frame.jpg').replace(os.sep,'/')
            match_img = check_filename(match_img)
            rimage = img.copy()
            # 用紙枠描画
            cv2.polylines(rimage, [perspective_base.astype(int)], True, (0,0,255), thickness=5, lineType=cv2.LINE_8)
            # 用紙枠を描画した画像出力
            cv2.imwrite(match_img, rimage)

    # 変換前の4点の座標と変換後の4点の座標から射影変換の変換行列を生成
    # 4点の座標をNumPy配列ndarrayで指定、ndarrayのデータ型dtypeはfloat32
    psp_matrix = cv2.getPerspectiveTransform(perspective_base, perspective)
    # 射影変換
    adjust_img = cv2.warpPerspective(img, psp_matrix, (width, height))
    return adjust_img

# 画像上の四角形マーク座標を取得
def get_mark_nparray(bin_image, image):
    # 輪郭取得
    contours, _ = cv2.findContours(bin_image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    height, width = bin_image.shape[:2]
    areamin = (width / 50) * (width / 50)
    areamax = (width / 10) * (width / 10)
    wmin = width * 40 / 3000 # 48 / 1654  71/3024
    wmax = width * 60 / 1300 # 48 / 1394
    wmin = width * 40 / 3000 # 2.8mm  48/1654-6mm
    wmax = width * 100 / 3000 # 7mm
    areamin = wmin * wmin
    areamax = wmax * wmax
    left_top = [width, height]
    right_top = [0, height]
    left_bottom = [width, 0]
    right_bottom = [0, 0]
    target_dict = {}
    mark_count = 0
    for i, cnt in enumerate(contours):
        # 輪郭線の長さを計算
        arclen = cv2.arcLength(cnt, True)
        # 長さの2%の精度を持つように輪郭線を近似
        approx = cv2.approxPolyDP(cnt, 0.02 * arclen, True)
        # 四角形4頂点 approx.shape[0]
        # 凸性の確認 isContourConvex
        # 輪郭の面積 contourArea
        area = abs(cv2.contourArea(approx))
        if approx.shape[0] == 4 and areamin < area and area < areamax and cv2.isContourConvex(approx) :
            rcnt = approx.reshape(-1,2)
            # w = abs(rcnt[2][0] - rcnt[0][0])
            # h = abs(rcnt[2][1] - rcnt[0][1])
            # if w < wmin or wmax < w or h < wmin or wmax < h:
            #     continue
            if rcnt[0][0] < width / 4:
                if rcnt[0][1] < height / 4: # 左上
                    if rcnt[0][1] < left_top[1]:
                        target_dict['LT'] = rcnt
                        left_top = rcnt[0]
                        mark_count += 1
                elif height * 3 / 4 < rcnt[0][1]:   # 左下
                    if left_bottom[1] < rcnt[0][1]:
                        target_dict['LB'] = rcnt
                        left_bottom = rcnt[0]
                        mark_count += 1
            elif width * 3 / 4 < rcnt[0][0]:
                if rcnt[0][1] < height / 4:   #  右上
                    if rcnt[0][1] < right_top[1]:
                        target_dict['RT'] = rcnt
                        right_top = rcnt[0]
                        mark_count += 1
                elif height * 3 / 4 < rcnt[0][1]:   # 右下
                    if right_bottom[1] < rcnt[0][1]:
                        target_dict['RB'] = rcnt
                        right_bottom = rcnt[0]
                        mark_count += 1
    logger.debug(f'{mark_count=}')
    targets = []
    rcnts = []
    rcnts.append(target_dict.get('LT'))
    rcnts.append(target_dict.get('RT'))
    rcnts.append(target_dict.get('RB'))
    rcnts.append(target_dict.get('LB'))
    for rcnt in rcnts:
        if rcnt is not None:
            vertexs = sort_point(rcnt)
            targets.extend([vertexs[0]])
            # 赤枠描画
            cv2.polylines(image, [rcnt], True, (0,0,255), thickness=2, lineType=cv2.LINE_8)
    # 四角形の傾きが逆だと変換がずれるので左上の座標のみ１X３=３点
    if len(targets) == 3 or len(targets) == 4: #12:
        apt = np.array(targets)
    else:
        apt = np.array([])
    return apt,image

# 画像上の四角形マーク座標を取得四角形以外も対象
def get_mark_nparray_polygon(bin_image, image):
    # 輪郭取得
    contours, _ = cv2.findContours(bin_image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    height, width = bin_image.shape[:2]
    areamin = (width / 50) * (width / 50)
    areamax = (width / 10) * (width / 10)
    wmin = width * 30 / 3000 # 2.8mm  48/1654-6mm
    wmax = width * 120 / 3000 # 7mm
    areamin = wmin * wmin
    areamax = wmax * wmax
    left_top = [[width, height],[width, height],[width, height],[width, height]]
    right_top = [[0, height],[0, height],[0, height],[0, height]]
    left_bottom = [[width, 0],[width, 0],[width, 0],[width, 0]]
    right_bottom = [[0, 0],[0, 0],[0, 0],[0, 0]]
    target_dict = {}
    mark_count = 0
    for i, cnt in enumerate(contours):
        # 輪郭線の長さを計算
        arclen = cv2.arcLength(cnt, True)
        # 長さの2%の精度を持つように輪郭線を近似
        approx = cv2.approxPolyDP(cnt, 0.02 * arclen, True)
        # 四角形4頂点 approx.shape[0]
        # 凸性の確認 isContourConvex
        # 輪郭の面積 contourArea
        area = abs(cv2.contourArea(approx))
        if areamin < area and area < areamax:
            rect = cv2.minAreaRect(approx)
            rect_points = cv2.boxPoints(rect)
            rcnt = rect_points.astype(int)
            w = abs(rcnt[2][0] - rcnt[0][0])
            h = abs(rcnt[2][1] - rcnt[0][1])
            if w < wmin or wmax < w or h < wmin or wmax < h:
                continue
            vertexs = sort_point(rcnt)
            if vertexs[0][0] < width / 4:
                if vertexs[0][1] < height / 4: # 左上
                    if vertexs[0][0] < left_top[0][0]:
                        target_dict['LT'] = rcnt
                        left_top = vertexs
                        mark_count += 1
                elif height * 3 / 4 < vertexs[0][1]:   # 左下
                    if vertexs[3][0] < left_bottom[3][0]:
                        target_dict['LB'] = rcnt
                        left_bottom = vertexs
                        mark_count += 1
            elif width * 3 / 4 < vertexs[0][0]:
                if vertexs[0][1] < height / 4:   #  右上
                    if right_top[1][0] < vertexs[1][0]:
                        target_dict['RT'] = rcnt
                        right_top = vertexs
                        mark_count += 1
                elif height * 3 / 4 < vertexs[0][1]:   # 右下
                    if right_bottom[2][0] < vertexs[2][0]:
                        target_dict['RB'] = rcnt
                        right_bottom = vertexs
                        mark_count += 1

    logger.debug(f'{mark_count=}')
    targets = []
    rcnts = []
    rcnts.append(target_dict.get('LT'))
    rcnts.append(target_dict.get('RT'))
    rcnts.append(target_dict.get('RB'))
    rcnts.append(target_dict.get('LB'))
    for rcnt in rcnts:
        if rcnt is not None:
            vertexs = sort_point(rcnt)
            targets.extend([vertexs[0]])
            # 赤枠描画
            cv2.polylines(image, [rcnt], True, (0,0,255), thickness=2, lineType=cv2.LINE_8)
    # 四角形の傾きが逆だと変換がずれるので左上の座標のみ１X３=３点
    if len(targets) == 3 or len(targets) == 4: #12:
        apt = np.array(targets)
    else:
        apt = np.array([])
    return apt,image
# 四角形の頂点の座標をソート
def sort_point(rcnt):
    approx = rcnt.tolist()
    left = sorted(approx, key=lambda x: x[0])[:2]   # 左側
    right = sorted(approx, key=lambda x: x[0])[2:]  # 右側
    left_top = sorted(left, key=lambda x: x[1])[0]  # 左上
    left_bottom = sorted(left, key=lambda x: x[1])[1]
    right_top = sorted(right, key=lambda x: x[1])[0]
    right_bottom = sorted(right, key=lambda x: x[1])[1]
    vertexs = [left_top, right_top, right_bottom, left_bottom]
    # 四角形の傾きが逆だと変換がずれるので４点の比較から左上の座標のみ１点の比較
    return vertexs
# 画像上の四角形マーク座標取得
def svt_get_nparray(image_path):
    # OpenCVではファイル名やパスに日本語が含まれていると、画像ファイルが開けない
    # NumPyで画像ファイルを開く
    # image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    buf = np.fromfile(image_path, np.uint8)
    image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if image is None:
        return np.array([])
    angle = sv_get_image_angle(image_path)
    if angle == 90:
        # 時計回りに90度回転
        image = cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        image = cv2.rotate(image,cv2.ROTATE_180)
    elif angle == 270:
        image = cv2.rotate(image,cv2.ROTATE_90_COUNTERCLOCKWISE)

    # hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # bin_img = cv2.inRange(hsv, (0, 0, 0), (179, 255, 30))
    # bin_img = cv2.inRange(hsv, (0, 0, 0), (179, 255, 50))
    # BGRをグレースケールに変換
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 大津の2値化でグレースケール画像を2値化
    _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # 2値化画像上の四角形マーク座標を取得
    apt,rimage = get_mark_nparray(bin_img, image)
    if settings.DEBUG:
        rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
        img_upload_dir = get_imgfolder_upload(rootfolder)
        match_img = os.path.join(img_upload_dir, 'bin-gray.jpg').replace(os.sep,'/')
        match_img = check_filename(match_img)
        # 2値化した画像を出力
        cv2.imwrite(match_img, bin_img)
        match_img = os.path.join(img_upload_dir, 'mark-gray.jpg').replace(os.sep,'/')
        match_img = check_filename(match_img)
        # 元の画像に赤枠描画
        cv2.imwrite(match_img, rimage)

    return apt

# 画像上の四角形マーク座標からアフィン行列の推定
# バッチ処理　PDFファイル 3点比較
def svt_get_matrix(ocrimages, formimage_dir, ocrform_id):
    matrixs = []
    for i, imagepath in enumerate(ocrimages, start=1):
        if not imagepath or not os.path.exists(imagepath):
            matrixs.append(np.array([]))
            continue
        try:
            file_name = get_ocrform_imagefile(formimage_dir, ocrform_id, i)

            if i == 1:  # フォームのおもての四角形マーク座標
                apt1 = np.array([[86,129],[1526,129],[86,2241]])
            else:       # フォームのうらの四角形マーク座標
                apt1 = np.array([[86,129],[1526,129],[86,2229]])
            # apt1 = svt_get_nparray(file_name)   # フォーム
            apt2 = svt_get_nparray(imagepath)
            if len(apt2) == 4:
                apt2 = np.delete(apt2, 2, axis=0)   # 3点にする
            logger.debug(f'svt_get_nparray page={i} apt2={len(apt2)}')
            # アフィン行列の推定(form --> entry)
            # mtx = cv2.estimateAffinePartial2D(apt1, apt2)[0]
            # 2 つの 2D 点セット間の最適なアフィン行列を求める
            affine_matrix = cv2.estimateAffine2D(apt1, apt2)[0]
            if 0 < affine_matrix.size:
                matrixs.append(affine_matrix)
            else:
                matrixs.append(np.array([]))
        except Exception:   # ValueError
            matrixs.append(np.array([]))
            logger.exception('svt_get_matrix exception')
    return matrixs

# def get_trapezoid(image_path):
#     buf = np.fromfile(image_path, np.uint8)
#     img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
#     angle = sv_get_image_angle(image_path)
#     if angle != 0:
#         if angle == 90:
#             # 時計回りに90度回転
#             img = cv2.rotate(img,cv2.ROTATE_90_CLOCKWISE)
#         elif angle == 180:
#             img = cv2.rotate(img,cv2.ROTATE_180)
#         elif angle == 270:
#             img = cv2.rotate(img,cv2.ROTATE_90_COUNTERCLOCKWISE)
#     # hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#     # bin_img = cv2.inRange(hsv, (0, 0, 0), (179, 255, 50))
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
#     contours, _ = cv2.findContours(bin_img, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
#     bin_img = cv2.drawContours(bin_img, contours, -1, (0, 0, 255), 30)

#     rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
#     img_upload_dir = get_imgfolder_upload(rootfolder)
#     output_path = os.path.join(img_upload_dir, 'trapezoid-1.jpg').replace(os.sep,'/')
#     output_path = check_filename(output_path)
#     cv2.imwrite(output_path, bin_img)
#     max_contour = None
#     max_area = 0
#     for contour in contours:
#         area = cv2.contourArea(contour)
#         if max_area < area:
#             max_area = area
#             max_contour = contour
#     arc_len = cv2.arcLength(max_contour, True)
#     approx_contour = cv2.approxPolyDP(max_contour, epsilon=0.1 * arc_len, closed=True)
#     bin_img = cv2.drawContours(bin_img, approx_contour, -1, (0, 0, 255), 30)
#     output_path = os.path.join(img_upload_dir, 'trapezoid-2.jpg').replace(os.sep,'/')
#     output_path = check_filename(output_path)
#     cv2.imwrite(output_path, bin_img)
#     approx = approx_contour.tolist()

#     left = sorted(approx, key=lambda x: x[0])[:2]
#     right = sorted(approx, key=lambda x: x[0])[2:]
#     left_down = sorted(left, key=lambda x: x[0][1])[0]
#     left_up = sorted(left, key=lambda x: x[0][1])[1]
#     right_down = sorted(right, key=lambda x: x[0][1])[0]
#     right_up = sorted(right, key=lambda x: x[0][1])[1]

#     perspective_base = np.float32([left_down, right_down, right_up, left_up])
#     perspective = np.float32([[0, 0], [1653, 0], [1653, 2338], [0, 2338]])

#     psp_matrix = cv2.getPerspectiveTransform(perspective_base, perspective)
#     plate_img = cv2.warpPerspective(img, psp_matrix, (1654, 2339))
#     output_path = os.path.join(img_upload_dir, 'trapezoid-3.jpg').replace(os.sep,'/')
#     output_path = check_filename(output_path)
#     cv2.imwrite(output_path, plate_img)
#     return plate_img

# def svt_get_trapezoid_matrix(ocrimages, formimage_dir, ocrform_id):
#     logger.debug('svt_get_matrix start ')
#     matrixs = []
#     for i, imagepath in enumerate(ocrimages, start=1):
#         if not imagepath or not os.path.exists(imagepath):
#             matrixs.append(np.array([]))
#             continue
#         try:
#             file_name = get_ocrform_imagefile(formimage_dir, ocrform_id, i)

#             # apt1 = svt_get_nparray(file_name)   # フォーム
#             # apt2 = svt_get_nparray(imagepath)
#             apt1 = np.float32([[0, 0], [1653, 0], [1653, 2338], [0, 2338]])
#             apt2 = get_trapezoid_npx(imagepath)

#             logger.debug('svt_get_nparray end ' + str(len(apt1)) + ':' + str(len(apt2)))
#             # アフィン行列の推定(form --> entry)
#             # mtx = cv2.estimateAffinePartial2D(apt1, apt2)[0]
#             affine_matrix = cv2.estimateAffine2D(apt1, apt2)[0] # 2 つの 2D 点セット間の最適なアフィン行列を求める
#             if 0 < affine_matrix.size:
#                 matrixs.append(affine_matrix)
#             else:
#                 matrixs.append(np.array([]))
#         except Exception:   # ValueError
#             matrixs.append(np.array([]))
#             logger.exception('svt_get_matrix exception : ')
#     return matrixs

# def get_trapezoid_npx(image_path):
#     buf = np.fromfile(image_path, np.uint8)
#     img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
#     angle = sv_get_image_angle(image_path)
#     if angle == 90:
#         # 時計回りに90度回転
#         img = cv2.rotate(img,cv2.ROTATE_90_CLOCKWISE)
#     elif angle == 180:
#         img = cv2.rotate(img,cv2.ROTATE_180)
#     elif angle == 270:
#         img = cv2.rotate(img,cv2.ROTATE_90_COUNTERCLOCKWISE)
#     # hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#     # bin_img = cv2.inRange(hsv, (0, 0, 0), (179, 255, 50))
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

#     contours, _ = cv2.findContours(bin_img, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
#     if settings.DEBUG:
#         rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
#         img_upload_dir = get_imgfolder_upload(rootfolder)
#         output_path = os.path.join(img_upload_dir, 'trapezoid-1.jpg').replace(os.sep,'/')
#         output_path = check_filename(output_path)
#         cv2.imwrite(output_path, bin_img)
#     max_contour = None
#     max_area = 0
#     for contour in contours:
#         area = cv2.contourArea(contour)
#         if max_area < area:
#             max_area = area
#             max_contour = contour
#     arc_len = cv2.arcLength(max_contour, True)
#     approx_contour = cv2.approxPolyDP(max_contour, epsilon=0.1 * arc_len, closed=True)
#     if settings.DEBUG:
#         bin_img = cv2.drawContours(bin_img, approx_contour, -1, (0, 0, 255), 30)
#         output_path = os.path.join(img_upload_dir, 'trapezoid-2.jpg').replace(os.sep,'/')
#         output_path = check_filename(output_path)
#         cv2.imwrite(output_path, bin_img)
#     approx = approx_contour.tolist()

#     left = sorted(approx, key=lambda x: x[0])[:2]
#     right = sorted(approx, key=lambda x: x[0])[2:]
#     left_down = sorted(left, key=lambda x: x[0][1])[0]
#     left_up = sorted(left, key=lambda x: x[0][1])[1]
#     right_down = sorted(right, key=lambda x: x[0][1])[0]
#     right_up = sorted(right, key=lambda x: x[0][1])[1]
#     return np.float32([left_down, right_down, right_up, left_up])

