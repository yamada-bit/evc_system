import logging
import os
import platform
import re
import shutil

import cv2
import numpy as np
from django.conf import settings

from commons.utils import ut_get_localtime, ut_get_localtoday
from Evc_App.sv_file import get_imgfolder_upload, make_dir, sv_get_processed_ym_path
from Evc_App.sv_get_image_shape import sv_imwrite
from Evc_App.sv_json import sv_json2textdatas
from Fms_Ocrform.svf_ocrform import (
    get_ocrform_image_dir,
    get_ocrform_imagefile,
    get_ocrform_rootfolder,
)

# from Fms_Ocrform.svt_pytorch import svt_load_model,svt_get_image_number

# 全角の文字列
Z_DIGITS = '０１２３４５６７８９'
Z_ALPHABET = 'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
Z_ALPHANUMERIC = Z_DIGITS + Z_ALPHABET  # 英数字
# 半角の文字列
H_DIGITS = '0123456789'
H_ALPHABET = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
H_ALPHANUMERIC = H_DIGITS + H_ALPHABET

ROOT_FOLDER = {
    'entry': 'Evc_Entry',
    'ocrdata': 'Evc_OcrData',
    'timesheet': 'Evc_Timesheet',
    'jafyame': 'Evc_Jafyame',   # JAふくおか八女
    'kumamoto': 'Evc_Kumamoto',   # 熊本市子育て支援申請
}

# --- align_image() の位置合わせパラメータ ---
# ホモグラフィ行列は理論上4組の対応点があれば計算できるが、
# 対応点が少ないと1組の誤マッチだけで変換結果が大きく崩れてしまう。
# 余裕を持たせて、これ未満の対応点しか得られなかった場合は
# 「位置合わせできない」ものとして明示的にエラーにする。
MIN_MATCH_COUNT = 10
# Lowe の比率テストの閾値。
# 各特徴点について「1番近い候補」と「2番目に近い候補」への距離を比較し、
# 1位が2位よりも(この倍率以上)明確に近い場合だけ信頼できるマッチとみなす。
# 値を小さくするほど厳しく絞り込まれ、誤マッチは減るが対応点数も減る。
# 0.7〜0.8 が一般的に使われる値。
LOWE_RATIO = 0.75
# RANSAC で外れ値（誤マッチ）を除外する際に許容する再投影誤差(px)
RANSAC_REPROJ_THRESHOLD = 5.0

logger = logging.getLogger(__name__)

def str2int(str):
    num = 0
    try:
        num = int(str, 10)
    except ValueError:
        num = 0
    return num

def isint(s):
    try:
        n = int(s, 10)
        if 0 < n:
            return True
    except ValueError:
        return False
    return False

# 数字、アルファベットを半角に変換する。
def zen2han(str):
    z2h = str.maketrans(Z_ALPHANUMERIC, H_ALPHANUMERIC)
    han = str.translate(z2h)
    han = han.replace(' ', '').replace('　', '')
    return han
# 大英字のみ抽出
def check_large(str):
    res = re.search('[A-Z]', str)
    if res:
        return res.group()
    return ''
# 数字以外削除
def check_digits(str):
    res = re.sub(r'\D', '', str)  # 元の文字列から数字以外を削除
    return res

# 文書保存ルートフォルダを取得
def svf_get_ocrdata_rootfolder(model_name):
    root_folder = getattr(settings, 'EVC_ROOT')#.lower()
    folder = ROOT_FOLDER.get(model_name)
    if folder:
        root_folder = os.path.join(root_folder, folder).replace(os.sep,'/')
    make_dir(root_folder)
    return root_folder

# 文書情報から画像ファイル名を取得
# 画像ファイル名：Ocr文書ID　+ _001(連番).jpg
def svf_get_ocrdata_imagepath(model_name, processed_ym, ocrdata_id, page_no):
    rootfolder = svf_get_ocrdata_rootfolder(model_name)   # ルートフォルダを取得
    dest_dir = sv_get_processed_ym_path(rootfolder, processed_ym)
    filepath = os.path.join(dest_dir, 'img', ocrdata_id + f'_{page_no:03d}.jpg').replace(os.sep,'/')
    return filepath

