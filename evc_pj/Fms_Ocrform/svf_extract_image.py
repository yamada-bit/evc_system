import fitz  # PyMuPDF
import os
import cv2	
import numpy as np	
import logging

logger = logging.getLogger(__name__)

def extract_image_from_pdf(pdf_path, output_dir, img1_path):
    """
    PDFファイルから特定の画像が含まれるページを抽出する関数。
    Args:
        pdf_path (str): 処理するPDFファイルのパス。
        output_dir (str, optional): 抽出した画像を一時的に保存するディレクトリ。
        img1_path: 抽出する画像
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.exception(f"PDFファイルを開けませんでした: {e}")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    basename_without_ext, ext_name = os.path.splitext(os.path.basename(pdf_path))
    matching_pages = []
    try:
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            img_list = page.get_images(full=True)  # 画像のリストを取得
            # 画像を抽出して保存
            for img_index, img in enumerate(img_list):
                xref = img[0]  # 画像のXREF番号
                base_image = doc.extract_image(xref)
                # image_bytes = base_image.get_pixmap()
                image_ext = 'jpg'
                image_name = f"output_image_page{page_num+1}_img{img_index+1}.{image_ext}"
                image_path = os.path.join(output_dir, image_name)
                with open(image_path, 'wb') as f:
                    f.write(base_image["image"])

                # 比較する画像ファイルのパス
                img2_path = image_path

                # 特徴点のマッチングを行う
                result = feature_matching(img1_path, img2_path)
                if os.path.exists(image_path):
                    os.remove(image_path)
                if result:
                    matching_pages.append(page_num + 1)
                    break
    except Exception:
        logger.exception(f'extract_image_from_pdf exception {basename_without_ext}')
    doc.close()
            
    return matching_pages

def feature_matching(img1_path, img2_path):
    # 画像をグレースケールで読み込み
    img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
    # 画像が読み込まれていない場合は終了
    if img1 is None or img2 is None:
        logger.error("画像が正しく読み込まれていません。")
        return False
    # 画像のサイズを一致させる
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    # ORBの特徴点検出器を作成
    orb = cv2.ORB_create(1000)
    # 特徴点とディスクリプタを計算
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)
    sift = None
    if des1 is None or des2 is None:
        # SIFT検出器を作成
        # SIFTは特許(特許期限が切れた?）があるため、商用利用には制限がある場合があります
        sift = cv2.SIFT_create()

        # 特徴点とディスクリプタを計算
        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)

    # 特徴点が検出されていない場合は終了
    if des1 is None or des2 is None:
        logger.error("特徴量が計算できませんでした。")
        return False
    if not sift:
        # ブルートフォースマッチャーで特徴量をマッチング
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    else:
        # BFMatcherを使用して、ディスクリプタの距離を計算
        # NORM_L2 はSIFTのディスクリプタに対して適切な距離計算方法です
        bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)

    # 特徴量マッチングを行う
    matches = bf.match(des1, des2)

    # # マッチング結果を距離順にソート
    # matches = sorted(matches, key=lambda x: x.distance)

    # マッチングした特徴点の数が閾値以上なら、一致とみなす
    # if len(matches) > 10:  # 10個以上の特徴点が一致すれば一致とみなす
    if len(matches) > 100:  # 100個以上の特徴点が一致すれば一致とみなす
        # 幾何的整合性（RANSACによるホモグラフィ推定）
        # 間違ったマッチを排除するために、対応点の整合性を幾何学的に確認する
        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        matches_mask = mask.ravel().tolist()
        # インライア（正しいマッチ）の数をカウント
        inlier_count = sum(matches_mask)
        inlier_ratio = inlier_count / len(matches_mask) # インライアの割合

        if inlier_count > 15 and inlier_ratio > 0.5: # 50%以上のマッチがインライアならOK
            # print("十分なマッチがあり、信頼できる")
            # print("一致する特徴点が見つかりました！")
            # # 上位10件のマッチを描画（最も近いマッチ）
            # img_matches = cv2.drawMatches(img1, kp1, img2, kp2, matches[:10], None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            # # 結果を表示
            # cv2.imshow("特徴点マッチング", img_matches)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()
            return True
        else:
            # print("マッチ不十分または信頼性低い")
            return False
    else:
        return False

"""
from pdf2image import convert_from_path
# 指定したページを画像として保存する
def convert_selected_pages_to_images(input_pdf, pages_to_convert, output_folder):
    # 画像に変換する際のオプション（メモリ効率を上げるための設定）
    # 高解像度にする場合はdpiを変更する（例：300 dpiにすると高品質になる）
    dpi = 200  # 解像度を指定。300 dpiなどにすることで、より高品質な画像にできます。

    # 各ページごとに画像を生成
    for page_number in pages_to_convert:
        images = convert_from_path(input_pdf, first_page=page_number, last_page=page_number, dpi=dpi)
        
        # 画像を保存
        image = images[0]  # 一ページ分だけリストに入っているので、最初の要素を選択
        image.save(f"{output_folder}/page_{page_number}.png", "PNG")
        logger.debug(f"ページ {page_number} を画像に変換しました。")

# # 使用例
# input_pdf = "large_pdf.pdf"  # 変換したいPDFファイル名
# pages_to_convert = [5, 50, 100, 150, 200]  # 変換したいページ番号のリスト（1始まり）
# output_folder = "./output_images"  # 画像の保存先フォルダ

# convert_selected_pages_to_images(input_pdf, pages_to_convert, output_folder)
"""

def pdf_to_image(pdf_path, page_numbers, image_format="jpg", output_dir="."):
    """
    PDFファイルの指定したページを画像に変換する関数

    Args:
        pdf_path (str): PDFファイルのパス
        page_numbers (list): 変換するページのリスト（1始まり）
        image_format (str): 出力画像の形式（例: "png", "jpg", "jpeg"）
        output_dir (str): 出力ディレクトリ
    """
    images = []
    try:
        pdf_document = fitz.open(pdf_path)
    except Exception as e:
        logger.exception(f"Error opening PDF: {e}")
        return images
    basename_without_ext, ext_name = os.path.splitext(os.path.basename(pdf_path))
    for page_number in page_numbers:
        try:
            page = pdf_document.load_page(page_number - 1)  # ページ番号は0始まりに変換
            image = page.get_pixmap()
            file_name = f'{basename_without_ext}_{page_number:02}.jpg'
            image_path = os.path.join(output_dir, file_name).replace(os.sep,'/')

            image.save(image_path)
            images.append(image_path)
            logger.debug(f"Page {page_number} saved as {image_path}")
            # 最初に設定されたページのみ処理する
            break
        except Exception as e:
            logger.exception(f"Error processing page {page_number}: {e}")

    pdf_document.close()
    return images
