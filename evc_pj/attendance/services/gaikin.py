"""
外勤報告書ファイル管理サービス（旧 Kms_Calendar/svk_report.py）。

【ファイル保存先】
  settings.ATTENDANCE_GAIKIN_ROOT（例: /data_root/Gaikin）
  └── YYYY/                ← 年フォルダ
      └── MM/              ← 月フォルダ
          ├── <ファイル名>  ← アップロードされた PDF / 画像
          └── img/         ← PDF から変換した画像ページ
              └── <report_id>_001.jpg  など

【レポートID形式】
  yyyymmdd_連番(00001〜)  例: 20260625_00001
"""
import logging
import os
import shutil

from django.conf import settings

using_db: str = settings.ATTENDANCE_DB

from commons.utils import ut_get_localdate, ut_get_localtoday, ut_get_timezone_now
from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_file import (
    get_imgfolder_upload,
    get_jsonfolder,
    make_dir,
    sv_delete_file,
    sv_get_processed_ym_path,
    sv_get_user_name,
)

from ..models import GaikinReport

logger = logging.getLogger(__name__)


def get_gaikin_rootfolder() -> str:
    """外勤報告書のルートフォルダパスを返す。存在しない場合は自動作成する。"""
    root_folder = getattr(settings, 'ATTENDANCE_GAIKIN_ROOT', '/data_root/Gaikin')
    root_folder = root_folder.replace(os.sep, '/')
    if not os.path.isdir(root_folder):
        make_dir(root_folder)
    return root_folder


def make_report_dir(rootfolder: str) -> bool:
    """外勤報告書ファイルを保存するための 年/月/img フォルダ群を作成する。"""
    try:
        today = ut_get_localtoday()
        yy = today.strftime('%Y')
        yy_dir = os.path.join(rootfolder, yy).replace(os.sep, '/')
        make_dir(yy_dir)
        for i in range(1, 13):
            mm = f'{i:02d}'
            mm_dir = os.path.join(yy_dir, mm).replace(os.sep, '/')
            make_dir(mm_dir)
            img_dir = os.path.join(mm_dir, 'img').replace(os.sep, '/')
            make_dir(img_dir)
    except Exception:
        logger.exception(f'make_report_dir exception {rootfolder=}')
        return False
    return True


def get_report_imagepath(report_obj: GaikinReport) -> list[str]:
    """報告書オブジェクトから、各ページの画像ファイルパスリストを返す。"""
    rootfolder = get_gaikin_rootfolder()
    images = []
    try:
        create_date = ut_get_localdate(report_obj.create_date)
        created_ym = create_date.strftime('%Y%m') if create_date else report_obj.processed_ym
        dest_dir = sv_get_processed_ym_path(rootfolder, created_ym)
        for page_no in range(1, report_obj.page_count + 1):
            page_id = report_obj.report_id + f'_{page_no:03d}'
            filepath = os.path.join(dest_dir, 'img', page_id + '.jpg').replace(os.sep, '/')
            images.append(filepath)
    except Exception:
        logger.exception(f'get_report_imagepath exception {report_obj.report_id}')
    return images


def get_report_imagefile(report_id: str, page_no: int = 1) -> str:
    """指定ページの画像ファイルパスを返す。取得できない場合は空文字。"""
    try:
        report_obj = GaikinReport.objects.using(using_db).get(report_id=report_id, delete_flg=0)
    except GaikinReport.DoesNotExist:
        return ''
    images = get_report_imagepath(report_obj)
    if not images:
        return ''
    idx = page_no - 1 if page_no <= len(images) else 0
    return images[idx]


def get_report_id() -> str:
    """本日日付ベースの採番IDを返す（形式: yyyymmdd_00001）。"""
    d = ut_get_localtoday().strftime('%Y%m%d')
    try:
        last_obj = GaikinReport.objects.using(using_db).all().order_by('-report_id').first()
        if last_obj:
            pre_id = last_obj.report_id
            try:
                last_date = int(pre_id[:8])
                if last_date < int(d):
                    return d + '_00001'
                num = int(pre_id[9:14])
                return d + f'_{num + 1:05d}'
            except Exception:
                return d + '_00001'
    except Exception:
        pass
    return d + '_00001'


def _check_filename(file: str) -> str:
    """同名ファイルが存在する場合は末尾に (連番) を付けて返す。"""
    if os.path.exists(file):
        filepath, ext = os.path.splitext(file)
        for i in range(1, 100000):
            new_path = f'{filepath}({i}){ext}'
            if not os.path.exists(new_path):
                return new_path
        logger.error(f'same file over 100000 {file=}')
    return file


def _move_file_processed_ym(filepath: str, rootfolder: str, basename: str) -> str:
    """アップロードファイルを当月フォルダへ移動する。"""
    if not filepath or not os.path.exists(filepath):
        return filepath
    try:
        processed_ym = ut_get_localtoday().strftime('%Y%m')
        dest_dir = sv_get_processed_ym_path(rootfolder, processed_ym)
        dest_file = os.path.join(dest_dir, basename).replace(os.sep, '/')
        if dest_file != filepath:
            dest_file = _check_filename(dest_file)
            new_path = shutil.move(filepath, dest_file)
            logger.info(f'move file {filepath} --> {new_path}')
            return new_path
    except Exception:
        logger.exception(f'move file exception {filepath=}')
    return filepath


