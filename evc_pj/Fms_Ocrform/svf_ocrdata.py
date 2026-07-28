import datetime
import functools
import json
import logging
import os
import re
import shutil

# from PIL import Image
# from decimal import Decimal
from django.conf import settings

# from django.utils import timezone
# from django.utils.timezone import make_aware
# from django.http import HttpResponse
from django.db.models import Q
from sequences import get_next_value

from commons.utils import ut_get_localdate, ut_get_localtoday, ut_get_timezone_now
from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_file import get_imgfolder_upload, get_jsonfolder, sv_delete_file
from Evc_App.sv_get_image_shape import sv_get_pdfpages
from Evc_App.sv_json import sv_datas2json, sv_save_detect_json, sv_save_json
from Fms_Ocrform.models import (
    TtAccessLog,
    TtEntry,
    TtJafyame,
    TtOcrData,
    TtOcrform,
    TtTimesheet,
)
from Fms_Ocrform.svf_common import (
    imread_unicode,
    svf_adjust_image,
    svf_detect_circled_choice,
    svf_draw_area,
    svf_get_areas_dict,
    svf_get_jafyame_imagepath,
    svf_get_json_text_page,
    svf_get_ocrdata_imagepath,
    svf_get_ocrdata_rootfolder,
    svf_move_uploadfile_jafyame,
    svf_move_uploadfile_ymfolder,
)
from Fms_Ocrform.svf_extract_image import pdf_to_image
from Fms_Ocrform.svf_extract_text import svf_extract_text
from Fms_Ocrform.svf_ocrform import (
    get_ocrform_image_dir,
    get_ocrform_imagefile,
    get_ocrform_rootfolder,
)
from Fms_Ocrform.svt_adjust_image import svt_adjust_image_trapezoid

MODEL_CLASSES = {
    'entry': TtEntry,
    'ocrdata': TtOcrData,
    'timesheet': TtTimesheet,
    'jafyame': TtJafyame,	# JAふくおか八女
    'kumamoto': TtOcrData,	# 福祉手当認定診断書（tt_ocrdataを流用、ocrform_nameで区分）
}
PAGE_MARK_IMAGE = '/data_root/evc_root/jafyame.jpg'   # OCRでテキストを抽出するページを判定する画像
KUMAMOTO_FORM_NAME_PREFIX = '福祉手当認定診断書'   # このプレフィックスで始まる名前で登録したフォームのみ対象
KUMAMOTO_KEYWORDS = [
    '氏名', '生年月日', '住所', '傷病名',
    '診断を受けた日',    # ⑤④のため初めて医師の診断を受けた日
    '傷病発生',          # ⑥傷病発生年月日
    '永続すると判',      # ⑦障害が永続すると判定された日
    '将来再認定の要',    # ⑧将来再認定の要
    '医師氏名',
    # 以下、⑨⑫⑭⑮⑯・診断日/病院名/所在地（area_no 10〜24、エリア抽出専用）
    '身長',              # ⑨身体計測
    '体重',              # ⑨身体計測
    '換気機能検査日',    # ⑫換気機能（平成〇年〇月〇日）
    '肺活量実測値',      # ⑫ア
    '予測肺活量',        # ⑫イ
    '努力性肺活量',      # ⑫ウ
    '１秒量',            # ⑫エ
    '努力性肺活量１秒率',  # ⑫オ
    '予測肺活量１秒率',    # ⑫カ
    '現在までの治療内容等',  # ⑭
    'その他の障害又は病状',  # ⑮（臨床所見）
    '備考',              # ⑯
    '上記のとおり診断します',  # 診断日
    '病院又は診療所の名称',
    '所在地',
    '撮影',              # ⑩胸部Ｘ線所見の撮影年月日
    'ふりがな',          # ①氏名の上のふりがな欄
]   # 仮実装。対象書式が決まり次第見直す
KEYWORD_SEPARATORS = '：:　 -－\t'   # キーワードの後ろに付く区切り文字
# search_text(キーワード:値)とフォームフィールド名(半角英数)の対応
KUMAMOTO_FIELD_MAP = {
    '氏名': 'name',
    '生年月日': 'birthday',
    '住所': 'address',
    '傷病名': 'disease',
    '診断を受けた日': 'first_exam_date',
    '傷病発生': 'onset_date',
    '永続すると判': 'permanent_date',
    '将来再認定の要': 'reexam',
    '医師氏名': 'doctor',
    '身長': 'height_cm',
    '体重': 'weight_kg',
    '換気機能検査日': 'vent_test_date',
    '肺活量実測値': 'vc_actual',
    '予測肺活量': 'vc_predicted',
    '努力性肺活量': 'fvc',
    '１秒量': 'fev1',
    '努力性肺活量１秒率': 'fev1_percent',
    '予測肺活量１秒率': 'predicted_fev1_percent',
    '現在までの治療内容等': 'treatment_history',
    'その他の障害又は病状': 'other_symptoms',
    '備考': 'remarks',
    '上記のとおり診断します': 'diagnosis_date',
    '病院又は診療所の名称': 'hospital_name',
    '所在地': 'hospital_address',
    '撮影': 'xray_date',
    'ふりがな': 'furigana',
}
# その他項目タブに表示する項目のフィールド名一覧（forms.py/テンプレートから参照）
KUMAMOTO_OTHER_FIELD_NAMES = [
    'furigana',
    'height_cm', 'weight_kg', 'vent_test_date', 'vc_actual', 'vc_predicted',
    'fvc', 'fev1', 'fev1_percent', 'predicted_fev1_percent',
    'treatment_history', 'other_symptoms', 'remarks',
    'diagnosis_date', 'hospital_name', 'hospital_address',
    'xray_date',
]

