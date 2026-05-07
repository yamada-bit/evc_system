import os
import sys
import argparse 
import dataclasses
import json

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTContainer, LTTextBox
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
import pypdf
import math
from typing import List


@dataclasses.dataclass
class TextData:
    x1: int
    y1: int
    x2: int
    y2: int
    text: str
    
@dataclasses.dataclass        
class TextDatas:
    ocrtext_flg: int
    page_no: int
    area_no: int
    page_width: int
    page_height: int
    textdata_list: List[TextData]


def main():
    """
    main
    :return: Jsonfile
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('json')
    args = parser.parse_args()
    pdf_file = args.path
    json_file = args.json

    pdf_reader = pypdf.PdfReader(pdf_file)
    page_num = len(pdf_reader.pages)
    page_width = 0
    page_height = 0

    page_no = 1
    # for p in pdf_reader.pages:
    #     p_size = p.mediabox
    #     p_width = p_size.width
    #     p_height = p_size.height
    #     page_width = math.ceil(p_width / 72 * 200)
    #     page_height = math.ceil(p_height / 72 * 200)
    #     break

    textdatas = []
    with open(pdf_file, 'rb') as f:
        pdfPages = PDFPage.get_pages(f)
        # #文字読み取りのルール指定
        # laParams = LAParams(line_overlap = 0.5,
        #                     word_margin  = 0.1,
        #                     char_margin  = 2,
        #                     line_margin  = 0.5,
        #                     detect_vertical = True)
        laParams = LAParams(detect_vertical=True)
        resourceManager = PDFResourceManager()
        device = PDFPageAggregator(resourceManager, laparams=laParams)
        interpreter = PDFPageInterpreter(resourceManager, device)
        #ページごとに処理
        for i, page in enumerate(pdfPages):
            p = pdf_reader.pages[i]
            p_size = p.mediabox
            p_width = p_size.width
            p_height = p_size.height
            page_width = math.ceil(p_width / 72 * 200)
            page_height = math.ceil(p_height / 72 * 200)

            interpreter.process_page(page)
            layout = device.get_result()
            boxes = find_textboxes(layout)
            # dPoint / 72.0L * 96
            # dPoint / 72.0L * 200 DPI
            #テキストひとまとまりごとに処理
            data = []
            for box in boxes:
                x0 = int(box.x0 / 72 * 200)
                x1 = int(box.x1 / 72 * 200)
                y0 = page_height - int(box.y1 / 72 * 200)
                y1 = page_height - int(box.y0 / 72 * 200)
                text = box.get_text().strip()
                data.append(TextData(x0, y0, x1, y1, text))
            textdatas.append(TextDatas(1, i + 1, 1, page_width, page_height, data))
    jsonfile = sv_textdatas2jsonfile(textdatas, json_file)
    sys.stdout.write('test = ' + jsonfile)
    return jsonfile

def find_textboxes(layout):
    if isinstance(layout, LTTextBox):
        return [layout]
    elif isinstance(layout, LTContainer):
        boxes = []
        for child in layout:
            boxes.extend(find_textboxes(child))
        return boxes
    else:
        return []
    
def obj_dict(obj):
    return obj.__dict__
def sv_save_json(textdatas, json_file):
    jsonfile = json_file
    try:
        with open(jsonfile, 'w', encoding='utf-8') as f:
            json.dump(textdatas, f, default=obj_dict, ensure_ascii=False, indent=2)
    except Exception:
        return ''
    return jsonfile
def sv_textdatas2jsonfile(textdatas, jsonfile):
    json_str = ''
    try:
        json_str = json.dumps(textdatas, default=obj_dict, ensure_ascii=False, indent=2)
        with open(jsonfile, 'w', encoding='utf-8') as f:
            f.write(json_str)
        json_str = jsonfile
    except Exception:
        json_str = ''
    return json_str

if __name__ == '__main__':
    jsonfile = main()