# 画像ファイルを保存するフォルダ作成
def svf_make_ocrdata_image_dir(rootfolder):
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
        logger.exception(f'make_ocrdata_image_dir exception {rootfolder=}')
        return False
    return True

# アップロードファイルは、年月フォルダに移動
def svf_move_uploadfile_ymfolder(filepath, rootfolder, basename):
    new_path = filepath
    if not rootfolder:
        return new_path
    if not filepath or not os.path.exists(filepath):
        return new_path
    try:
        today = ut_get_localtoday()
        processed_ym = today.strftime('%Y%m')
        dest_dir = sv_get_processed_ym_path(rootfolder, processed_ym)
        dest_file = os.path.join(dest_dir, basename).replace(os.sep,'/')

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
        logger.exception(f'move_uploadfile_ymfolder exception {filepath=}')

    return new_path

# 同じファイル名が存在する場合　'(連番)'　追加
def check_filename(file):
    if os.path.exists(file):
        filepath, ext = os.path.splitext(file)
        i = 1
        while i < 100000:
            new_path = f'{filepath}({i}){ext}'
            if not os.path.exists(new_path):
                return new_path
            i += 1
        logger.error(f'same file over 100000 {file}')
    return file

# JAふくおか八女 アップロードファイルを部課フォルダに移動
def svf_move_uploadfile_jafyame(filepath, dept, sect):
    new_path = filepath
    rootfolder = svf_get_ocrdata_rootfolder('jafyame')
    if not rootfolder:
        return new_path
    if not filepath or not os.path.exists(filepath):
        return new_path
    try:
        svf_make_jafyame_image_dir(rootfolder, dept, sect)
        basename = os.path.basename(filepath)
        dest_file = os.path.join(rootfolder, dept, sect, basename).replace(os.sep,'/')

        logger.debug(f'{dest_file=}')

        if dest_file:
            # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
            if dest_file != filepath:
                dest_file = check_filename(dest_file)
                new_path = shutil.move(filepath, dest_file)
        logger.info(f'move file {filepath} --> {new_path}')
    except Exception:
        logger.exception(f'svf_move_uploadfile_jafyame exception {filepath=}')

    return new_path

# JAふくおか八女 部課から画像ファイル名を取得  部課imgフォルダ
# 画像ファイル名：Ocr文書ID　+ _001(ページ番号).jpg
def svf_get_jafyame_imagepath(dept, sect, ocrdata_id, page_no):
    rootfolder = svf_get_ocrdata_rootfolder('jafyame')   # ルートフォルダを取得
    if rootfolder:
        # 部課フォルダパス
        dest_dir = os.path.join(rootfolder, dept, sect).replace(os.sep,'/')
    else:
        dest_dir = ''
    filepath = os.path.join(dest_dir, 'img', ocrdata_id + f'_{page_no:03d}.jpg').replace(os.sep,'/')
    return filepath

# JAふくおか八女 画像ファイルを保存するフォルダ作成 # 部課imgフォルダ
def svf_make_jafyame_image_dir(rootfolder, dept, sect):
    try:
        img_dir = os.path.join(rootfolder, dept, sect, 'img').replace(os.sep,'/')
        make_dir(img_dir)
    except Exception:
        logger.exception(f'make_dir exception {rootfolder=} {dept=} {sect=}')
        return False
    return True

# フォームの領域情報をdictに
# dicts:{0:areas0,1:areas1,...}
# areas = [{'x1':x1,'y1':y1,'x2':x2,'y2':y2,'text':'1'}, ...]
def svf_get_areas_dict(ocrform_area):
    dicts = {}
    if ocrform_area:
        try:
            areadatas = sv_json2textdatas(ocrform_area)
            for i, pagedata in enumerate(areadatas):
                areas = []
                for textdata in pagedata.textdata_list:
                    x1 = textdata.x1
                    y1 = textdata.y1
                    x2 = textdata.x2
                    y2 = textdata.y2
                    text = textdata.text
                    if x2 != 0 and y2 != 0:
                        # areas.append((x1, y1, x2, y2, int(text)))
                        areas.append({ 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'text':text })
                dicts[i] = areas
            # logger.debug('get_areas_dict  : ' + jsontext + ':' + ocrform_id)
        except Exception:
            logger.exception('get_areas_dict exception')
    return dicts
