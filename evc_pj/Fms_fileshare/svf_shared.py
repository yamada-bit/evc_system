import os
import datetime
import shutil
import logging
# import json
# from decimal import Decimal
from django.conf import settings
# from django.utils import timezone
# from django.utils.timezone import make_aware
from sequences import get_next_value

from Fms_fileshare.models import TtSharedFile
from commons.utils import ut_get_localdate,ut_get_timezone_now,ut_get_localtoday

from Evc_App.sv_file import (sv_delete_file, make_dir, sv_get_user_name,
                             get_imgfolder_upload, get_jsonfolder,
                             sv_get_textlines, sv_get_processed_ym_path
)
# from Evc_App.sv_search import sv_search_text
from Evc_App.sv_create_image import sv_create_ocr_image
# from Evc_App.sv_extract_text import sv_extract_text
# from Evc_App.sv_json import sv_save_json, sv_save_detect_json

OCR_DPI = 200     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う
# OCR_DPI = 300     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う

logger = logging.getLogger(__name__)

# ルートフォルダを取得(共有ファイル)
def svf_get_shared_rootfolder():
    root_folder = getattr(settings, 'EVC_ROOT')#.lower()
    root_folder = os.path.join(root_folder, 'sharedfiles').replace(os.sep,'/')
    if not os.path.isdir(root_folder):
        make_dir(root_folder)
    return root_folder
# 共有ファイルを保存するフォルダ作成
# 年月フォルダ
def svf_make_shared_dir(rootfolder):
    try:
        today = ut_get_localtoday()
        yy = today.strftime('%Y')
        yy_dir = os.path.join(rootfolder, yy).replace(os.sep,'/')
        make_dir(yy_dir)
        for i in range(1,13):
            mm = '{:02d}'.format(i)
            mm_dir = os.path.join(yy_dir, mm).replace(os.sep,'/')
            make_dir(mm_dir)
            img_dir = os.path.join(mm_dir, 'img').replace(os.sep,'/')
            make_dir(img_dir)
    except Exception:
        logger.exception(f'svf_make_shared_dir exception {rootfolder=}')
        return False
    return True

# 共有ファイル情報から画像ファイルpath(全ページ)を取得
def svf_get_shared_imagepath(sharedfile_obj):
    rootfolder = svf_get_shared_rootfolder()
    images = []
    try:
        # create_date = ut_get_localdate(sharedfile_obj.create_date)
        # if create_date:
        #     created_ym = create_date.strftime('%Y%m')
        # else:
        #     created_ym = sharedfile_obj.processed_ym
        created_ym = sharedfile_obj.processed_ym
        dest_dir = sv_get_processed_ym_path(rootfolder, created_ym) 
        for page_no in range(1, sharedfile_obj.page_count + 1):
            page_id = sharedfile_obj.shared_id + '_{:03d}'.format(page_no)
            filepath = os.path.join(dest_dir, 'img', page_id + '.jpg').replace(os.sep,'/')
            images.append(filepath)
    except Exception:
        logger.exception(f'svf_get_shared_imagepath exception {sharedfile_obj.shared_id}')
    return images
# 共有ファイルIDから画像ファイル名を取得
def get_shared_imagefile(shared_id, papge_no=1):
    imagepath = ''
    try:
        sharedfile_obj = TtSharedFile.objects.get(shared_id=shared_id,delete_flg=0)
    except TtSharedFile.DoesNotExist:
        sharedfile_obj = None
    if sharedfile_obj:
        images = svf_get_shared_imagepath(sharedfile_obj)
        if images:
            if papge_no <= len(images):
                imagepath = images[papge_no - 1]
            else:
                imagepath = images[0]
    return imagepath

# 共有ファイル情報登録
def svf_create_sharedfile(uploadfiles, user_id, owner_id):
    ok_list = []
    error_list = []
    rootfolder = svf_get_shared_rootfolder()
    img_upload_dir = get_imgfolder_upload(rootfolder)
    if not img_upload_dir:
        logger.error(f'upload imgfolder error {rootfolder=}')
        return ok_list, error_list
    json_dir = get_jsonfolder(rootfolder)
    for uploadfile in uploadfiles:
        filename = uploadfile.get('name')
        path = uploadfile.get('path')
        shared_type = uploadfile.get('shared_type')

        local_today = ut_get_localtoday()
        # 処理年月のフォルダに保存
        new_path = move_file_processed_ym(path, rootfolder, filename, local_today).replace('\\', '/')
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
        # 共有ファイル情報テーブルデータ作成・登録
        save_id = svf_create_sharedfile_page(new_path, user_id, owner_id, local_today, shared_type, page_count)
        logger.debug(f'create sharedfile page {save_id}')
        if save_id:
            for idx, imgfile in enumerate(ocrimages):
                if imgfile:
                    # 画像移動(共有ファイル情報画像ファイル保存)
                    move_image(owner_id, imgfile, save_id, idx + 1, False)   # MOVE
            ok_list.append(filename)
        else:
            error_list.append(filename)
            logger.error(f'create sharedfile page error {filename=}')
            sv_delete_file(new_path)    # アップロードファイル削除

        # # OCR機能で使用した画像ファイルを削除
        # basename_without_ext, ext_name = os.path.splitext(os.path.basename(path))
        # # if ocrimages and ext_name.lower() == '.pdf':
        # #     delete_files(ocrimages)
        # if shared_type == 'file' and ext_name.lower() == '.pdf':
        #     if 1 < len(ocrimages):
        #         ocrimages.pop(0)    # 先頭ページのみ残す
        #         delete_files(ocrimages)
    return ok_list, error_list