def _move_image(report_id: str, filepath: str, page_no: int) -> None:
    """OCR変換済み画像を所定の img フォルダへ移動する。"""
    if not filepath or not os.path.exists(filepath):
        return
    try:
        file_name = get_report_imagefile(report_id, page_no)
        if file_name:
            shutil.move(filepath, file_name)
            logger.debug(f'move imagefile {filepath} --> {file_name}')
    except Exception:
        logger.exception(f'_move_image exception {report_id=} {filepath=}')


def _create_report_record(filepath: str, user_id: str, owner_id: str, pages: int):
    """報告書情報テーブルにレコードを登録して report_id を返す。失敗時は False。"""
    basename = os.path.basename(filepath)
    pdf_name = os.path.splitext(basename)[0]
    processed_ym = ut_get_localtoday().strftime('%Y%m')
    report_name = f'{processed_ym}_{sv_get_user_name(user_id)}'
    report_id = get_report_id()
    try:
        obj = GaikinReport(
            report_id=report_id,
            report_name=report_name,
            owner_id=owner_id,
            pdf_name=pdf_name,
            file_path=filepath,
            processed_ym=processed_ym,
            page_count=pages,
            delete_flg=0,
            notes='',
            create_date=ut_get_timezone_now(),
            create_user=user_id,
            update_user=user_id,
            update_date=ut_get_timezone_now(),
        )
        obj.save(using=using_db)
        logger.info(f'GaikinReport 登録 {report_id} : {pdf_name}')
    except Exception:
        logger.exception(f'GaikinReport save exception {pdf_name}')
        return False
    return report_id


def create_report(uploadfiles: list[dict], user_id: str, owner_id: str) -> tuple[list, list]:
    """
    アップロードファイルリストを処理して外勤報告書を登録する。

    引数:
      uploadfiles: [{'name': 元ファイル名, 'path': 保存先パス}, ...]
    戻り値:
      (ok_list, error_list) — 処理成功/失敗のファイル名リスト
    """
    ok_list, error_list = [], []
    rootfolder = get_gaikin_rootfolder()
    img_upload_dir = get_imgfolder_upload(rootfolder)
    if not img_upload_dir:
        logger.error(f'upload imgfolder error {rootfolder=}')
        return ok_list, error_list

    for uploadfile in uploadfiles:
        filename = uploadfile.get('name', '')
        path = uploadfile.get('path', '')
        new_path = _move_file_processed_ym(path, rootfolder, filename).replace('\\', '/')
        ocrimages = sv_create_ocr_image(new_path, img_upload_dir, -1)
        if not ocrimages:
            logger.error(f'ocrimages error {filename=}')
            error_list.append(filename)
            sv_delete_file(new_path)
            continue

        page_count = len(ocrimages)
        report_id = _create_report_record(new_path, user_id, owner_id, page_count)
        if report_id:
            for idx, imgfile in enumerate(ocrimages):
                if imgfile:
                    _move_image(report_id, imgfile, idx + 1)
            ok_list.append(filename)
        else:
            error_list.append(filename)
            logger.error(f'create_report_record error {filename=}')
            sv_delete_file(new_path)

    return ok_list, error_list


def update_report(report_id: str, report_name: str, processed_ym: str, notes: str, user_id: str):
    """報告書情報を更新する。成功時は report_id、失敗時は False を返す。"""
    try:
        obj = GaikinReport.objects.using(using_db).get(report_id=report_id)
    except GaikinReport.DoesNotExist:
        logger.exception(f'GaikinReport DoesNotExist {report_id=}')
        return False
    obj.report_name = report_name
    obj.processed_ym = processed_ym
    obj.notes = notes
    obj.update_user = user_id
    obj.update_date = ut_get_timezone_now()
    try:
        obj.save(using=using_db)
        logger.info(f'GaikinReport 更新 {report_id} : {obj.pdf_name}')
    except Exception:
        logger.exception(f'GaikinReport update exception {report_id}')
        return False
    return report_id


def physical_delete_report(report_id: str):
    """報告書情報とファイル（PDF / 画像）を物理削除する。成功時は pdf_name、失敗時は False。"""
    try:
        obj = GaikinReport.objects.using(using_db).get(report_id=report_id)
    except GaikinReport.DoesNotExist:
        logger.exception(f'GaikinReport DoesNotExist {report_id=}')
        return False

    # 関連ファイルを先に削除
    for img_path in get_report_imagepath(obj):
        sv_delete_file(img_path)
    if obj.file_path:
        sv_delete_file(obj.file_path)
        logger.info(f'GaikinReport ファイル削除 {report_id} : {obj.file_path}')

    filename = obj.pdf_name
    obj.delete(using=using_db)
    logger.info(f'GaikinReport 物理削除 {report_id} : {filename}')
    return filename
