import logging
import os
import shutil

# import json
# from decimal import Decimal
from django.conf import settings

from commons.utils import ut_get_localdate, ut_get_localtoday, ut_get_timezone_now

# from Evc_App.sv_search import sv_search_text
from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_file import (
    get_imgfolder_upload,
    get_jsonfolder,
    make_dir,
    sv_delete_file,
    sv_get_processed_ym_path,
    sv_get_user_name,
)

# from Evc_App.sv_extract_text import sv_extract_text
# from django.utils import timezone
# from django.utils.timezone import make_aware
# from sequences import get_next_value
from Kms_Calendar.models import TtGaikinReport

OCR_DPI = 200     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う
# OCR_DPI = 300     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う

logger = logging.getLogger(__name__)

# ルートフォルダを取得(外勤報告書)
def svk_get_gaikin_rootfolder():
    root_folder = getattr(settings, 'EVC_ROOT')#.lower()
    root_folder = os.path.join(root_folder, 'Gaikin').replace(os.sep,'/')
    if not os.path.isdir(root_folder):
        make_dir(root_folder)
    return root_folder
# 外勤報告書ファイルを保存するフォルダ作成
# 年月フォルダ
def svk_make_report_dir(rootfolder):
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
        logger.exception(f'svk_make_report_dir exception {rootfolder=}')
        return False
    return True

# 外勤報告書情報から画像ファイル名を取得
def svk_get_report_imagepath(report_obj):
    rootfolder = svk_get_gaikin_rootfolder()
    images = []
    try:
        create_date = ut_get_localdate(report_obj.create_date)
        if create_date:
            created_ym = create_date.strftime('%Y%m')
        else:
            created_ym = report_obj.processed_ym
        dest_dir = sv_get_processed_ym_path(rootfolder, created_ym)
        for page_no in range(1, report_obj.page_count + 1):
            page_id = report_obj.report_id + f'_{page_no:03d}'
            filepath = os.path.join(dest_dir, 'img', page_id + '.jpg').replace(os.sep,'/')
            images.append(filepath)
    except Exception:
        logger.exception(f'svk_get_report_imagepath exception {report_obj.report_id}')
    return images
# 報告書IDから画像ファイル名を取得
def get_report_imagefile(report_id, papge_no=1):
    imagepath = ''
    try:
        report_obj = TtGaikinReport.objects.get(report_id=report_id,delete_flg=0)
    except TtGaikinReport.DoesNotExist:
        report_obj = None
    if report_obj:
        images = svk_get_report_imagepath(report_obj)
        if images:
            if papge_no <= len(images):
                imagepath = images[papge_no - 1]
            else:
                imagepath = images[0]
    return imagepath

# 外勤報告書情報登録
def svk_create_report(uploadfiles, user_id, owner_id):
    ok_list = []
    error_list = []
    rootfolder = svk_get_gaikin_rootfolder()
    img_upload_dir = get_imgfolder_upload(rootfolder)
    if not img_upload_dir:
        logger.error(f'upload imgfolder error {rootfolder=}')
        return ok_list, error_list
    json_dir = get_jsonfolder(rootfolder)
    for uploadfile in uploadfiles:
        filename = uploadfile.get('name')
        path = uploadfile.get('path')
        # 処理年月のフォルダに保存
        new_path = move_file_processed_ym(path, rootfolder, filename).replace('\\', '/')
        # ページごとに画像データを作成
        ocrimages = sv_create_ocr_image(new_path, img_upload_dir, -1)
        if not ocrimages:   # パスワード設定などにより読み込めない
            logger.error(f'ocrimages error {filename=}')
            error_list.append(filename)
            sv_delete_file(new_path)    # アップロードファイル削除
            continue

        textdatas = []

        logger.debug(f'extract text {filename=}')

        save_id = False
        page_count = len(ocrimages)
        # 報告書情報テーブルデータ作成・登録
        save_id = svk_create_report_page(new_path, user_id, owner_id, page_count)
        logger.debug(f'create report page {save_id}')
        if save_id:
            for idx, imgfile in enumerate(ocrimages):
                if imgfile:
                    # 画像移動(報告書情報画像ファイル保存)
                    move_image(owner_id, imgfile, save_id, idx + 1, False)   # MOVE
            ok_list.append(filename)
        else:
            error_list.append(filename)
            logger.error(f'create report page error {filename=}')
            sv_delete_file(new_path)    # アップロードファイル削除

        # # OCR機能で使用した画像ファイルを削除
        # basename_without_ext, ext_name = os.path.splitext(os.path.basename(path))
        # # if ocrimages and ext_name.lower() == '.pdf':
        # #     delete_files(ocrimages)
        # if report_kubun == 'file' and ext_name.lower() == '.pdf':
        #     if 1 < len(ocrimages):
        #         ocrimages.pop(0)    # 先頭ページのみ残す
        #         delete_files(ocrimages)
    return ok_list, error_list