# 丸で囲む形式の選択肢の自動判定を実行するかどうかのフラグ。
# Falseにすると位置合わせ済み画像とテンプレート画像の差分比較処理を一切行わない
# （精度に確信が持てない場合や、処理時間を減らしたい場合はFalseにする）。
KUMAMOTO_DETECT_CIRCLED_CHOICES = False
# KUMAMOTO_DETECT_CIRCLED_CHOICES = True

# 丸で囲む形式の選択肢の矩形領域(pt単位、72dpi基準・register_real_form.py等と同じ実座標)。
# 1つのキーにつき選択肢のリストを持たせ、svf_detect_circled_choice()で
# テンプレートとの差分が最も大きい選択肢を判定する。
# 実座標はPyMuPDFのsearch_for()で実PDFから直接取得したもの。
KUMAMOTO_CIRCLE_FIELDS = {
    '推定確認': [   # ⑦ 推定・確認
        {'label': '推定', 'box': (289.9, 180.5, 310.5, 190.8)},
        {'label': '確認', 'box': (289.9, 191.9, 310.5, 202.2)},
    ],
    '将来再認定の要_選択': [   # ⑧ 将来再認定の要 有・無
        {'label': '有', 'box': (425.2, 186.3, 435.8, 196.6)},
        {'label': '無', 'box': (521.5, 186.3, 532.1, 196.6)},
    ],
    '活動能力の程度': [   # ⑪ ア〜オのいずれかに丸
        {'label': 'ア', 'box': (103.7, 396.9, 113.2, 407.2)},
        {'label': 'イ', 'box': (103.7, 408.3, 112.4, 418.6)},
        {'label': 'ウ', 'box': (103.7, 431.0, 113.7, 441.2)},
        {'label': 'エ', 'box': (103.7, 476.3, 113.2, 486.6)},
        {'label': 'オ', 'box': (103.7, 499.0, 113.6, 509.3)},
    ],
    '安静を要する程度': [   # ⑬ 1度〜8度のいずれかに丸
        {'label': '1度', 'box': (344.5, 220.8, 365.2, 231.1)},
        {'label': '2度', 'box': (344.5, 232.2, 365.2, 242.5)},
        {'label': '3度', 'box': (344.5, 243.5, 365.2, 253.8)},
        {'label': '4度', 'box': (344.5, 254.9, 365.2, 265.2)},
        {'label': '5度', 'box': (344.5, 266.2, 365.2, 276.5)},
        {'label': '6度', 'box': (344.5, 288.9, 365.2, 299.2)},
        {'label': '7度', 'box': (344.5, 311.5, 365.2, 321.8)},
        {'label': '8度', 'box': (344.5, 334.2, 365.2, 344.5)},
    ],
    # ⑩ 胸部Ｘ線所見（ア〜カの各項目ごとに なし・軽・中・高 のいずれかに丸）
    '胸部Ｘ線所見_胸膜癒着': [
        {'label': 'なし', 'box': (203.7, 249.0, 221.8, 259.3)},
        {'label': '軽', 'box': (240.6, 249.0, 251.2, 259.3)},
        {'label': '中', 'box': (267.6, 249.0, 278.2, 259.3)},
        {'label': '高', 'box': (294.6, 249.0, 305.2, 259.3)},
    ],
    '胸部Ｘ線所見_気腫化': [
        {'label': 'なし', 'box': (203.7, 260.3, 221.8, 270.6)},
        {'label': '軽', 'box': (240.6, 260.3, 251.2, 270.6)},
        {'label': '中', 'box': (267.6, 260.3, 278.2, 270.6)},
        {'label': '高', 'box': (294.6, 260.3, 305.2, 270.6)},
    ],
    '胸部Ｘ線所見_線維化': [
        {'label': 'なし', 'box': (203.7, 271.7, 221.8, 282.0)},
        {'label': '軽', 'box': (240.6, 271.7, 251.2, 282.0)},
        {'label': '中', 'box': (267.6, 271.7, 278.2, 282.0)},
        {'label': '高', 'box': (294.6, 271.7, 305.2, 282.0)},
    ],
    '胸部Ｘ線所見_不透明肺': [
        {'label': 'なし', 'box': (203.7, 283.0, 221.8, 293.3)},
        {'label': '軽', 'box': (240.6, 283.0, 251.2, 293.3)},
        {'label': '中', 'box': (267.6, 283.0, 278.2, 293.3)},
        {'label': '高', 'box': (294.6, 283.0, 305.2, 293.3)},
    ],
    '胸部Ｘ線所見_胸郭変形': [
        {'label': 'なし', 'box': (203.7, 294.4, 221.8, 304.7)},
        {'label': '軽', 'box': (240.6, 294.4, 251.2, 304.7)},
        {'label': '中', 'box': (267.6, 294.4, 278.2, 304.7)},
        {'label': '高', 'box': (294.6, 294.4, 305.2, 304.7)},
    ],
    '胸部Ｘ線所見_心縦隔の変形': [
        {'label': 'なし', 'box': (203.7, 305.7, 221.8, 316.0)},
        {'label': '軽', 'box': (240.6, 305.7, 251.2, 316.0)},
        {'label': '中', 'box': (267.6, 305.7, 278.2, 316.0)},
        {'label': '高', 'box': (294.6, 305.7, 305.2, 316.0)},
    ],
}
# KUMAMOTO_CIRCLE_FIELDS の各キーを画面・JSON側の項目名(半角英数)に対応させる。
# search_text(キーワード:値)とフォームフィールド名の対応であるKUMAMOTO_FIELD_MAPに
# 合流させることで、画面表示・登録・JSONダウンロードの各処理を既存の汎用ロジックに乗せる。
_KUMAMOTO_CIRCLE_FIELD_MAP = {
    '推定確認': 'suitei_kakunin',
    '将来再認定の要_選択': 'reexam_choice',
    '活動能力の程度': 'activity_level',
    '安静を要する程度': 'rest_level',
    '胸部Ｘ線所見_胸膜癒着': 'xray_pleural_adhesion',
    '胸部Ｘ線所見_気腫化': 'xray_emphysema',
    '胸部Ｘ線所見_線維化': 'xray_fibrosis',
    '胸部Ｘ線所見_不透明肺': 'xray_opacity',
    '胸部Ｘ線所見_胸郭変形': 'xray_thorax_deform',
    '胸部Ｘ線所見_心縦隔の変形': 'xray_mediastinum_deform',
}
# フォームからこれらのフィールドを除外する際に使うフィールド名一覧(forms.pyから参照)。
KUMAMOTO_CIRCLE_FIELD_NAMES = list(_KUMAMOTO_CIRCLE_FIELD_MAP.values())

