from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle


def create_pdf(response, year, month, pdf_list, getuji, emp_id, emp_name):
    title = 'title: 勤怠レポート'
    font_name = 'HeiseiKakuGo-W5'
    is_bottomup = True
    lineH = 4
    # A4横書きのpdfを作る
    size = landscape(A4)
    # pdfを描く場所を作成：位置を決める原点は左上にする(bottomup)
    # デフォルトの原点は左下
    pdf_canvas = canvas.Canvas(response, pagesize=size, bottomup=is_bottomup)
    #pdf_canvas.setPageSize((1200, 850))

    pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    # pdfのタイトルを設定
    pdf_canvas.setTitle(title)

    posY = 200
    # ヘッダー
    font_size = 10  # フォントサイズ
    pdf_canvas.setFont(font_name, font_size)
    pdf_canvas.drawString(120 * mm, posY * mm, str(year)+"年"+str(month)+"月度 日次勤怠")

    #font_size = 10
    #pdf_canvas.setFont(font_name, font_size)
    #pdf_canvas.drawString(15 * mm, 270 * mm, f"社員番号  氏名  雇用形態  部門名  拠点名 ")
    data = [[ "社員番号","氏名","雇用形態","部門名","拠点名"]]
    data.append([emp_id, emp_name, "","", ""])

    table = Table(
        data,
        colWidths=(25 * mm, 50 * mm, 50 * mm, 50 * mm, 50 * mm),
        rowHeights=lineH * mm,
    )
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 8),
        # 四角に罫線を引いて、0.5の太さで、色は黒
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        # 四角の内側に格子状の罫線を引いて、0.25の太さで、色は黒
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
        # セルの縦文字位置
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.darkblue),
        ('TEXTCOLOR', (2, 0), (2, 0), colors.darkblue),
        # 指定された範囲の背景色を変える
        ('BACKGROUND', (0, 0), (4, 0), colors.lightseagreen),
        ]))
    posY = 190
    # tableを描き出す位置を指定
    table.wrapOn(pdf_canvas, 10 * mm, posY * mm)
    table.drawOn(pdf_canvas, 10 * mm, posY * mm)

    #table = Table(data, colWidths=(50 * mm, 60 * mm), rowHeights=(7 * mm))
    #table.setStyle(TableStyle([
    #    ("FONT", (0, 0), (1, 2), font_name, 10),
    #    ("BOX", (0, 0), (2, 3), 1, colors.black),
    #    ("INNERGRID", (0, 0), (1, -1), 1, colors.black),
    #    ("VALIGN", (0, 0), (1, 2), "MIDDLE"),
    #    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    #    ]))
    #table.wrapOn(pdf_canvas, 20 * mm, 218 * mm,)
    #table.drawOn(pdf_canvas, 20 * mm, 218 * mm,)

    data = [["日付","勤務区分","出勤時刻","退勤時刻","総労働時間","休憩時間","残業時間","残業時間:36",
        "実働時間","所定内労働","法定内時間\n外労働","法定時間外\n労働","法定外休日\n労働","法定休日\n労働","深夜労働",
        "経費","備考"]]
    #タイトル行を2行にするため
    data.append(["", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " "])
    line_count = len(pdf_list)
    for idx in range(line_count):
        d = pdf_list[idx]
        t = d['times']
        data.append([d['date'], d['kbn_name'], d['corret_start'],  d['corret_end'],
                   t['work_time'], t['rest1'], t['over_time'], t['over_time36'], t['jitu_work'],
                   t['syoteinai_work'], t['hoteinai_jikangai'], t['hotei_jikangai'],
                   t['hoteigai_kyu'], t['hotei_kyu'], t['midnight_time'], d['expenses'], d['memo']])
    table = Table(
        data,
        colWidths=(15 * mm, 15 * mm, 15 * mm, 15 * mm, 17 * mm, 17 * mm,
                   17 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm,
                   17 * mm, 15 * mm, 15 * mm, 15 * mm, 25 * mm),
        rowHeights=(lineH*mm)
    )
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 8),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ('BACKGROUND', (0, 0), (-1, 1), colors.lightseagreen),
        ('SPAN', (0,0), (0,1)),
        ('SPAN', (1,0), (1,1)),
        ('SPAN', (2,0), (2,1)),
        ('SPAN', (3,0), (3,1)),
        ('SPAN', (4,0), (4,1)),
        ('SPAN', (5,0), (5,1)),
        ('SPAN', (6,0), (6,1)),
        ('SPAN', (7,0), (7,1)),
        ('SPAN', (8,0), (8,1)),
        ('SPAN', (9,0), (9,1)),
        ('SPAN', (10,0), (10,1)),
        ('SPAN', (11,0), (11,1)),
        ('SPAN', (12,0), (12,1)),
        ('SPAN', (13,0), (13,1)),
        ('SPAN', (14,0), (14,1)),
        ('SPAN', (15,0), (15,1)),
        ('SPAN', (16,0), (16,1)),
    ]))
    posY = posY - (line_count + 2) * lineH
    table.wrapOn(pdf_canvas, 10 * mm, posY * mm)
    table.drawOn(pdf_canvas, 10 * mm, posY * mm)

    font_size = 8  # フォントサイズ
    posY -= lineH
    pdf_canvas.setFont(font_name, font_size)
    pdf_canvas.drawString(10 * mm, posY * mm, "出勤状況")
    pdf_canvas.drawString(80 * mm, posY * mm, "勤務時間")
    pdf_canvas.drawString(150 * mm, posY * mm, "休日・休暇取得")
    pdf_canvas.drawString(220 * mm, posY * mm, "勤務区分")
    if getuji == None:
        data = [["所定日数",""],["出勤日数",""],
                ["法定外休日出勤日数",""],["法定休日出勤日数",""],
                ["欠勤日数",""],["遅刻日数",""],["早退日数",""]]
    else:
        data = [["所定日数",getuji['shotei_count']],["出勤日数",getuji['work_count']],
                ["法定外休日出勤日数",getuji['hoteigai_work_count']],["法定休日出勤日数",getuji['hotei_work_count']],
                ["欠勤日数",getuji['kekkin_count']],["遅刻日数",getuji['late_count']],["早退日数",getuji['early_count']]
                ]

    table = Table(
        data,
        colWidths=(40 * mm, 15 * mm),
        rowHeights=lineH * mm,
    )
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 8),
        ("BOX", (0, 0), (-1, 6), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, 6), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ('BACKGROUND', (0, 0), (0, 6), colors.lightseagreen),
    ]))
    table.wrapOn(pdf_canvas, 10 * mm, (posY - lineH * 7) * mm)
    table.drawOn(pdf_canvas, 10 * mm, (posY - lineH * 7) * mm)

    if getuji == None:
        data = [["総労働時間",""],["実労時間",""],
                ["所定時間",""],["所定内労働時間",""],
                ["残業時間",""],["法定内時間外労働時間",""],
                ["法定時間外労働時間",""],
                ["法定外休日労働時間",""],["法定休日労働時間",""],
                ["深夜労働時間",""],
                ["遅刻時間",""],["早退時間",""],
                ["所定不足時間",""],
                ]
    else:
        data = [["総労働時間",getuji['all_work_time']],["実労時間",getuji['jitu_work_time']],
                ["所定時間",getuji['shotei_time']],["所定内労働時間",getuji['shoteinai_work_time']],
                ["残業時間",getuji['overtime_time']],["法定内時間外労働時間",getuji['shotei_count']],
                ["法定時間外労働時間",getuji['hoteinai_over_time']],
                ["法定外休日労働時間",getuji['hoteigaikyu_time']],["法定休日労働時間",getuji['hoteikyu_time']],
                ["深夜労働時間",getuji['midnight_time']],
                ["遅刻時間",getuji['late_time']],["早退時間",getuji['early_time']],
                ["所定不足時間",getuji['shotei_less_time']],
                ]
    table = Table(
        data,
        colWidths=(40 * mm, 15 * mm),
        rowHeights=lineH * mm,
    )

    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 8),
        ("BOX", (0, 0), (-1, 12), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, 12), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ('BACKGROUND', (0, 0), (0, 12), colors.lightseagreen),
    ]))
    table.wrapOn(pdf_canvas, 80 * mm, (posY - lineH * 13) * mm)
    table.drawOn(pdf_canvas, 80 * mm, (posY - lineH * 13) * mm)

    if getuji == None:
        data = [["公休日数",""],["有給休暇日数",""],
                ["本日までの有給休暇残数",""],["夏季休暇日数",""],
                ["本日までの夏季休暇残数",""],["振替休日日数",""],
                ["本日までの振替休日残数",""],
                ["代休日数",""],["本日までの代休残数",""],["特別休暇日数",""],
            ]
    else:
        data = [["公休日数",getuji['holiday_count']],["有給休暇日数",getuji['yukyu_count']],
                ["本日までの有給休暇残数",getuji['yukyu_zan_count']],["夏季休暇日数",getuji['kakikyu_count']],
                ["本日までの夏季休暇残数",getuji['kakikyu_zan_count']],["振替休日日数",getuji['furikyu_count']],
                ["本日までの振替休日残数",getuji['furikyu_zan_count']],
                ["代休日数",getuji['daikyu_count']],["本日までの代休残数",getuji['daikyu_zan_count']],["特別休暇日数",getuji['tokukyu_count']],
            ]
    table = Table(
        data,
        colWidths=(40 * mm, 15 * mm),
        rowHeights=lineH * mm,
    )
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 8),
        ("BOX", (0, 0), (-1, 9), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, 9), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ('BACKGROUND', (0, 0), (0, 9), colors.lightseagreen),
    ]))
    table.wrapOn(pdf_canvas, 150 * mm, (posY - lineH * 10) * mm)
    table.drawOn(pdf_canvas, 150 * mm, (posY - lineH * 10) * mm)

    if getuji == None:
        data = [["有休",""],["夏休",""]]
    else:
        data = [["有休",getuji['month_yukyu_count']],["夏休",getuji['month_kakikyu_count']]]

    table = Table(
        data,
        colWidths=(40 * mm, 15 * mm),
        rowHeights=lineH * mm,
    )
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 8),
        ("BOX", (0, 0), (-1, 1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, 1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ('BACKGROUND', (0, 0), (0, 1), colors.lightseagreen),
    ]))
    table.wrapOn(pdf_canvas, 220 * mm, (posY - lineH * 2) * mm)
    table.drawOn(pdf_canvas, 220 * mm, (posY - lineH * 2) * mm)

    pdf_canvas.showPage()

    # pdfの書き出し
    pdf_canvas.save()

        ## 全ての作品情報を出力する。（検索結果は無関係）
        #id_array = list(Work.objects.all().values_list('pk', flat=True))
        #for work_count, work_id in enumerate(id_array):
        #    logger.debug(work_count)
        #    if Image.objects.filter(work_id=work_id).exists():  # 画像が紐づく場合
        #        # 作品に紐づく画像パスを取得
        #        image = Image.objects.values_list('image', flat=True).get(work_id=work_id)
        #    else:
        #        # No Imageパス
        #        image = settings.MEDIA_URL + NO_IMAGE
        #    # 作品情報
        #    workInfo = Work.objects.filter(pk=work_id).first()
        #    # 表の情報
        #    data = [
        #        ['タイトル', workInfo.title, 'メモ', workInfo.memo],
        #    ]
        #    table = Table(data, (15 * mm, 50 * mm, 12 * mm, 50 * mm), None, hAlign='CENTER')
        #    # TableStyleを使って、Tableの装飾をします。
        #    table.setStyle(TableStyle([
        #        # 表で使うフォントとそのサイズを設定
        #        ('FONT', (0, 0), (-1, -1), self.font_name, 9),
        #        # 四角に罫線を引いて、0.5の太さで、色は黒
        #        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        #        # 四角の内側に格子状の罫線を引いて、0.25の太さで、色は黒
        #        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
        #        # セルの縦文字位置
        #        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        #        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        #        ('TEXTCOLOR', (0, 0), (0, 0), colors.darkblue),
        #        ('TEXTCOLOR', (2, 0), (2, 0), colors.darkblue),
        #    ]))
        #    if work_count % 2 == 0:  # 偶数の場合
        #        # 画像の描画
        #        p.drawImage(ImageReader(image[1:]), 10, 530, width=580, height=280, mask='auto',
        #                    preserveAspectRatio=True)
        #        # tableを描き出す位置を指定
        #        table.wrapOn(p, 50 * mm, 50 * mm)
        #        table.drawOn(p, 43 * mm, 160 * mm)
        #    else:  # 奇数の場合
        #        # 画像の描画
        #        p.drawImage(ImageReader(image[1:]), 10, 130, width=580, height=280, mask='auto',
        #                    preserveAspectRatio=True)
        #        # tableを描き出す位置を指定
        #        table.wrapOn(p, 50 * mm, 50 * mm)
        #        table.drawOn(p, 43 * mm, 19 * mm)
        #        p.showPage()  # Canvasに書き込み（改ページ）
        #if len(id_array) % 2 != 0:  # 出力作品数が奇数の場合
        #    p.showPage()  # Canvasに書き込み