# ファイルは、年月フォルダ(当月)に移動
def move_file_processed_ym(filepath, rootfolder, basename):
    new_path = filepath
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
        logger.exception(f'move file exception {filepath=}')

    return new_path
# 同じファイル名が存在する場合　'(連番)'　追加
def check_filename(file):
    if os.path.exists(file):
        # 別日付の場合
        # dt = datetime.datetime.fromtimestamp(os.path.getmtime(file))
        # dt_now = ut_get_localtoday()
        # if dt.year != dt_now.year or dt.month != dt_now.month or dt.day != dt_now.day:
        filepath, ext = os.path.splitext(file)
        i = 1
        while i < 100000:
            new_path = f'{filepath}({i}){ext}'
            if not os.path.exists(new_path):
                return new_path
            i += 1
        logger.error(f'same file over 100000 {file=}')
    return file
# 報告書情報ID取得
# report_id：yyyymmdd_連番(00001～)
def get_report_id():
    d = ut_get_localtoday().strftime('%Y%m%d')
    try:
        # # シーケンス採番
        # num = get_next_value(d)
        # id = d + '_{:05d}'.format(num)
        lastobj = TtGaikinReport.objects.all().order_by('-report_id').first()
        # first():存在しない場合Noneを返す
        if lastobj:
            pre_id = lastobj.report_id
            try:
                last = int(pre_id[:8])
                if last < int(d):
                    id = d + '_00001'
                else:
                    # num = int(pre_id[-5:])
                    num = int(pre_id[9:14])
                    id = d + f'_{num + 1:05d}'
            except Exception:   # ValueError
                id = d + '_00001'
        else:
            id = d + '_00001'
    except Exception:   # ValueError
        id = d + '_00001'

    return id
# 報告書情報テーブルデータ作成・登録
def svk_create_report_page(filepath, user_id, owner_id, pages):
    basename = os.path.basename(filepath)
    basename_without_ext, ext_name = os.path.splitext(basename)
    pdf_name = basename_without_ext
    # d = ut_get_localtoday().strftime('%Y%m%d')
    create_date = ut_get_timezone_now()
    create_user_id = user_id
    id = get_report_id()
    # 報告月
    processed_ym = ut_get_localtoday().strftime('%Y%m')
    # google_amount = pages
    # 報告書名
    name = f'{processed_ym}_{sv_get_user_name(user_id)}'
    try:
        obj = TtGaikinReport(
            report_id = id,
            report_name = name,
            owner_id = owner_id,
            pdf_name = pdf_name,
            file_path = filepath,
            processed_ym = processed_ym,
            page_count = pages,
            delete_flg = 0,
            notes = '',
            # google_amount = google_amount,
            create_date = create_date,                # DateTimeField
            create_user = create_user_id,
            update_user = user_id,
            update_date = ut_get_timezone_now()     # DateTimeField
        )
        obj.save()
        logger.info(f'報告書情報情報テーブル登録 {id} : {pdf_name}')
    except Exception:
        logger.exception(f'TtGaikinReport save exception {pdf_name}')
        return False
    return id
# 画像移動(報告書情報画像保存)
def move_image(owner_id, filepath, report_id, page_no, copy):
    if not filepath or not os.path.exists(filepath):
        return
    new_path = filepath

    if filepath and report_id:
        try:
            # rootfolder = get_rootfolder(owner_id)
            # img_dir = get_report_image_dir(rootfolder)
            # # basename_without_ext, ext_name = os.path.splitext(os.path.basename(filepath))
            # file_name =  os.path.join(img_dir, report_id + '.jpg').replace(os.sep,'/')
            file_name = get_report_imagefile(report_id, page_no)
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
            logger.exception(f'move_image exception {report_id=} {filepath=}')

def delete_files(files):
    if files:
        for file in files:
            sv_delete_file(file)