# KUMAMOTO_DETECT_CIRCLED_CHOICES が True の時だけ、丸で囲む形式の項目を
# 画面(KUMAMOTO_FIELD_MAP経由)・JSONダウンロード(KUMAMOTO_EXPORT_KEYS)に反映する。
# Falseの場合は検出処理自体を実行しないだけでなく、画面・JSON側にも一切出さない。
if KUMAMOTO_DETECT_CIRCLED_CHOICES:
    KUMAMOTO_FIELD_MAP.update(_KUMAMOTO_CIRCLE_FIELD_MAP)
    # JSONダウンロード用のキー一覧。KUMAMOTO_KEYWORDSはsvf_extract_keywords()での
    # 文字列検索にも使われるため、丸で囲む形式の項目(文字列検索の対象ではない)は
    # 混在させず、JSONダウンロード専用にKUMAMOTO_CIRCLE_FIELDSのキーを追加する。
    KUMAMOTO_EXPORT_KEYS = KUMAMOTO_KEYWORDS + list(KUMAMOTO_CIRCLE_FIELDS.keys())
else:
    KUMAMOTO_EXPORT_KEYS = list(KUMAMOTO_KEYWORDS)
# 行頭のマッチ判定で無視する飾り文字（丸数字・番号・記号・空白など）。
# 例:「② 生年月日」「⑥　傷病発生年月日」の先頭の "②　" "⑥　" の部分を取り除くために使う。
# 丸数字は①(U+2460)〜⑳(U+2473)の範囲。
_LEADING_MARKER_RE = re.compile(r'^[\s　①-⑳0-9０-９.．、,・]+')

