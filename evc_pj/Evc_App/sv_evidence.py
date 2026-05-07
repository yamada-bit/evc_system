import os
import datetime
import shutil
import logging
import json
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_aware
from sequences import get_next_value
from django.db.models import F

from users.models import TtEvidence,MtPartner,HtEvidence,TtDetect,MtFolder
from commons.utils import ut_get_localdate

from Evc_App.sv_file import (sv_delete_file,
    get_rootfolder,get_imgfolder_upload,
    get_jsonfolder,get_evidence_image_dir,sv_get_evidence_imagepath,
    sv_get_textlines,sv_get_processed_ym_path,sv_get_evidence_filename,sv_delete_detect
)
from Evc_App.sv_search import sv_search_text
from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_extract_text import sv_extract_text
# from Evc_App.sv_extract_azure import sv_extract_azure
from Evc_App.sv_json import (sv_save_json,sv_save_detect_json
    # ,sv_save_fulltext,sv_load_jsonfile,
    # sv_replace_fulltext,sv_delete_fulltext
)
from Evc_App.sv_get_image_shape import sv_get_cropped_image,sv_get_image_angle
OCR_DPI = 200     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う
# OCR_DPI = 300     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う

logger = logging.getLogger(__name__)

# エビデンス情報登録
def sv_create_evidence(uploadfiles, user_id, owner_id, areas_flg, evidence_kubun, specif_pages):
    ok_list = []
    error_list = []
    rootfolder = get_rootfolder(owner_id)
    img_upload_dir = get_imgfolder_upload(rootfolder)
    if not img_upload_dir:
        logger.error(f'upload imgfolder error {rootfolder=}')
        return ok_list, error_list
    json_dir = get_jsonfolder(rootfolder)
    specif_page_list = get_pages(specif_pages)  # 指定ページのリストを'1,2,2-4' の形式から取得)
    areas_dict = {}
    images = []
    files = []
    if areas_flg:    # 画像分割での処理
        # 画像データがすでに作成されているので設定
        # アップロードファイルは１ファイルのみ
        # ページごとの情報設定
        firstLoop = True
        for i, uploadfile in enumerate(uploadfiles):
            imgpath = uploadfile.get('imgpath')
            images.append(imgpath)
            # ページごとの分割領域取得(画像分割領域指定)
            jsonpos = uploadfile.get('areas')
            areas_dict[i] = get_areas(jsonpos)  # 座標データ(json形式)から領域リストを取得
            if firstLoop:
                files.append(uploadfile)    # １ファイルのみ
                firstLoop = False
    else:
        files = uploadfiles
    for uploadfile in files:
        filename = uploadfile.get('name')
        path = uploadfile.get('path')
        # 処理年月のフォルダに保存
        new_path = move_file_processed_ym(path, rootfolder, filename).replace('\\', '/')
        if images:
            ocrimages = images  # 画像分割で作成済み
        else:
            # ページごとに画像データを作成
            ocrimages = sv_create_ocr_image(new_path, img_upload_dir, -1)
        if not ocrimages:   # パスワード設定などにより読み込めない
            logger.error(f'ocrimages error {filename=}')
            error_list.append(filename)
            sv_delete_file(new_path)    # アップロードファイル削除
            continue

        # if areas and 1 < len(ocrimages):   # 画像分割の場合、先頭ページのみ処理
        #     toppage = ocrimages.pop(0)    # 先頭ページのみ残す
        #     delete_files(ocrimages)
        #     ocrimages = [toppage]
        
        # OCR機能を使って、テキスト抽出しTextDataデータに変換
        textdatas, detecttext_list, google_cnt = sv_extract_text(ocrimages, areas_dict, specif_page_list)
        logger.debug(f'extract text {filename=}')

        evi_id = get_evidence_id()  # エビデンスID取得
        save_id = False
        page_count = len(ocrimages)
        if 1 < page_count and specif_page_list:
            page_exist = False
            for page_no in range(1, page_count + 1):
                if page_no in specif_page_list:
                    page_exist = True
                    break
            if not page_exist: # 指定ページがなければファイル全体を１エビデンスで登録
                evidence_kubun = 'file'
        # エビデンス情報テーブルデータ作成・登録
        if page_count == 1 or evidence_kubun == 'file':
            imgfile = ocrimages[0]
            page_areas = areas_dict.get(0)
            save_id = sv_create_evidence_page(new_path, textdatas, -1, user_id, owner_id,
                                               page_areas, evi_id, imgfile, evidence_kubun, google_cnt)
            logger.debug(f'create evidence page {save_id} : {imgfile}')
        else:
            for page_no in range(1, page_count + 1):
                if not specif_page_list or page_no in specif_page_list:
                    imgfile = ocrimages[page_no - 1]
                    page_areas = areas_dict.get(page_no - 1)
                    id = sv_create_evidence_page(new_path, textdatas, page_no, user_id, owner_id,
                                                  page_areas, evi_id, imgfile, 'page', 1)
                    if not save_id:
                        save_id = id
                    logger.debug(f'create evidence page {id} : {imgfile}:{page_no}')
                else:
                    sv_delete_file(ocrimages[page_no - 1])
        if save_id:
            ok_list.append(filename)
            if settings.DEBUG:
                # デバッグ時に使用するデータをjsonファイルで保存
                if textdatas:
                    sv_save_json(new_path, textdatas, json_dir)
                if detecttext_list:
                    basename_without_ext, ext_name = os.path.splitext(filename)
                    sv_save_detect_json(basename_without_ext, detecttext_list, json_dir)
        else:
            error_list.append(filename)
            logger.error(f'create evidence page error {filename=}')
            sv_delete_file(new_path)    # アップロードファイル削除

        # OCR機能で使用した画像ファイルを削除
        basename_without_ext, ext_name = os.path.splitext(os.path.basename(path))
        # if ocrimages and ext_name.lower() == '.pdf':
        #     delete_files(ocrimages)
        if evidence_kubun == 'file' and ext_name.lower() == '.pdf':
            if 1 < len(ocrimages):
                ocrimages.pop(0)    # 先頭ページのみ残す
                delete_files(ocrimages)
    return ok_list, error_list

