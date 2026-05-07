import os
import io
import logging

from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

# from reportlab.lib.pagesizes import A4
# from reportlab.lib.pagesizes import A3, landscape, portrait, letter
# from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from Evc_App.sv_create_image import sv_create_ocr_image
from Evc_App.sv_extract_text import sv_extract_text

logger = logging.getLogger(__name__)

# pypdf を使って元のPDFページを読み込み、reportlab で透明テキストを加え、最後に新しいPDFを作成します。
def add_text_to_pdf(response, org_path, texts):
    # 既存のPDFファイルを読み込む
    original_pdf_path = org_path    # 既存のPDFファイルパスを指定
    pdf_reader = PdfReader(original_pdf_path)
    # PDFに透明テキストを埋め込むためのPdfWriter
    pdf_writer = PdfWriter()

    font_name = 'HeiseiKakuGo-W5'   # reportlabにデフォルトで組み込まれているフォント
    pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    font_size = 12
    # pdfを描く場所を作成：位置を決める原点は左上にする(bottomup)
    # デフォルトの原点は左下
    # size = landscape(A4)
    # PDFに追加するテキストを生成するために、バッファを使ってreportlabで作成
    # packet = io.BytesIO()
    # pdf_canvas = canvas.Canvas(packet, pagesize=size)
    
    # 各ページにテキストを追加
    for page_num in range(len(pdf_reader.pages)):
        # 元のPDFページを取得
        page = pdf_reader.pages[page_num]
        if page_num < len(texts):
            try:
                width = round(page.mediabox.width)
                height = round(page.mediabox.height)
                page_size = (width, height)
                full_text = texts[page_num]
                lines = full_text.split('\n')
                # 新しいページを作成
                packet = io.BytesIO()
                pdf_canvas = canvas.Canvas(packet, pagesize=page_size)
                pdf_canvas.setFillColorRGB(1, 1, 1, alpha=0)  # 透明に設定
                pdf_canvas.setFont(font_name, font_size)
                y = height - 50
                for line in lines:
                    # 新しいページにテキストを追加
                    pdf_canvas.drawString(10, y, line)
                    y -= 10
                # PDFを保存
                pdf_canvas.save()

                # 透明テキストの内容を新しいページに追加
                packet.seek(0)
                new_pdf = PdfReader(packet)
                new_page = new_pdf.pages[0]
                # 元のページと透明テキストページをマージ
                page.merge_page(new_page)
            except Exception:
                logger.exception(f'text add exception {org_path} : {page_num + 1}')
        # ページをwriter(新しいPDF)に追加
        pdf_writer.add_page(page)

    # 新しいPDFをHTTPレスポンスとして返す    
    pdf_writer.write(response)
    return response

# pypdf を使って元のPDFページを読み込み、reportlab で透明テキストを座標を合わせて加え、新しいPDFを作成
def add_text_area_to_pdf(response, pdfpath, img_upload_dir):
    ocrimages = sv_create_ocr_image(pdfpath, img_upload_dir, -1)
    if not ocrimages:   # パスワード設定などにより読み込めない
        logger.error(f'ocrimages error {pdfpath=}')
        return ''
    areas_dict = {}
    # OCR機能を使って、テキスト抽出しTextDataデータに変換
    textdatas, detecttext_list, google_cnt = sv_extract_text(ocrimages, areas_dict, None)
    if not textdatas:
        logger.error(f'sv_extract_text error {pdfpath=}')
        return ''
    # 既存のPDFファイルを読み込む
    original_pdf_path = pdfpath    # 既存のPDFファイルパスを指定
    pdf_reader = PdfReader(original_pdf_path)
    # PDFに透明テキストを埋め込むためのPdfWriter
    pdf_writer = PdfWriter()

    font_name = 'HeiseiKakuGo-W5'   # reportlabにデフォルトで組み込まれているフォント
    pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    font_size = 12
    
    area_no = -1
    # 各ページにテキストを追加
    for page_num in range(len(pdf_reader.pages)):
        # 元のPDFページを取得
        page = pdf_reader.pages[page_num]
        try:
            width = round(page.mediabox.width)
            height = round(page.mediabox.height)
            page_size = (width, height)
            page_no = page_num + 1

            # 新しいページを作成
            packet = io.BytesIO()
            pdf_canvas = canvas.Canvas(packet, pagesize=page_size)
            pdf_canvas.setFillColorRGB(1, 1, 1, alpha=0)  # 透明に設定

            for pagedata in textdatas:
                if page_no == -1 or pagedata.page_no == page_no:
                    if area_no != -1 and pagedata.area_no != area_no:
                        continue
                    page_width = pagedata.page_width
                    page_height = pagedata.page_height
                    scx = width / page_width
                    scy = height / page_height
                    for textdata in pagedata.textdata_list:
                        x1 = textdata.x1
                        x2 = textdata.x2
                        y1 = textdata.y1
                        y2 = textdata.y2
                        x = x1 * scx
                        y = height - y1 * scy
                        # y = height - y2 * scy
                        h = y2 - y1
                        # フォントサイズを計算
                        # font_size = get_resized_font_size(pdf_canvas, word, w, h, font_name)    
                        font_size = round(h * scy)  # バウンディングボックスの高さをフォントサイズとして使用
                        pdf_canvas.setFont(font_name, font_size)
                        # テキストを対応する位置に描画
                        pdf_canvas.drawString(int(x), int(y), textdata.text)  # OCRされたテキストを元の位置に
            # PDFを保存
            pdf_canvas.save()

            # 透明テキストの内容を新しいページに追加
            packet.seek(0)
            new_pdf = PdfReader(packet)
            # 元のページと透明テキストページをマージ
            page.merge_page(new_pdf.pages[0])
            # 新しいページをwriterに追加
            pdf_writer.add_page(page)
        except Exception:
            pdf_writer.add_page(page)
            logger.exception(f'text add exception {pdfpath} : {page_no}')

    # 新しいPDFをHTTPレスポンスとして返す
    pdf_writer.write(response)
    return response