logger = logging.getLogger(__name__)

# KUMAMOTO_KEYWORDS のようなキーワードリストの中に、
# あるキーワードが別のキーワードの部分文字列になっているものがないか事前にチェックする。
# (例えば将来「名」のような短いキーワードを追加してしまうと、
#  「氏名」「傷病名」「医師氏名」すべてに巻き込まれてマッチしてしまう。
#  そうした「値ではなくキーワード同士が衝突している」事故を、
#  実データで気づく前にこの関数で検知できるようにしておく)
# 戻り値: [(短い方のキーワード, それを含む長い方のキーワード), ...]。問題なければ空リスト。
def svf_check_keyword_collisions(keywords):
    collisions = []
    for short in keywords:
        for long_ in keywords:
            if short != long_ and short in long_:
                collisions.append((short, long_))
    return collisions

# モジュール読み込み時に一度だけチェックし、問題があればログに警告を残す。
# ここで検知しても処理は止めない（誤字修正漏れなどですぐにアプリが起動できなくなるのを避けるため）。
# _kumamoto_keyword_collisions = svf_check_keyword_collisions(KUMAMOTO_KEYWORDS)
# if _kumamoto_keyword_collisions:
#     logger.warning(f'KUMAMOTO_KEYWORDS に部分文字列の衝突があります: {_kumamoto_keyword_collisions}')

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
        elif model_name == 'kumamoto':   # 熊本市子育て支援申請
            q_objects = Q(ocrdata_id=ocrdata_id)
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
            ocrimages, adjust_failed_pages = svf_adjust_image(ocrimages, ocrform_id)
            if adjust_failed_pages:
                # 位置合わせに失敗したページがあると、以降のarea抽出でページ番号と
                # 内容がずれた不完全なデータが登録されてしまう。
                # そのため黙って残りのページだけで処理を続けず、このファイルは
                # 他の読み込みエラー(パスワード付きファイル等)と同様にエラー扱いにする。
                logger.error(f'位置合わせ失敗ページあり {filename=} {adjust_failed_pages=}')
                error_list.append(filename)
                sv_delete_file(new_path)    # アップロードファイル削除
                continue
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
        search_dict = get_search_text(json_str, page_no)
        if model_name == 'kumamoto':   # 福祉手当認定診断書：エリア抽出を優先し、空の項目だけキーワード抽出で補う
            search_dict = svf_merge_kumamoto_search_text(search_dict, fulltext)
            # 丸で囲む形式の選択肢を、テンプレートとの差分から判定して追加する
            search_dict.update(svf_detect_kumamoto_circles(ocrform_id, ocrimages))
        search = json.dumps(search_dict, ensure_ascii=False) # 辞書型のオブジェクトをJSON形式の文字列に変換
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
        pdf_name = basename_without_ext + f'_Page{page_no}'
        page = page_no if 0 < page_no else 1
        area = 1
        ocrdata_id = ocrdata_id + f'_{page:03d}{area:02d}'
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
    elif model_name == 'kumamoto':   # 熊本市子育て支援申請
        save_id = save_ocrdata(ocrdata_id, param_dict)
    else:
        save_id = False
    return save_id