# フォームの項目領域ごとに抽出テキストを取得
# **kwargs: 複数のキーワード引数を辞書として受け取る
def svf_get_json_text_page(**param_dict):
    """
    model_name: 'entry'での処理
    GoogleOCRで空白の場合に領域画像を解析
    抽出領域の文字を認識する手書き数字認識処理
    PyTorchというPythonのオープンソース機械学習ライブラリを使用
    （PyTorchは、Facebookが開発を主導したPython向けの機械学習ライブラリ）
    MNIST学習済みモデルを使って手書き数字を認識する（6万枚の訓練データと1万枚のテストデータのデータセット）
    """
    model_name = param_dict.get('model_name')
    textdatas = param_dict.get('textdatas')
    page_no = param_dict.get('page_no') or 1
    ocrform_text_datas = param_dict.get('ocrform_text_datas')

    if model_name == 'entry':
        # 手書き数字認識処理の前処理
        rootfolder = svf_get_ocrdata_rootfolder('entry')   # ルートフォルダを取得
        ocrimages = param_dict.get('ocrimages')
        areas_dict = param_dict.get('areas_dict')
        pattern = param_dict.get('pattern')
        # 領域画像を解析するための画像を取得
        imagefile = get_cropped_image(rootfolder, ocrimages, page_no)
        if areas_dict:
            areas = areas_dict.get(page_no - 1)
        else:
            areas = []
        # model = svt_load_model(1)   # 空白の場合に領域画像を解析するための学習モデルを呼び出す

    pagedatas = []
    if textdatas:
        for pagedata in textdatas:
            if page_no == -1 or pagedata.page_no == page_no:
                pagedatas.append(pagedata)
    if settings.DEBUG:
        now = ut_get_localtime()
        print(now)

    object_list = []
    if ocrform_text_datas:
        try:
            if len(ocrform_text_datas) < page_no:
                pagedata = ocrform_text_datas[0]
                object_list = pagedata.get('page_list')
            else:
                for pagedata in ocrform_text_datas:
                    if pagedata.get('page_no') == str(page_no):
                        object_list = pagedata.get('page_list')
        except Exception:
            logger.exception('svf_get_json_text_page exception ')

    lists = []
    item_no = 1
    # 項目ごとの抽出テキストを取得
    for item in object_list:
        item_name = item.get('item_name')
        # json_name = ''
        area_no_str = item.get('area_no')
        item_json = item.get('item_json')
        table_id = item.get('table_id')
        fulltext = ''
        if area_no_str:
            area_no = int(area_no_str)
            if pagedatas:
                textlines = get_textlines(pagedatas, page_no, area_no)
                fulltext = ' \n'.join(textlines)

                if model_name == 'entry' and imagefile:
                    # 手書き数字認識処理
                    if item_json == 'code_h':
                        fulltext = check_large(fulltext)
                    elif item_json and 0 < len(item_json):
                        fulltext = zen2han(fulltext)
                        fulltext = check_digits(fulltext)
                        # GoogleOCRで空白の場合に領域画像を解析
                        if table_id:
                            if 'date_y' in item_json:
                                if fulltext and 2 < len(fulltext):
                                    # 年の文字列が３文字で先頭が20でなければ20を先頭につける
                                    if len(fulltext) == 3:
                                        if fulltext[:2] != '20':
                                            fulltext = '20' + fulltext[-2:]
                                    add_item = True
                                else:   # date_yに入力がなければその行は処理しない
                                    add_item = False
                        else:
                            if 'date_y' in item_json:
                                if fulltext and len(fulltext) == 3:
                                    if fulltext[:2] != '20':
                                        fulltext = '20' + fulltext[-2:]
                            add_item = True # テーブル以外の項目は処理する
                        # if not fulltext and add_item:
                        #     # 領域内数字認識
                        #     fulltext = svt_get_image_number(model, imagefile, area_no, areas, pattern)

        data = {
            'item_no': str(item_no),
            'item_name': item_name,
            'item_json': item_json,
            'item_text': fulltext,
            'area_no': area_no_str,
            'table_id': table_id,
        }
        lists.append(data)
        item_no += 1
    if settings.DEBUG:
        now = ut_get_localtime()
        print(now)
    # else:
    #     svt_remove_numfiles()
    return lists