# 報告書情報情報テーブル更新
def svk_update_report(report_id, report_name, processed_ym, notes, user_id):
    # owner_id = get_owner_id(user_id)
    try:
        report_obj = TtGaikinReport.objects.get(report_id=report_id)
    except TtGaikinReport.DoesNotExist:
        logger.exception(f'TtGaikinReport DoesNotExist {report_id=}')
        return False
        # raise ValueError('報告書情報情報テーブル更新エラー!')
    # if report_obj.category_name != category:
    #     new_path = sv_change_category(owner_id, report_obj.pdf_name, report_obj.category_name, category)
    #     # report_obj.pdf_name = os.path.splitext(os.path.basename(new_path))[0]
    #     if new_path:
    #         report_obj.pdf_name = os.path.basename(new_path)
    report_obj.create_date = ut_get_localdate(report_obj.create_date)
    report_obj.update_user = user_id
    report_obj.update_date = ut_get_timezone_now()
    report_obj.report_name = report_name
    report_obj.processed_ym = processed_ym
    report_obj.notes = notes

    try:
        report_obj.save()
        logger.info(f'報告書情報情報テーブル更新 {report_id} : {report_obj.pdf_name}')
    except Exception:
        logger.exception(f'TtGaikinReport update exception {report_id} : {report_obj.pdf_name}')
        return False
    return report_id

# 報告書情報情報テーブル論理削除
def svk_delete_report(report_id, report_name, processed_ym, notes, user_id):
    # owner_id = get_owner_id(user_id)
    try:
        report_obj = TtGaikinReport.objects.get(report_id=report_id)
    except TtGaikinReport.DoesNotExist:
        logger.exception(f'TtGaikinReport DoesNotExist {report_id=}')
        return False
    report_obj.delete_flg = 1
    report_obj.create_date = ut_get_localdate(report_obj.create_date)
    report_obj.update_user = user_id
    report_obj.update_date = ut_get_timezone_now()
    if report_name:
        report_obj.report_name = report_name
    if processed_ym:
        report_obj.processed_ym = processed_ym
    if notes:
        report_obj.notes = notes
    filename = report_obj.pdf_name
    try:
        report_obj.save()
    except Exception:
        logger.exception(f'TtGaikinReport delete exception {report_id} : {filename}')
        return False
    logger.info(f'報告書情報情報データ削除 {report_id} : {filename}')

    return filename
# 報告書情報情報削除フラグ・物理削除
def svk_physical_delete_all():
    reports = TtGaikinReport.objects.filter(delete_flg=1)
    cnt = 0
    for report_obj in reports:
        report_id = report_obj.report_id
        try:
            delete_report_file(report_obj)
        except Exception:
            logger.exception(f'delete exception {report_id=}')
        filename = report_obj.pdf_name
        report_obj.delete()    # 報告書情報情報テーブルから削除
        logger.info(f'報告書情報情報データ削除 {report_id} : {filename}')
        cnt += 1
    return cnt

# 報告書情報情報削除・物理削除
def svk_physical_delete_report(report_id):
    try:
        report_obj = TtGaikinReport.objects.get(report_id=report_id)
    except TtGaikinReport.DoesNotExist:
        logger.exception(f'TtGaikinReport DoesNotExist {report_id=}')
        return False
        # raise ValueError('報告書情報情報削除　取得エラー ' + report_id)
    try:
        delete_report_file(report_obj)
    except Exception:
        logger.exception(f'delete exception {report_id=}')
    filename = report_obj.pdf_name
    report_obj.delete()    # 報告書情報情報テーブルから削除
    logger.info(f'報告書情報情報データ削除 {report_id} : {filename}')

    return filename
# 報告書情報ファイル削除
def delete_report_file(report_obj):
    report_id = report_obj.report_id
    # dest_dir = sv_get_category_path(owner_id, report_obj.category_name)
    # dest_file = sv_get_processed_ym_path(owner_id, report_obj.processed_ym, report_obj.pdf_name)
    dest_file = report_obj.file_path

    # 削除データも閲覧できるように画像ファイルは削除しない
    # # rootfolder = get_rootfolder(owner_id)
    # # img_dir = get_report_image_dir(rootfolder)
    # # file_name =  os.path.join(img_dir, report_id + '.jpg').replace(os.sep,'/')
    # file_name = get_report_imagefile(report_id)
    # sv_delete_file(file_name)   # 報告書情報画像ファイルを削除
    images = svk_get_report_imagepath(report_obj)
    for file_name in images:
        sv_delete_file(file_name)   # 報告書情報画像ファイルを削除

    if dest_file:
        sv_delete_file(dest_file)   # ファイルを削除
        logger.info(f'報告書情報ファイル削除 {report_id} : {dest_file}')
        # # jsonファイル
        # rootfolder = get_rootfolder(owner_id)
        # if rootfolder:
        #     json_dir = get_jsonfolder(rootfolder)
        #     if json_dir:
        #         sv_delete_fulltext(json_dir, dest_file)    # json全文データから削除
        # basename_without_ext = os.path.splitext(report_obj.pdf_name)[0]
        # jsonfile = os.path.join(json_dir, basename_without_ext + '.json').replace(os.sep,'/')
        # os.remove(jsonfile)   # jsonファイルの削除
    return True