# json形式の座標データから領域リストを取得
def get_areas(jsonpos):
    areas = []
    if jsonpos:
        try:
            postext = json.loads(jsonpos)
            # dict { 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2 }
            for pos in postext:
                x1 = int(pos.get('x1','0'))
                y1 = int(pos.get('y1','0'))
                x2 = int(pos.get('x2','0'))
                y2 = int(pos.get('y2','0'))
                if x2 != 0 and y2 != 0:
                    areas.append((x1, y1, x2, y2))
        except Exception:
            logger.exception(f'postext exception {jsonpos=}')
    return areas

# 指定ページのリストを'1,2,2-4' の形式から取得
def get_pages(specif_pages):
    page_list = []
    if specif_pages:
        try:
            pages = specif_pages.split(',')
            for page in pages:
                p = page.split('-')
                if len(p) == 1:
                    page_list.append(int(p[0]))
                elif len(p) == 2:
                    s = int(p[0])
                    e = int(p[1])
                    for i in range(min(s, e), max(s, e) + 1):
                        page_list.append(i)
        except Exception:
            logger.exception(f'get_pages exception {specif_pages=}')

    return page_list
# エビデンス情報テーブルデータ作成・登録
def sv_create_evidence_page(filepath, textdatas, page_no, user_id, owner_id, areas, evi_id, imgfile,
                             evidence_kubun, google_cnt):
    save_id = False
    pagedatas = []
    for pagedata in textdatas:
        if page_no == -1 or pagedata.page_no == page_no:
            pagedatas.append(pagedata)
    basename = os.path.basename(filepath)
    basename_without_ext, ext_name = os.path.splitext(basename)
    # if imgfile and ext_name.lower() == '.pdf':
    #     pdf_img = True
    #     angle = sv_get_image_angle(imgfile)
    # else:
    #     pdf_img = False
    #     angle = sv_get_image_angle(filepath)
    angle = sv_get_image_angle(imgfile)
    area_count = len(areas) if areas else 1

    for i in range(1, area_count + 1):
        area_no = i if 1 < area_count else -1
        # evidence_id ：yyyymmdd_連番(00001～)_ページ番号(001)+領域番号(01)
        if evidence_kubun == 'file':
            evidence_id = evi_id + '_00000' # ページごとに分割しない
        else:
            page = page_no if 0 < page_no else 1
            area = i
            evidence_id = evi_id + '_{:03d}{:02d}'.format(page, area)

        # テキストデータおよび検索キーを取り出す
        search = sv_search_text(pagedatas, user_id, owner_id, area_no, evidence_id)
         # 検索キーおよびファイルのリンク情報を、DBに保存する
        if pagedatas:
            textlines = sv_get_textlines(pagedatas, page_no, area_no)
            fulltext = '\n'.join(textlines)
        else:
            fulltext = ''
        # google利用枚数
        if page_no == -1 and evidence_kubun == 'file':
            google_pages = google_cnt
        elif i == 1:    # 最初の領域だけカウントする
            google_pages = 1
        else:           # 2番目以降の領域はカウントしない
            google_pages = 0
        #  複数ページでページごとのエビデンスの場合、'_Page1'の形式でページ番号を追加
        if page_no == -1:
            pdf_name = basename_without_ext
        else:
            pdf_name = basename_without_ext + '_Page{}'.format(page_no)
        # pdf_name = basename_without_ext + '_Page{}'.format(page_no) + '({}/{})'\
        #     .format(area_no, area_count)
        #  複数領域の場合、'(1/4)'の形式で分割エリア番号を追加
        if 1 < area_count:
            pdf_name = pdf_name + ' ({}/{})'.format(area_no, area_count)

        # エビデンス情報テーブル登録処理
        id = save_evidence_data(user_id,owner_id,filepath,pdf_name,search,fulltext,google_pages,evidence_id)
        if not save_id:
            save_id = id
        if id:
            if 1 < area_count:
                # 分割領域画像ファイル作成
                create_area_image(owner_id, imgfile, areas[area_no - 1], id, angle)
                # if pdf_img:
                #     create_area_image(owner_id, imgfile, areas[area_no - 1], id, angle)
                # else:
                #     create_area_image(owner_id, filepath, areas[area_no - 1], id, angle)
            else:
                # 画像移動(エビデンス画像ファイル作成)
                move_image(owner_id, imgfile, id, False)    # MOVE
                # if pdf_img:
                #     move_image(owner_id, imgfile, id, False)    # MOVE
                # else:
                #     move_image(owner_id, imgfile, id, True) # COPY
    if 1 < area_count:  # 分割で画像を保存のためページの画像は削除
        sv_delete_file(imgfile)

    return save_id