# 文字列(TextDatasのリスト)からキー情報を抽出（ページごと)
def get_search_text(json_str, page_no):
    search = {
    }
    if not json_str:
        logger.error('json_str False')
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
        logger.exception('get_search_text exception')

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
        id = d + f'_{num:05d}'
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

    search_text = json.dumps(data_dict, ensure_ascii=False) # 辞書型のオブジェクトをJSON形式の文字列に変換

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

# 行頭の丸数字・番号・記号・空白等の飾り文字を取り除く
# 例:「② 生年月日」→「生年月日」
def _strip_leading_marker(line):
    return _LEADING_MARKER_RE.sub('', line)

# キーワードの各文字の間に半角/全角スペースやタブが入っていても一致する
# 正規表現パターンを組み立てる。
# 実際の帳票では「氏　名」「住　所」のように、2文字の項目名を1文字ずつ
# 均等割り付けする表記がよく使われる。単純な文字列一致(in/find)だと
# 「氏名」というキーワードは「氏　名」に一致しないため、キーワードの
# 文字と文字の間に空白が挟まっていても一致するようにしている。
_KEYWORD_GAP = r'[ \t　]*'

@functools.lru_cache(maxsize=None)
def _build_keyword_pattern(keyword):
    escaped_chars = [re.escape(ch) for ch in keyword]
    return re.compile(_KEYWORD_GAP.join(escaped_chars))

# line内でstart〜endの範囲にマッチしたkeywordが、実はkeywords一覧にある
# 「別の、より長いキーワード」の一部として出現しているだけなのかどうかを判定する。
# 例：「医師氏名」というテキスト中の"氏名"は、KUMAMOTO_KEYWORDSに含まれる
#     "医師氏名"というキーワード自体の一部として出現しているだけなので、
#     "氏名"というキーワードの一致としては扱わない。
# (svf_check_keyword_collisions() が事前に検知するのはキーワード一覧同士の
#  衝突の可能性であり、実際にOCRテキスト中でどちらの意味で出現しているかは
#  ここで実行時に判定する)
def _is_part_of_longer_keyword(line, start, end, keyword, keywords):
    for other in keywords:
        if other == keyword or keyword not in other:
            continue
        # otherキーワード自身も文字間の空白を許容するパターンで、
        # line内の一致範囲がkeywordの一致範囲を完全に包含していないか確認する
        for m in _build_keyword_pattern(other).finditer(line):
            if m.start() <= start and end <= m.end():
                return True
    return False