def append_text(annotations, page_pdf, pdf_writer, page_size):
    # 最初のオーバーラッピングテキストはページ全体のテキスト
    text = annotations[0].description
    # 各単語の位置情報（`boundingPoly`）を元に位置を設定
    word_positions = [(word.description, word.bounding_poly) for word in annotations[1:]]  # 最初のentryはページ全体のテキスト

    # 透明テキストをPDFに描画
    packet = io.BytesIO()
    # c = canvas.Canvas(packet, pagesize=letter)
    width = page_pdf.mediabox[2]  # 幅
    height = page_pdf.mediabox[3]  # 高さ
    page_pdfsize = (width, height)
    scx = width / page_size[0]
    scy = height / page_size[1]
    # デフォルトの原点は左下
    pdf_canvas = canvas.Canvas(packet, pagesize=page_pdfsize)

    # c.setFillColorRGB(1, 1, 1, alpha=0)  # 透明に設定
    pdf_canvas.setFillColorRGB(1, 0, 1, alpha=1.0)  # 透明に設定
    # font_name = 'MS Gothic'
    # # フォントファイルのパスを指定（MS Gothic）
    # font_path = r'C:\Windows\Fonts\msgothic.ttc'  # もしくはmsgothic.ttf
    # # MS Gothicフォントを登録
    # pdfmetrics.registerFont(TTFont(font_name, font_path))
    font_name = 'HeiseiKakuGo-W5'
    pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    # 各単語を指定の位置に描画
    for word, bounding_poly in word_positions:
        vertices = bounding_poly.vertices
        x11 = vertices[0].x
        y11 = vertices[0].y
        x22 = vertices[2].x
        y22 = vertices[2].y
        x1 = min(x11, x22)
        y1 = min(y11, y22)
        x2 = max(x11, x22)
        y2 = max(y11, y22)

        x = x1 * scx
        y = height - y1 * scy
        w = x2 - x1
        h = y2 - y1
        # フォントサイズを計算
        # font_size = get_resized_font_size(pdf_canvas, word, w, h, font_name)    
        font_size = round(h * scy)  # バウンディングボックスの高さをフォントサイズとして使用
        pdf_canvas.setFont(font_name, font_size)
        # pdf_canvas.setFont("Helvetica", 10)
        # テキストを対応する位置に描画
        pdf_canvas.drawString(int(x), int(y), word)  # OCRされたテキストを元の位置に

    pdf_canvas.save()

    # 新たに生成したPDFを追加
    packet.seek(0)
    new_pdf = PdfReader(packet)
    new_page = new_pdf.pages[0]
    # 元のページと透明テキストページをマージ
    page_pdf.merge_page(new_page)
    # 新しいPDFに追加
    pdf_writer.add_page(page_pdf)

def get_resized_font_size(c, text, width, height, font_name, min_font_size=6, max_font_size=10):
    # 行数の計算（改行で分ける）
    lines = text.split("\n")
    num_lines = len(lines)
    
    # 初期フォントサイズを最大値に設定
    test_font_size = max_font_size
    # 最大フォントサイズでの文字列の幅と高さを計算
    text_width = c.stringWidth(lines[0], font_name, test_font_size)
    text_height = test_font_size * num_lines  # 行数分の高さを計算
    
    # 幅が収まらない場合、フォントサイズを縮小
    while text_width > width and test_font_size > min_font_size:
        test_font_size -= 1
        text_width = c.stringWidth(lines[0], font_name, test_font_size)
        text_height = test_font_size * num_lines
    
    # 高さが収まらない場合、フォントサイズを縮小
    while text_height > height and test_font_size > min_font_size:
        test_font_size -= 1
        text_height = test_font_size * num_lines
    
    return test_font_size