def delete_files(files):
    if files:
        for file in files:
            sv_delete_file(file)
# エビデンス情報から画像ファイル名を取得
def get_evidence_imagefile(evi_id):
    imagepath = ''
    try:
        evi_obj = TtEvidence.objects.get(evidence_id=evi_id)
    except TtEvidence.DoesNotExist:
        evi_obj = None
    if evi_obj:
        imagepath = sv_get_evidence_imagepath(evi_obj)
    return imagepath
# 画像移動(エビデンス画像作成)
def move_image(owner_id, filepath, evidence_id, copy):
    if not filepath or not os.path.exists(filepath):
        return
    new_path = filepath

    if filepath and evidence_id:
        try:
            # rootfolder = get_rootfolder(owner_id)
            # img_dir = get_evidence_image_dir(rootfolder)
            # # basename_without_ext, ext_name = os.path.splitext(os.path.basename(filepath))
            # file_name =  os.path.join(img_dir, evidence_id + '.jpg').replace(os.sep,'/')
            file_name = get_evidence_imagefile(evidence_id)
            # logger.debug('dest_dir  : ' +  (dest_dir or 'False'))
        # new_path = shutil.move(file, dest_dir)
        # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
        # basename = os.path.basename(file)
            if copy:
                new_path = shutil.copy(filepath, file_name)
            else:
                new_path = shutil.move(filepath, file_name)
            logger.debug(f'move imagefile {filepath} --> {new_path}')
        except Exception:   # ValueError
            logger.exception(f'move_image exception {evidence_id=} {filepath=}')
# 分割領域画像ファイル作成
def create_area_image(owner_id, filepath, area, evidence_id, angle):
    if not filepath or not os.path.exists(filepath):
        return False
    area_image = False
    if filepath and evidence_id:
        try:
            # rootfolder = get_rootfolder(owner_id)
            # img_dir = get_evidence_image_dir(rootfolder)
            # cropped_image_file =  os.path.join(img_dir, evidence_id + '.jpg').replace(os.sep,'/')
            cropped_image_file = get_evidence_imagefile(evidence_id)

            area_image = sv_get_cropped_image(filepath, area, cropped_image_file, angle)
            # new_path = shutil.move(filepath, file_name)
            logger.debug(f'create_are_image {filepath} --> {cropped_image_file}')
        except Exception:   # ValueError
            logger.exception(f'create_are_image exception {evidence_id=} {filepath=}')
    return area_image