# lines の中から keyword にマッチする行を探し、キーワード以降の値を返す。
# strict=True  : 行頭（飾り文字を除いた部分）がキーワードそのもので始まる行だけを対象にする
# strict=False : 行のどこかにキーワードが含まれていればよい（ただし他のより長い
#                キーワードの一部として出現しているだけの箇所は除く）
#
# 一致する行が見つかったら、その時点で確定させて他の行は探しに行かない。
# （同じ行に値が無い場合だけ、ラベル行と値行が分かれているレイアウトを想定して
#  直後の1行だけを値として見る。それでも空ならこのキーワードは「値なし」として
#  諦める）。ここで探索を続けて他の行まで見に行くと、離れた場所にある無関係な
#  行との部分一致を誤って拾ってしまう恐れがあるため、あえて打ち切っている。
def _find_keyword_value(lines, keyword, keywords, strict):
    pattern = _build_keyword_pattern(keyword)
    for i, line in enumerate(lines):
        if strict:
            stripped = _strip_leading_marker(line)
            m = pattern.match(stripped)   # 行頭(飾り文字除去後)からの一致のみ許可
            if not m:
                continue
            # 飾り文字を取り除く前の元の行における、一致終了位置に補正する
            offset = len(line) - len(stripped)
            match_end = offset + m.end()
        else:
            # 他のより長いキーワードの一部として出現しているだけの箇所はスキップし、
            # 独立したキーワードとして出現している箇所だけを探す
            match_end = None
            search_from = 0
            while True:
                m = pattern.search(line, search_from)
                if not m:
                    break
                if _is_part_of_longer_keyword(line, m.start(), m.end(), keyword, keywords):
                    search_from = m.start() + 1
                    continue
                match_end = m.end()
                break
            if match_end is None:
                continue

        after = line[match_end:].strip(KEYWORD_SEPARATORS)
        if after:
            return after
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip(KEYWORD_SEPARATORS)
            if next_line:
                return next_line
        return ''
    return ''

# OCR全文からキーワードを含む行を探し、キーワード以降の文字列を値として抽出
#
# 単純に「行のどこかにキーワードを含んでいればよい」という一致条件だけだと、
# 別項目のラベルの中に今回のキーワードがたまたま部分文字列として
# 紛れ込んでいるケースを誤って拾ってしまうことがある。
# 例：キーワード「生年月日」に対して
#   ② 生年月日                      ← 本来ヒットしてほしい行
#   ⑥ 傷病発生年月日　　　　年　月　日 ← "生年月日"を含むが別の項目(傷病の発生日)
# のような書式の場合、⑥の行を誤って「生年月日」の値として拾ってしまうことがあった。
# 同様に「医師氏名　佐藤一郎」のような行は、"氏名"というキーワードにとって
# 紛らわしい部分一致になる。
#
# これを避けるため、次の2段階で一致する行を探す。
#   1段階目（strict） : 行頭（先頭の丸数字・番号・空白等を除いた部分）がキーワードで
#                       始まっている行だけを探す。ラベル単独の行（例:「② 生年月日」）は
#                       ここでヒットし、⑥のように説明文の途中にキーワードが
#                       埋もれている行はヒットしない。
#   2段階目（fallback）: 1段階目で見つからなかった場合のみ、行のどこかにキーワードが
#                       含まれていればよい、という緩い一致にフォールバックする。
#                       ただし_is_part_of_longer_keyword()により、他の登録済み
#                       キーワード（例:「医師氏名」）の一部として出現しているだけの
#                       箇所は除外する。ラベルが説明文の末尾に付いている行
#                       （例:「④ 障害の原因となった傷病名」）は行頭一致には
#                       ならないため、こちらで拾う。
#
# fulltext: 改行区切りの全文テキスト、keywords: 抽出したいキーワードのリスト
# 戻り値: {キーワード: 抽出した値} （見つからない場合は空文字）
def svf_extract_keywords(fulltext, keywords):
    if not fulltext:
        return dict.fromkeys(keywords, '')
    lines = fulltext.split('\n')
    result = {}
    for keyword in keywords:
        value = _find_keyword_value(lines, keyword, keywords, strict=True)
        if not value:
            value = _find_keyword_value(lines, keyword, keywords, strict=False)
        result[keyword] = value
    return result

