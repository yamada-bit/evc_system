import os
import shutil
import logging
import datetime
import platform

from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image # tiffile -> jpeg

from commons.utils import ut_get_localtime

JPEG = True # False
if platform.system() == 'Windows':
    # POPPLER_DIR = Path(__file__).resolve().parent.parent.parent / 'venv/poppler-0.68.0/bin'
    POPPLER_DIR = Path(__file__).resolve().parent.parent.parent / 'venv/poppler-25.12.0/Library/bin'
    # 一部の日本語文字だけが文字化けする場合が発生popplerのバージョンアップで対処 2025/04/03
OCR_DPI = 200     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う
# OCR_DPI=300     # 解像度でGoogle Cloud Vision APIのblockの区切りが違う

logger = logging.getLogger(__name__)

# アップロードファイルから画像ファイルを作成
def sv_create_ocr_image(path, img_dir, page_no):
    logger.debug(f'create image start {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
    ocrimages = []
    if not path or not os.path.exists(path):
        return ocrimages
    basename_without_ext, ext_name = os.path.splitext(os.path.basename(path))
    if not ext_name:
        logger.error(f'uploadfile ext name error {path=}')
    else:
        if ext_name.lower() == '.tif' or  ext_name.lower() == '.tiff':
            jpeg_path = sv_tiff_to_jpeg(path, img_dir)
            if jpeg_path:
                # os.remove(path)
                # path = jpeg_path
                ocrimages = [jpeg_path]
            else:
                ocrimages = []
        elif ext_name.lower() == '.pdf':
        # PDFをイメージ（JPEGタイプ）に変換
            ocrimages = sv_create_image(path, img_dir, OCR_DPI, page_no)
        else:
            ocrimages = sv_img_to_jpeg(path, img_dir)
            # ocrimages = [path]
        logger.info(f'create image {path} : {len(ocrimages) if ocrimages else 0}')
    logger.debug(f'create image end {ut_get_localtime().strftime("%Y/%m/%d %H:%M:%S")}')
    return ocrimages
# PDFファイルから画像ファイルを作成
def sv_create_image(pdffile, img_dir, dpi, page_no):
    imagefiles = []
    basename_without_ext, ext_name = os.path.splitext(os.path.basename(pdffile))
    if not ext_name or ext_name.lower() != '.pdf':
        logger.error(f'ext name error {pdffile}')
        return imagefiles
    if platform.system() == 'Windows':
        # Windowsの場合			
        # poppler/binフォルダにあるユーティリティをpdf2imageライブラリが利用するため、PATHを通しておく
        poppler_dir = POPPLER_DIR
        # poppler_dir =  settings.BASE_DIR + '/poppler-0.68.0/bin'
        os.environ['PATH'] += os.pathsep + str(poppler_dir)

    out_format = 'jpeg' if JPEG else 'png'
    try:
        images = convert_from_path(pdf_path=pdffile, dpi=dpi, fmt=out_format)   # 画像に変換
    except Exception:
        logger.exception(f'convert_from_path exception {pdffile=}')
        return imagefiles

    for i, image in enumerate(images):
        # image_path = str(image_dir) + basename_without_ext + '_{:02d}'.format(i + 1) + '.png'
        # 文字列結合でパスをつなぎ合わせると、不正なパスになることもある
        # image_path = os.path.join(image_dir, basename_without_ext + '_{:02d}'.format(i + 1) + '.png').replace(os.sep,'/')
        # image.save(image_path, 'PNG')
        if page_no == -1 or page_no == i + 1:
            try:
                file_name =  basename_without_ext + '_{:02d}'.format(i + 1) + ('.jpg' if JPEG else '.png')
                image_path = os.path.join(img_dir, file_name).replace(os.sep,'/')
                image.save(image_path, 'JPEG' if JPEG else 'PNG')
                imagefiles.append(image_path)
                logger.debug(f'pdf image save {image_path=}')
            except Exception:
                logger.exception(f'pdf image save exception {basename_without_ext}:{i + 1}')

    return imagefiles

# tiffファイルから画像ファイルを作成
def sv_tiff_to_jpeg(tiffile, img_dir):
    tiff = ['.tif','.tiff']
    basename_without_ext, ext_name = os.path.splitext(os.path.basename(tiffile))
    if not ext_name or not ext_name.lower() in tiff:
        logger.error(f'ext name error {tiffile=}')
        return False
    try:
        img = Image.open(tiffile).convert('RGB')
        file_name =  basename_without_ext + ('.jpg' if JPEG else '.png')
        image_path = os.path.join(img_dir, file_name).replace(os.sep,'/')
        img.save(image_path)
        logger.debug(f'tiff convert {tiffile} -> {image_path}')
    except Exception:
        image_path = False
        logger.exception(f'tiff convert exception {tiffile=}')
    return image_path

# 画像ファイルから画像ファイルを作成
def sv_img_to_jpeg(imgfile, img_dir):
    imagefiles = []

    basename_without_ext, ext_name = os.path.splitext(os.path.basename(imgfile))
    try:
        file_name =  basename_without_ext + '_01' + ('.jpg' if JPEG else '.png')
        image_path = os.path.join(img_dir, file_name).replace(os.sep,'/')
        # im = Image.open(imgfile) # 画像を開く
        # if 2400 < im.width or 2400 < im.height:
        #     im.thumbnail(size=(2400, 2400))   # アスペクト比を維持しながら、指定したサイズ以下の画像に縮小
        #     im.save(image_path) # JPEGの品質、デフォルトは75
        #     logger.debug('change image size ' + str(im.width) + ' : '  + str(im.height) + ' : ' + file_name)
        # else:
        #     # imcopy = im.copy()
        #     # imcopy.save(image_path)
        #     im.save(image_path)
        #     logger.debug('copy image ' + image_path + ' <- ' + imgfile)
        # im.close()
        if ext_name.lower() == '.jpg' or  ext_name.lower() == '.jpeg':
            image_path = shutil.copy(imgfile, image_path)
        else:
            img = Image.open(imgfile) # 画像を開く
            rgb_img = img.convert('RGB')
            rgb_img.save(image_path)
        imagefiles.append(image_path)
        logger.debug(f'copy image {image_path} <- {imgfile}')
    except Exception:
        logger.exception(f'image copy exception {imgfile}')
    return imagefiles