# ファイルは、年月フォルダに移動
def move_file_processed_ym(filepath, rootfolder, basename):
    new_path = filepath
    if not filepath or not os.path.exists(filepath):
        return new_path
    try:
        today = datetime.datetime.now()
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
        logger.exception(f'move file exception {filepath=}')

    return new_path

# 同じファイル名が存在する場合　'(連番)'　追加
def check_filename(file):
    if os.path.exists(file):
        # 別日付の場合
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
        logger.error(f'same file over 100000 {file=}')
    return file
# エビデンスID取得
# evidence_id：yyyymmdd_連番(00001～)
def get_evidence_id():
    d = datetime.date.today().strftime('%Y%m%d')
    # lastobj = TtEvidence.objects.all().order_by('-evidence_id').first()
    # # first():存在しない場合Noneを返す
    # if lastobj:
    #     pre_id = lastobj.evidence_id
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
        num = get_next_value(d)
        id = d + '_{:05d}'.format(num)
    except Exception:   # ValueError
        id = d + '_00001'

    return id
# エビデンス情報テーブル登録処理
def save_evidence_data(user_id, owner_id, file_path, pdf_name, search, jsontext, pages, evidence_id):
    # basename_without_ext, ext_name = os.path.splitext(os.path.basename(pdffile))
    # owner_id = get_owner_id(user_id)
    try:
        partnerobj = MtPartner.objects.get(partner_id=search.partner_id)
        partner_ryaku_name = partnerobj.partner_ryaku_name or ''
    except MtPartner.DoesNotExist:
        partner_ryaku_name = ''
    d = datetime.date.today().strftime('%Y%m%d')
    create_date = datetime.datetime.now()
    create_user_id = user_id
    id = evidence_id    # get_evidence_id()
    processed_ym = create_date.strftime('%Y%m')
    # try:
    #     with open(pdffile, 'rb') as f:
    #         b_pdf = f.read()
    # except Exception:
    #     b_pdf = None
    #     logger.exception('pdffile read exception : ' + basename)
    # b_pdf = None
    b_pdf = file_path.encode('utf-8')

    # 請求書に明細がある時
    # tran_detail = {
    #     '明細No': 1,
    #     'attribute': {
    #         'attribute': {
    #             '品名': 'PC',
    #             '仕様': 'CPUXXXX',	
    #             'メモリ': '5M',	
    #             'Disk容量': '100G',
    #             '金額': 120000,	
    #         }
    #     }
    # }
    google_amount = pages
    tran_detail = ''
    name = d + '_' +  partner_ryaku_name + '_' + (str(search.total_amount) if search.total_amount else '')
    obj = TtEvidence(
        evidence_id=id,
        evidence_name=name,
        owner_id=owner_id,
        pdf_name=pdf_name,
        processed_ym=processed_ym,
        category_name=search.category_name,
        processed_date=search.processed_date,   # DateField
        partner_id=search.partner_id,
        publisher_id=search.publisher_id,
        total_amount=search.total_amount,       # DecimalField
        pdf_handbook=jsontext,
        tran_detail=tran_detail,                # JSONField
        evidence_data=b_pdf,                    # BinaryField
        google_amount = google_amount,
        account_id = '',
        account_desc = '',
        slip_number = '',
        # payment_date = '',
        create_date=create_date,                # DateTimeField
        create_user=create_user_id,
        update_user=user_id,
        update_date=datetime.datetime.now()     # DateTimeField
    )
    try:
        obj.save()
        logger.info(f'エビデンス情報テーブル登録 {evidence_id} : {pdf_name}')
    except Exception:
        logger.exception(f'TtEvidence save exception {evidence_id} : {pdf_name}')
        return False
    return id