# 福祉手当認定診断書のsearch_text用に、エリア抽出結果とキーワード抽出結果をマージする。
# area_search_dict: get_search_text()の戻り値（item_json＝半角英数キー、矩形領域からの抽出値）
# fulltext: OCR全文（キーワード抽出のフォールバック用）
#
# 矩形領域は座標で位置を直接指定しているため、キーワードが別の行に紛れ込んで
# 誤った値を拾うkeyword抽出よりも基本的に信頼度が高い。そのため
# エリア抽出値を優先し、値が空（未検出・未記入）の項目だけキーワード抽出で補う。
# 戻り値のキーはKUMAMOTO_KEYWORDS(日本語)に統一する
# （画面・JSONダウンロードはこのキーだけを参照するため、item_json側の英語キーは
#  ここで捨てて日本語キーのみのdictにする）。
def svf_merge_kumamoto_search_text(area_search_dict, fulltext):
    keyword_dict = svf_extract_keywords(fulltext, KUMAMOTO_KEYWORDS)
    merged = {}
    for keyword in KUMAMOTO_KEYWORDS:
        field_name = KUMAMOTO_FIELD_MAP.get(keyword)
        area_value = area_search_dict.get(field_name, '') if field_name else ''
        merged[keyword] = area_value or keyword_dict.get(keyword, '')
    return merged

# 丸で囲む形式の選択肢(KUMAMOTO_CIRCLE_FIELDS)を、位置合わせ済み画像と
# テンプレート画像の差分から判定する。KUMAMOTO_DETECT_CIRCLED_CHOICESがFalseの場合、
# または画像が読み込めない場合は何もせず全項目を空文字で返す(処理は止めない)。
#
# ocrform_id        : 登録済みテンプレートのID(テンプレート画像の特定に使う)
# aligned_imagepaths: svf_adjust_image()で位置合わせ済みの画像ファイルパスのリスト
#                     (先頭ページのみを判定対象にする)
# 戻り値: {KUMAMOTO_CIRCLE_FIELDSのキー: 判定結果のlabel}（判定できない項目は空文字）
def svf_detect_kumamoto_circles(ocrform_id, aligned_imagepaths):
    result = dict.fromkeys(KUMAMOTO_CIRCLE_FIELDS, '')
    if not KUMAMOTO_DETECT_CIRCLED_CHOICES or not aligned_imagepaths:
        return result
    try:
        rootfolder = get_ocrform_rootfolder()
        formimg_dir = get_ocrform_image_dir(rootfolder)
        template_path = get_ocrform_imagefile(formimg_dir, ocrform_id, 1)
        template_img = imread_unicode(template_path)
        aligned_img = imread_unicode(aligned_imagepaths[0])
        if template_img is None or aligned_img is None:
            logger.error(f'svf_detect_kumamoto_circles 画像読み込み失敗 {ocrform_id=}')
            return result
        for key, choices in KUMAMOTO_CIRCLE_FIELDS.items():
            label = svf_detect_circled_choice(template_img, aligned_img, choices)
            result[key] = label or ''
    except Exception:
        logger.exception(f'svf_detect_kumamoto_circles exception {ocrform_id=}')
    return result

# 熊本市子育て支援申請 対象のocrform_idリストを取得（フォーム名がプレフィックスで始まるもの）
def get_kumamoto_ocrform_ids():
    return list(
        TtOcrform.objects
        .filter(ocrform_name__startswith=KUMAMOTO_FORM_NAME_PREFIX)
        .values_list('ocrform_id', flat=True)
    )

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
        elif model_name == 'kumamoto':   # 熊本市子育て支援申請
            q_objects = Q(ocrdata_id=ocrdata_id)
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
        elif model_name == 'kumamoto':   # 熊本市子育て支援申請
            q_objects = Q(ocrdata_id=ocrdata_id)
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
# 福祉手当認定診断書 検索条件で絞り込み
def svf_filter_kumamoto(request, queryset):
    try:
        pdf_name = request.GET.get('pdf_name')
        if pdf_name:
            queryset = queryset.filter(pdf_name__contains=pdf_name)
        # 氏名はTtOcrDataの専用カラムを持たずsearch_text(JSON文字列)に格納されているため、
        # 部分一致でsearch_text自体をcontains検索する(氏名以外の項目に偶然一致する可能性はあるが、
        # 構造化されたJSONField化はしていないため簡易的な対応とする)
        name = request.GET.get('name')
        if name:
            queryset = queryset.filter(search_text__contains=name)
        create_date = request.GET.get('create_date')
        if create_date:
            queryset = queryset.filter(create_date__date=create_date)
    except Exception:
        logger.exception('svf_filter_kumamoto exception')
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