# 領域画像を解析するための画像
def get_cropped_image(rootfolder, ocrimages, page_no):
    imagefile = ''
    if ocrimages and page_no != -1 and page_no - 1 < len(ocrimages):
        try:
            imagefile = ocrimages[page_no - 1]
            img_dir = get_imgfolder_upload(rootfolder)
            cropped_image_file =  os.path.join(img_dir, 'binary_image.jpg').replace(os.sep,'/')

            buf = np.fromfile(imagefile, np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
            # グレースケールに変換
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # ガウスブラーでノイズ除去 なし<---くるめ生産履歴票５.pdf などで罫線除去できなくなるため
            # gray = cv2.GaussianBlur(gray, (5, 5), 0)
            # ２値化  薄い色(水色)の罫線除去
            ret,dst = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # ret,dst = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            # cv2.imwrite(cropped_image_file, img)
            cv2.imwrite(cropped_image_file, dst)
            imagefile = cropped_image_file
            if settings.DEBUG:
                if platform.system() == 'Windows':
                    PYTORCH_NUM_FOLDER = '../data/num_file'
                else:
                    PYTORCH_NUM_FOLDER = '/data_root/data/num_file'
                out_file =  os.path.join(PYTORCH_NUM_FOLDER, 'binary_image' + str(page_no) + '.jpg').replace(os.sep,'/')
                cv2.imwrite(out_file, dst)
            # 直線消去
            # dst = svt_draw_rect(img, page_no)
            # cv2.imwrite(cropped_image_file, dst)
        except Exception:
            logger.exception(f'get_cropped_image exception {page_no=} {imagefile=}')
    return imagefile
# フォームの項目領域ごとにテキストを連結
def get_textlines(textdatas, page_no, area_no):
    if not textdatas:
        logger.error('textdatas False ')
        return []
    textlines = []
    threshold = 8
    for pagedata in textdatas:
        if page_no == -1 or pagedata.page_no == page_no:
            if area_no != -1 and pagedata.area_no != area_no:
                continue
            text = ''
            for textdata in pagedata.textdata_list:
                text += textdata.text
            textlines.append(text)
    return textlines

# デバッグのため領域を描画した画像を出力（射影変換後の全画像）
def svf_draw_area(ocrimages, ocrform_area):
    if not ocrform_area:
        return False
    try:
        rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
        img_upload_dir = get_imgfolder_upload(rootfolder)

        areadatas = sv_json2textdatas(ocrform_area) # [TextDatas,TextDatas...]
        for i, pagedata in enumerate(areadatas):
            if i < len(ocrimages):
                imagepath = ocrimages[i]
                file_name = os.path.basename(imagepath)
                # fname, ext = os.path.splitext(file_name)
                out_name =  os.path.join(img_upload_dir, 'areas_' + file_name).replace(os.sep,'/')
                buf = np.fromfile(imagepath, np.uint8)
                cv2_image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
                rect_image = cv2_image.copy()
                for textdata in pagedata.textdata_list:
                    x1 = textdata.x1
                    y1 = textdata.y1
                    x2 = textdata.x2
                    y2 = textdata.y2
                    if x2 != 0 and y2 != 0:
                        cv2.rectangle(rect_image, (x1, y1), (x2, y2), (0, 0, 255), 5)
                # cv2.imwrite(out_name, rect_image)
                # 日本語を含むファイルパスを取り扱う際の問題への対処
                sv_imwrite(out_name, rect_image)
    except Exception:
        logger.exception('draw_area exception')

# 日本語ファイル名に対応した画像読み込み関数
def imread_unicode(path, flags=cv2.IMREAD_COLOR):
    with open(path, 'rb') as f:
        bytes_data = np.asarray(bytearray(f.read()), dtype=np.uint8)
        return cv2.imdecode(bytes_data, flags)

# 入力画像をフォーム画像に合わせる
# 戻り値: (adjusts, failed_pages)
#   adjusts      : 位置合わせに成功したページの画像パスのリスト
#   failed_pages : 位置合わせに失敗したページ番号(1始まり)のリスト
# 以前はalign_image()が失敗したページを結果から黙って除外していたため、
# ページ数が減ったままextract処理に渡り、ページ番号と内容がずれた不完全な
# データが登録されてしまう不具合があった。
# そのため失敗したページ番号を明示的に返し、呼び出し元(svf_create_ocrdata)側で
# 「このファイルはエラー扱いにして登録しない」という判断ができるようにしている。
def svf_adjust_image(ocrimages, ocrform_id):
    adjusts = []
    failed_pages = []
    rootfolder = get_ocrform_rootfolder()   # ルートフォルダを取得
    formimg_dir = get_ocrform_image_dir(rootfolder)
    img_dir = get_imgfolder_upload(rootfolder)
    for i, imagepath in enumerate(ocrimages, start=1):
        if not imagepath or not os.path.exists(imagepath):
            continue
        try:
            file_name = get_ocrform_imagefile(formimg_dir, ocrform_id, i)
            # 入力画像を変換しフォーム画像に合わせる
            aligned = align_image(file_name, imagepath, draw_matches=False)

            basename = os.path.basename(imagepath)
            file_name =  os.path.join(img_dir, 'adjust_' + basename).replace(os.sep,'/')
            # cv2.imwrite(file_name, img)
            # 射影変換で変換した入力画像をファイルに出力
            sv_imwrite(file_name, aligned)
            # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
             # ファイルに出力した変換画像にアップロード画像を入れ替える
            shutil.move(file_name, imagepath)
            adjusts.append(imagepath)
            # adjusts.append(file_name)
        except Exception:   # ValueError（対応点不足・ホモグラフィ推定失敗など）
            # ここで例外を握りつぶして次のページへ進むのではなく、
            # 「何ページ目が失敗したか」を記録して呼び出し元に伝える。
            logger.exception(f'svf_adjust_image exception {i=} {imagepath=}')
            failed_pages.append(i)
    return adjusts, failed_pages

# 入力画像を変換しフォーム画像に合わせる（ORB特徴点マッチング＋射影変換）
#
# 処理の流れ:
#   1. ORBで template(登録済みフォーム画像) と input(アップロード画像) それぞれから特徴点を検出
#   2. knnMatch(k=2) + Loweの比率テストで「信頼できる対応点」だけに絞り込む
#   3. 対応点からRANSACでホモグラフィ行列(射影変換行列)を推定
#      （RANSACは対応点の中に混じった誤マッチ=外れ値を自動的に無視して行列を求める）
#   4. その行列でinput画像をtemplateと同じ座標系・同じサイズに変形する
#
# 対応点が少なすぎる場合や、対応点はあってもホモグラフィが数学的に求まらない場合は
# ValueErrorを送出する。呼び出し元(svf_adjust_image)はこれを検知してそのページを
# failed_pagesに積む。
def align_image(template_path, input_path, draw_matches=False):
    # 画像読み込み（特徴点検出は明暗差だけで十分なためグレースケールで行う）
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    # OpenCVではファイル名やパスに日本語が含まれていると、画像ファイルが開けない
    # NumPyで画像ファイルを開く
    input_img = imread_unicode(input_path, cv2.IMREAD_GRAYSCALE)
    # input_img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)

    # ORB特徴量抽出（画像の「角」や模様の変化点のような特徴的な点を検出する）
    orb = cv2.ORB_create(5000)
    kp1, des1 = orb.detectAndCompute(template, None)
    kp2, des2 = orb.detectAndCompute(input_img, None)

    if des1 is None or des2 is None:
        raise ValueError("特徴量が検出されませんでした")

    # # 型確認（あくまで確認用）
    # print(f"des1: {des1.shape}, dtype: {des1.dtype}")
    # print(f"des2: {des2.shape}, dtype: {des2.dtype}")

    # 特徴点マッチング（k近傍探索）
    # 以前はcrossCheck=Trueの最近傍マッチ(bf.match)で「距離が近い上位50件」を
    # 機械的に採用していたが、これだと対応点の「質」を見ていないため、
    # 罫線や似た形の文字(年・月・日など)が多い帳票では誤マッチが混入しやすかった。
    # knnMatch(k=2)で各特徴点ごとに「1番目に近い候補」「2番目に近い候補」の
    # 2つを取得し、この後のLoweの比率テストで質の悪いマッチを除外する。
    # ※ knnMatchを使う場合、BFMatcherのcrossCheckはTrueにできない(仕様上併用不可)ため外す。
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn_matches = bf.knnMatch(des1, des2, k=2)

    # Loweの比率テスト
    # 1位の候補との距離が、2位の候補との距離よりも十分に近い(=紛れもなく一番似ている)
    # 場合だけを「信頼できる対応点」として採用する。
    # 1位と2位の距離がほぼ同じ(=どちらの候補か区別がつかない)マッチは
    # 誤マッチである可能性が高いためここで除外する。
    good_matches = []
    for match_pair in knn_matches:
        # 特徴点によっては近傍候補が1つしか見つからず2件揃わないことがあるため件数を確認する
        if len(match_pair) != 2:
            continue
        m, n = match_pair
        if m.distance < LOWE_RATIO * n.distance:
            good_matches.append(m)

    # ホモグラフィ行列の推定には理論上4組の対応点があれば足りるが、
    # 少数の対応点しかないと1組の誤マッチだけで変換結果が大きく崩れて不安定になる。
    # そのためMIN_MATCH_COUNT件未満の場合は「位置合わせできない」ものとして
    # ここで明示的にエラーにする（黙って処理を続けて誤った変換をしない）。
    if len(good_matches) < MIN_MATCH_COUNT:
        raise ValueError(
            f'位置合わせに十分な対応点が見つかりませんでした '
            f'({len(good_matches)}/{MIN_MATCH_COUNT}件)。'
            '写真の向き・ピント・書類全体が写っているかを確認してください。'
        )

    # 対応点座標を取得（input側の座標をtemplate側の座標に変換する行列を求める）
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    # ホモグラフィ行列推定（RANSACで対応点に混じった外れ値=誤マッチを自動的に除外する）
    M, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, RANSAC_REPROJ_THRESHOLD)

    # 対応点の数がMIN_MATCH_COUNT以上あっても、点の配置(ほぼ一直線上に並ぶ等)
    # によっては解が数学的に求まらずMがNoneで返ってくることがある。
    # ここでチェックせずにcv2.warpPerspectiveへ渡すと、原因のわかりにくい
    # OpenCVレベルのエラーになってしまうため、必ず確認してから先に進む。
    if M is None:
        raise ValueError('ホモグラフィ行列の推定に失敗しました。位置合わせできません。')

    # 射影変換で位置合わせ（出力サイズはtemplate画像に合わせる）
    h, w = template.shape

    # 読み込みと warpPerspective 処理
    # 特徴点検出はグレースケールで行ったが、出力・以降のOCR処理では
    # カラー画像のまま扱うためここで改めてカラーで読み込み直す
    input_img = imread_unicode(input_path)
    if input_img is None:
        raise ValueError("画像の読み込みに失敗しました。ファイルパスを確認してください。")
    aligned_img = cv2.warpPerspective(input_img, M, (w, h))

    # if draw_matches:
    #     match_img = cv2.drawMatches(template, kp1, input_img, kp2, good_matches, None, flags=2)
    #     cv2.imshow("Matches", match_img)
    #     cv2.waitKey(0)
    #     cv2.destroyAllWindows()

    # 位置合わせ結果の確認用画像はDEBUG時のみ書き出す
    # （以前はcv2.imwrite("aligned_result.jpg", ...)でカレントディレクトリに
    #   無条件で書き出しており、日本語パス非対応かつ本番でも不要なファイルが
    #   溜まり続けていたため、入力画像と同じフォルダにDEBUG時のみ出力するよう変更）
    if settings.DEBUG:
        debug_dir = os.path.dirname(input_path)
        debug_name = os.path.join(debug_dir, 'aligned_' + os.path.basename(input_path)).replace(os.sep, '/')
        sv_imwrite(debug_name, aligned_img)

    return aligned_img