# エビデンス情報テーブル更新・エビデンス履歴情報テーブルに登録
def sv_update_evidence(evidence_id, search, account_id, account_desc, duplicate_ok, slip_number, payment_date, user_id):
    # owner_id = get_owner_id(user_id)
    try:
        evi_obj = TtEvidence.objects.get(evidence_id=evidence_id)
        sv_copy_htevidence(evi_obj, user_id, 'U')
    except TtEvidence.DoesNotExist:
        logger.exception(f'TtEvidence DoesNotExist {evidence_id=}')
        return False
        # raise ValueError('エビデンス情報テーブル更新エラー!')
    if search.total_amount or search.total_amount == 0:
        try:
            total_amount = Decimal(search.total_amount)
        except Exception:
            total_amount = None 
    else:
        total_amount = None 
    # if evi_obj.category_name != category:
    #     new_path = sv_change_category(owner_id, evi_obj.pdf_name, evi_obj.category_name, category)
    #     # evi_obj.pdf_name = os.path.splitext(os.path.basename(new_path))[0]
    #     if new_path:
    #         evi_obj.pdf_name = os.path.basename(new_path)
    # カテゴリの検索履歴を更新
    # if evi_obj.category_name != search.category_name:
    #     sv_update_use_count(evi_obj.owner_id, search.category_name)
    evi_obj.category_name = search.category_name
    evi_obj.processed_date = search.processed_date
    evi_obj.partner_id = search.partner_id
    evi_obj.publisher_id = search.publisher_id
    evi_obj.total_amount = total_amount
    # evi_obj.pdf_handbook = fulltext
    evi_obj.account_id = account_id
    evi_obj.account_desc = account_desc
    evi_obj.slip_number= slip_number
    evi_obj.payment_date= payment_date
    tran_detail = {
        '重複':'許可'
    }
    evi_obj.tran_detail = tran_detail if duplicate_ok else ''
    evi_obj.create_date = ut_get_localdate(evi_obj.create_date)
    evi_obj.update_user = user_id
    evi_obj.update_date = datetime.datetime.now()

    try:
        evi_obj.save()
        logger.info(f'エビデンス情報テーブル更新 {evidence_id} : {evi_obj.pdf_name}')
    except Exception:
        logger.exception(f'TtEvidence update exception {evidence_id} : {evi_obj.pdf_name}')
        return False
    return evidence_id
# カテゴリの検索履歴をカウント
def sv_update_use_count(owner_id, category):
    if not category:
        return
    try:
        MtFolder.objects.filter(owner_id=owner_id, category_name=category).update(
            use_count=F('use_count') + 1
        )
    except Exception:
        logger.exception(f'update exception {owner_id} : {category}')

# エビデンス テキストデータ更新
def sv_update_shiori(evidence_id, fulltext, user_id, owner_id):
    try:
        evi_obj = TtEvidence.objects.get(evidence_id=evidence_id)
        sv_copy_htevidence(evi_obj, user_id, 'O')
    except TtEvidence.DoesNotExist:
        logger.exception(f'TtEvidence DoesNotExist {evidence_id=}')
        return False
        # raise ValueError('エビデンス テキストデータ更新エラー!')
    evi_obj.pdf_handbook = fulltext
    evi_obj.create_date = ut_get_localdate(evi_obj.create_date)
    evi_obj.update_user = user_id
    evi_obj.update_date = datetime.datetime.now()

    try:
        evi_obj.save()
        logger.info(f'update pdf_handbook {evidence_id} : {evi_obj.pdf_name}')
    except Exception:
        logger.exception(f'update pdf_handbook exception {evidence_id} : {evi_obj.pdf_name}')
        return False
    # jsonファイル fullTextLists.json 更新
    # try:
    #     # owner_id = get_owner_id(user_id)
    #     rootfolder = get_rootfolder(owner_id)
    #     if rootfolder:
    #         json_dir = get_jsonfolder(rootfolder)
    #         if json_dir:
    #             # old_path = sv_get_category_path(owner_id, evi_obj.category_name)
    #             # filepath = sv_get_processed_ym_path(owner_id, evi_obj.processed_ym, evi_obj.pdf_name)  
    #             filepath = sv_get_evidence_filename(evi_obj)

    #             sv_replace_fulltext(json_dir, fulltext, filepath)
    # except Exception:
    #     logger.exception('fullTextLists update exception : ' + evidence_id)
    return evidence_id
# エビデンス 取引先更新
def sv_update_partner(evidence_id, partner_id):
    try:
        evi_obj = TtEvidence.objects.get(evidence_id=evidence_id)
    except TtEvidence.DoesNotExist:
        logger.exception(f'TtEvidence DoesNotExist {evidence_id=}')
        return False
    evi_obj.partner_id = partner_id
    evi_obj.create_date = ut_get_localdate(evi_obj.create_date)
    evi_obj.update_date = ut_get_localdate(evi_obj.update_date)

    try:
        evi_obj.save()
        logger.info(f'update partner_id {evidence_id} : {partner_id=}')
        update_detect(evi_obj)
    except Exception:
        logger.exception(f'update pdf_handbook exception {evidence_id} : {partner_id=}')
        return False
    return evidence_id