# ファイルは、年月フォルダ(当月)に移動
def move_file_processed_ym(filepath, rootfolder, basename, local_today):
    new_path = filepath
    if not filepath or not os.path.exists(filepath):
        return new_path
    try:
        processed_ym = local_today.strftime('%Y%m')
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
        # dt_now = ut_get_timezone_now()
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
# 共有ファイル情報ID取得
# shared_id：yyyymmdd_連番(00001～)
def get_sharedfile_id():
    d = ut_get_localtoday().strftime('%Y%m%d')
    try:
        # シーケンス採番
        num = get_next_value(f'shared_{d}')
        id = d + '_{:05d}'.format(num)
        # lastobj = TtSharedFile.objects.all().order_by('-shared_id').first()
        # # first():存在しない場合Noneを返す
        # if lastobj:
        #     pre_id = lastobj.shared_id
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
    except Exception:   # ValueError
        id = d + '_00001'

    return id
# 共有ファイル情報テーブルデータ作成・登録
def svf_create_sharedfile_page(filepath, user_id, owner_id, local_today, shared_type, pages):
    basename = os.path.basename(filepath)
    basename_without_ext, ext_name = os.path.splitext(basename)
    pdf_name = basename_without_ext
    # d = ut_get_localtoday().strftime('%Y%m%d')
    create_date = ut_get_timezone_now()
    create_user_id = user_id
    id = get_sharedfile_id()
    shared_date = local_today.strftime('%Y%m%d')
    # google_amount = pages
    # 共有ファイル名
    processed_ym = local_today.strftime('%Y%m')
    name = f'{processed_ym}_{sv_get_user_name(user_id)}'
    try:
        obj = TtSharedFile(
            shared_id = id,
            shared_name = pdf_name,#name,
            owner_id = owner_id,
            file_name = pdf_name,
            file_path = filepath,
            shared_type = shared_type,
            shared_date = shared_date,
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
        logger.info(f'共有ファイル情報情報テーブル登録 {id} : {pdf_name}')
    except Exception:
        logger.exception(f'TtSharedFile save exception {pdf_name}')
        return False
    return id
# 画像移動(共有ファイル情報画像保存)
def move_image(owner_id, filepath, shared_id, page_no, copy):
    if not filepath or not os.path.exists(filepath):
        return
    new_path = filepath

    if filepath and shared_id:
        try:
            # rootfolder = get_rootfolder(owner_id)
            # img_dir = get_shared_image_dir(rootfolder)
            # # basename_without_ext, ext_name = os.path.splitext(os.path.basename(filepath))
            # file_name =  os.path.join(img_dir, shared_id + '.jpg').replace(os.sep,'/')
            file_name = get_shared_imagefile(shared_id, page_no)
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
            logger.exception(f'move_image exception {shared_id=} {filepath=}')

def delete_files(files):
    if files:
        for file in files:
            sv_delete_file(file)

# 共有ファイル情報情報テーブル更新
def svf_update_sharedfile(shared_id, shared_name, shared_type, shared_date, notes, user_id):
    # owner_id = get_owner_id(user_id)
    try:
        sharedfile_obj = TtSharedFile.objects.get(shared_id=shared_id)
    except TtSharedFile.DoesNotExist:
        logger.exception(f'TtSharedFile DoesNotExist {shared_id=}')
        return False
        # raise ValueError('共有ファイル情報情報テーブル更新エラー!')
    # if shared_obj.category_name != category:
    #     new_path = sv_change_category(owner_id, shared_obj.pdf_name, shared_obj.category_name, category)
    #     # shared_obj.pdf_name = os.path.splitext(os.path.basename(new_path))[0]
    #     if new_path:
    #         shared_obj.pdf_name = os.path.basename(new_path)
    sharedfile_obj.create_date = ut_get_localdate(sharedfile_obj.create_date)
    sharedfile_obj.update_user = user_id
    sharedfile_obj.update_date = ut_get_timezone_now()
    sharedfile_obj.shared_name = shared_name
    sharedfile_obj.shared_type = shared_type
    # sharedfile_obj.processed_ym = processed_ym
    sharedfile_obj.shared_date = shared_date
    sharedfile_obj.notes = notes

    try:
        sharedfile_obj.save()
        logger.info(f'共有ファイル情報情報テーブル更新 {shared_id} : {sharedfile_obj.file_name}')
    except Exception:
        logger.exception(f'TtSharedFile update exception {shared_id} : {sharedfile_obj.file_name}')
        return False
    return shared_id

# 共有ファイル情報情報テーブル論理削除
def svf_delete_sharedfile(shared_id, shared_name, shared_date, notes, user_id):
    # owner_id = get_owner_id(user_id)
    try:
        sharedfile_obj = TtSharedFile.objects.get(shared_id=shared_id)
    except TtSharedFile.DoesNotExist:
        logger.exception(f'TtSharedFile DoesNotExist {shared_id=}')
        return False
    sharedfile_obj.delete_flg = 1
    sharedfile_obj.create_date = ut_get_localdate(sharedfile_obj.create_date)
    sharedfile_obj.update_user = user_id
    sharedfile_obj.update_date = ut_get_timezone_now()
    if shared_name:
        sharedfile_obj.shared_name = shared_name
    # if processed_ym:
    #     sharedfile_obj.processed_ym = processed_ym
    if shared_date:
        sharedfile_obj.shared_date = shared_date
    if notes:
        sharedfile_obj.notes = notes
    filename = sharedfile_obj.file_name
    try:
        sharedfile_obj.save()
    except Exception:
        logger.exception(f'TtSharedFile delete exception {shared_id} : {filename}')
        return False
    logger.info(f'共有ファイル情報情報データ削除 {shared_id} : {filename}')

    return filename
# 共有ファイル情報情報削除フラグ・物理削除
def svf_physical_delete_all():
    sharedfiles = TtSharedFile.objects.filter(delete_flg=1)
    cnt = 0
    for sharedfile_obj in sharedfiles:
        shared_id = sharedfile_obj.shared_id
        try:
            delete_sharedfile(sharedfile_obj)
        except Exception:
            logger.exception(f'delete exception {shared_id=}')
        filename = sharedfile_obj.file_name
        sharedfile_obj.delete()    # 共有ファイル情報情報テーブルから削除
        logger.info(f'共有ファイル情報情報データ削除 {shared_id} : {filename}')
        cnt += 1
    return cnt

# 共有ファイル情報情報削除・物理削除
def svf_physical_delete_sharedfile(shared_id):
    try:
        sharedfile_obj = TtSharedFile.objects.get(shared_id=shared_id)
    except TtSharedFile.DoesNotExist:
        logger.exception(f'TtSharedFile DoesNotExist {shared_id=}')
        return False
        # raise ValueError('共有ファイル情報情報削除　取得エラー ' + shared_id)
    try:
        delete_sharedfile(sharedfile_obj)
    except Exception:
        logger.exception(f'delete exception {shared_id=}')
    filename = sharedfile_obj.file_name
    sharedfile_obj.delete()    # 共有ファイル情報情報テーブルから削除
    logger.info(f'共有ファイル情報情報データ削除 {shared_id} : {filename}')

    return filename
# 共有ファイル情報ファイル削除
def delete_sharedfile(sharedfile_obj):
    shared_id = sharedfile_obj.shared_id
    # dest_dir = sv_get_category_path(owner_id, shared_obj.category_name)
    # dest_file = sv_get_processed_ym_path(owner_id, shared_obj.processed_ym, shared_obj.pdf_name)  
    dest_file = sharedfile_obj.file_path

    # 削除データも閲覧できるように画像ファイルは削除しない
    # # rootfolder = get_rootfolder(owner_id)
    # # img_dir = get_shared_image_dir(rootfolder)
    # # file_name =  os.path.join(img_dir, shared_id + '.jpg').replace(os.sep,'/')
    # file_name = get_shared_imagefile(shared_id)
    # sv_delete_file(file_name)   # 共有ファイル情報画像ファイルを削除
    images = svf_get_shared_imagepath(sharedfile_obj)
    for file_name in images:
        sv_delete_file(file_name)   # 共有ファイル情報画像ファイルを削除

    if dest_file:
        sv_delete_file(dest_file)   # ファイルを削除
        logger.info(f'共有ファイル情報ファイル削除 {shared_id} : {dest_file}')
        # # jsonファイル
        # rootfolder = get_rootfolder(owner_id)
        # if rootfolder:
        #     json_dir = get_jsonfolder(rootfolder)
        #     if json_dir:
        #         sv_delete_fulltext(json_dir, dest_file)    # json全文データから削除
        # basename_without_ext = os.path.splitext(shared_obj.pdf_name)[0]
        # jsonfile = os.path.join(json_dir, basename_without_ext + '.json').replace(os.sep,'/')
        # os.remove(jsonfile)   # jsonファイルの削除
    return True