# エビデンス 発行元更新
def sv_update_publisher(evidence_id, publisher_id):
    try:
        evi_obj = TtEvidence.objects.get(evidence_id=evidence_id)
    except TtEvidence.DoesNotExist:
        logger.exception(f'TtEvidence DoesNotExist {evidence_id=}')
        return False
    evi_obj.publisher_id = publisher_id
    evi_obj.create_date = ut_get_localdate(evi_obj.create_date)
    evi_obj.update_date = ut_get_localdate(evi_obj.update_date)

    try:
        evi_obj.save()
        logger.info(f'update publisher_id {evidence_id} : {publisher_id=}')
        update_detect(evi_obj)
    except Exception:
        logger.exception(f'update publisher_id exception {evidence_id} : {publisher_id=}')
        return False
    return evidence_id
# 検出情報データ更新
def update_detect(evi_obj):
    if evi_obj.evidence_id:
        try:
            detect = TtDetect.objects.get(evidence_id=evi_obj.evidence_id)
            if (not detect.partner_name or evi_obj.partner_id) and (not detect.publisher_name or evi_obj.publisher_id):
                sv_delete_detect(evi_obj.evidence_id)   # 検出情報削除
        except TtDetect.DoesNotExist:
            pass

# エビデンス情報削除・エビデンス履歴情報テーブルに登録
def sv_delete_evidence(evidence_id, user_id, owner_id):
    try:
        evi_obj = TtEvidence.objects.get(evidence_id=evidence_id)
    except TtEvidence.DoesNotExist:
        logger.exception(f'TtEvidence DoesNotExist {evidence_id=}')
        return False
        # raise ValueError('エビデンス情報削除　取得エラー ' + evidence_id)
    try:
        sv_copy_htevidence(evi_obj, user_id, 'D')
        delete_evidence_file(evi_obj)
    except Exception:
        logger.exception(f'delete exception {evidence_id=}')
    sv_delete_detect(evidence_id)   # 検出情報削除
    filename = evi_obj.pdf_name
    evi_obj.delete()    # エビデンス情報テーブルから削除
    logger.info(f'エビデンス情報データ削除 {evidence_id} : {filename}')

    return filename
# エビデンスファイル削除
# 削除データも閲覧できるように画像ファイルは削除しない
def delete_evidence_file(evi_obj):
    evidence_id = evi_obj.evidence_id
    # dest_dir = sv_get_category_path(owner_id, evi_obj.category_name)
    # dest_file = sv_get_processed_ym_path(owner_id, evi_obj.processed_ym, evi_obj.pdf_name)  
    dest_file = sv_get_evidence_filename(evi_obj)
    # evidence_data:PDFファイルのパス
    other_obj = TtEvidence.objects.filter(evidence_data=evi_obj.evidence_data)\
                                    .exclude(evidence_id=evidence_id).first()

    # 削除データも閲覧できるように画像ファイルは削除しない
    # # rootfolder = get_rootfolder(owner_id)
    # # img_dir = get_evidence_image_dir(rootfolder)
    # # file_name =  os.path.join(img_dir, evidence_id + '.jpg').replace(os.sep,'/')
    # file_name = get_evidence_imagefile(evidence_id)
    # sv_delete_file(file_name)   # エビデンス画像ファイルを削除

    if dest_file and not other_obj:
        sv_delete_file(dest_file)   # ファイルを削除
        logger.info(f'エビデンスファイル削除 {evidence_id} : {dest_file}')
        # # jsonファイル
        # rootfolder = get_rootfolder(owner_id)
        # if rootfolder:
        #     json_dir = get_jsonfolder(rootfolder)
        #     if json_dir:
        #         sv_delete_fulltext(json_dir, dest_file)    # json全文データから削除
        # basename_without_ext = os.path.splitext(evi_obj.pdf_name)[0]
        # jsonfile = os.path.join(json_dir, basename_without_ext + '.json').replace(os.sep,'/')
        # os.remove(jsonfile)   # jsonファイルの削除
    return True
# エビデンス履歴情報テーブル登録
def sv_copy_htevidence(evi_obj, user_id, rireki_kbn):
    lastobj = HtEvidence.objects.all().order_by('-r_evidence_id').first()
    # r_evidence_id：yyyymmdd_連番(00001～)
    d = datetime.date.today().strftime('%Y%m%d')
    if lastobj:
        pre_id = lastobj.r_evidence_id
        try:
            last = int(pre_id[:8])
            if last < int(d):
                id = d + '_00001'
            else:
                num = int(pre_id[-5:])
                id = d + '_{:05d}'.format(num + 1)
        except Exception:
           id = d + '_00001'
    else:
        id = d + '_00001'
 
    try:
        obj = HtEvidence.objects.create(
            r_evidence_id = id,
            rireki_kbn = rireki_kbn,
            evidence_id = evi_obj.evidence_id,
            evidence_name = evi_obj.evidence_name,
            owner_id = evi_obj.owner_id,
            pdf_name = evi_obj.pdf_name,
            processed_ym = evi_obj.processed_ym,
            category_name = evi_obj.category_name,
            processed_date = evi_obj.processed_date,
            partner_id = evi_obj.partner_id,
            publisher_id = evi_obj.publisher_id,
            total_amount = evi_obj.total_amount,
            pdf_handbook = evi_obj.pdf_handbook,
            tran_detail = evi_obj.tran_detail,
            evidence_data = evi_obj.evidence_data,
            # evidence_data = None if rireki_kbn == 'D' else evi_obj.evidence_data ,
            google_amount = evi_obj.google_amount,
            account_id = evi_obj.account_id,
            account_desc = evi_obj.account_desc,
            slip_number = evi_obj.slip_number,
            payment_date= evi_obj.payment_date,
            create_date = datetime.datetime.now(),
            create_user = user_id,
            update_date = datetime.datetime.now(),
            update_user = user_id
        )    
        logger.info(f'履歴情報テーブル登録 {evi_obj.pdf_name} : {evi_obj.evidence_id} -> {id}')
    except Exception:
        logger.exception(f'HtEvidence create exception {evi_obj.evidence_id} {id}')
        return False
    return id

# カテゴリ名フォルダから年月フォルダに移動
# def sv_category2date_file(eviobj):
#     if not eviobj.owner_id or not eviobj.category_name or not eviobj.processed_ym or not eviobj.pdf_name:
#         return False
#     new_path = False
#     category_dir = sv_get_category_path(eviobj.owner_id, eviobj.category_name)

#     if category_dir:
#     # new_path = shutil.move(file, dest_dir)
#     # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
#         category_file = os.path.join(category_dir, eviobj.pdf_name).replace(os.sep,'/')
#         if os.path.exists(category_file):
#             rootfolder = get_rootfolder(eviobj.owner_id)

#             dest_file = sv_get_processed_ym_path(rootfolder, eviobj.processed_ym, eviobj.pdf_name)
#             if dest_file != category_file:
#                 dest_file = check_filename(dest_file)
#                 new_path = shutil.move(category_file, dest_file)
#                 logger.info('move file : ' + category_file + '-->' + new_path)
#     return new_path

# エビデンス画像を作成する（存在しなかった場合に呼び出す）
def sv_create_evidence_image(evidence_id):
    try:
        eviobj = TtEvidence.objects.get(evidence_id=evidence_id)
    except TtEvidence.DoesNotExist:
        logger.exception(f'TtEvidence DoesNotExist {evidence_id=}')
        return False
    try:
        page_no = int(evidence_id[-5:-2])
    except Exception:   # ValueError
        return False
    filepath = sv_get_evidence_filename(eviobj)
    rootfolder = get_rootfolder(eviobj.owner_id)
    # make_evidence_image_dir(rootfolder)

    img_upload_dir = get_imgfolder_upload(rootfolder)
    ext = os.path.splitext(os.path.basename(filepath))[1]

    ocrimages = sv_create_ocr_image(filepath, img_upload_dir, page_no)

    if not ocrimages:
        return False
    imgfile = ocrimages[0]
    move_image(eviobj.owner_id, imgfile, evidence_id, False)    # MOVE
    # if ext.lower() == '.pdf':
    #     pdf_img = True
    #     # angle = sv_get_image_angle(imgfile)
    #     move_image(eviobj.owner_id, imgfile, evidence_id, False)    # MOVE
    # else:
    #     pdf_img = False
    #     # angle = sv_get_image_angle(filepath)
    #     move_image(eviobj.owner_id, imgfile, evidence_id, True) # COPY

    return evidence_id
