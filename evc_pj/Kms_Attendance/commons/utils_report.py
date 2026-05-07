import datetime as dt
import calendar
import logging

from commons.mixins import MonthCalendarMixin

from Kms_Attendance.models import (M_emp,M_holiday,
                                    T_time_stamp,T_getuji_report,T_request,T_request_rest,
                                    T_daily_report,M_yukyu
                                    )

#from django.db import connection
from django.db.models import Q # Qオブジェクト

from Kms_Attendance.commons.utils import (get_kbn_name,get_date2time_str,get_times,
    add_weekday_to_date,is_holiday)

logger = logging.getLogger(__name__)

def get_int2datestr(date):
    try:
        str_date = str(date)
        return f'{str_date[:4]}/{str_date[4:6]}/{str_date[6:]}'
    except Exception as e:
        return ''

# 日報
def get_daily_report(obj_emp, year, month):
    report_list = []
    holidays = M_holiday.objects.values_list('HOLIDAY_YMD', flat=True).order_by('HOLIDAY_YMD')
    cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
    # その月の全ての日、月初や月末の週には前後の月の月末や月初が入ってくることがある
    month_days = cal.itermonthdates(year, month)

    for day in month_days:
        if day.month == month:  # 前後月の日付は除外
    # for week in days2:
    #     for day in week:
            target_date = year * 10000 + month * 100 + day.day
            obj_report = T_daily_report.objects. filter(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date).first()

            if obj_report != None:
                # gyomu_yotei = obj_report.GYOMU_YOTEI_TIME
                # gyomu_jisseki = obj_report.GYOMU_JISEKI_TIME
                # diff_time = obj_report.GYOMU_YOTEI_TIME
                report = obj_report.REPORT  # 日報
                com_LTD_CD = obj_report.COM_LTD_CD  # コメント所属CD
                com_EMP_ID = obj_report.COM_EMP_ID # コメント社員番号
                comment = obj_report.COMMENT   # コメント
            else:
                report=''
                # gyomu_yotei = ''
                # gyomu_jisseki = ''
                # diff_time = ''
                com_LTD_CD = ''
                com_EMP_ID = ''
                comment = ''

            obj_timestamp = T_time_stamp.objects. filter(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date).first()
            if obj_timestamp != None:
                times = get_times(obj_timestamp.CORRET_START_TIME, obj_timestamp.CORRET_END_TIME, obj_emp.WORK_PAT_CD)
                work_time = times['work_time']
            else:
                work_time = ''

            report =({
                'w' : MonthCalendarMixin.week_names[day.weekday()],
                'd' : str(day.day).zfill(2),
                'datew' : add_weekday_to_date(day),
                'is_saturday': day.weekday() == 5,
                'is_sunday': day.weekday() == 6,
                'is_holiday': is_holiday(day),
                'date' : target_date,
                'report' : report,
                # 'gyomu_yotei' : gyomu_yotei,
                # 'gyomu_jisseki' : gyomu_jisseki,
                # 'work_time' : work_time,
                # 'diff_time' : diff_time,
                'com_LTD_CD' : com_LTD_CD,
                'com_EMP_ID' : com_EMP_ID,
                'comment' : comment
                })
            report_list.append(report)
    return report_list
# 今日の出退勤レポート
def get_today_stamp(number, department, lodgment, employment, manager):
    obj_list = []
    dt_now = dt.datetime.now()
    today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    
    q_objects = Q(TARGET_DATE = today)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(EMP_ID=number)
    if department is not None and department != '':
        q_objects &= Q(LTD_CD=department)

    queryset = T_time_stamp.objects. filter(q_objects).order_by('LTD_CD', 'EMP_ID')

    for obj_timestamp in queryset:
        start = get_date2time_str(obj_timestamp.START_TIME)
        end = get_date2time_str(obj_timestamp.END_TIME)
        corret_start = get_date2time_str(obj_timestamp.CORRET_START_TIME)
        corret_end = get_date2time_str(obj_timestamp.CORRET_END_TIME)
        kbn = obj_timestamp.KBN
        work_stat = obj_timestamp.WORK_STAT
        stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請'
        kbn_name = get_kbn_name(kbn)

        try:
            obj_emp = M_emp.objects.get(
                LTD_CD = obj_timestamp.LTD_CD,
                EMP_ID = obj_timestamp.EMP_ID,)
        except M_emp.DoesNotExist:
            continue

        timestamp =({
            'user_id':obj_emp.user_id,
            'kbn_name' : kbn_name,
            'start' : start,
            'end' : end,
            'corret_start' : corret_start,
            'corret_end' : corret_end,
            'number' : obj_timestamp.EMP_ID,
            'name' : obj_emp.EMP_NAME,
            'department' : '',
            'lodgment' : '',
            'employment' : '',
            })
        obj_list.append(timestamp)
    return obj_list
# 月締状況レポート
def get_shime_status(year, month, number, department, lodgment, employment, manager):
    obj_list = []
    yearmonth = year * 100 + month
    
    q_objects = Q(TARGET_MONTH = yearmonth)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(EMP_ID=number)
    if department is not None and department != '':
        q_objects &= Q(LTD_CD=department)

    queryset = T_getuji_report.objects.filter(q_objects).order_by('LTD_CD', 'EMP_ID')

    for obj_getuji_report in queryset:
        try:
            obj_emp = M_emp.objects.get(
                LTD_CD = obj_getuji_report.LTD_CD,
                EMP_ID = obj_getuji_report.EMP_ID,)
        except M_emp.DoesNotExist:
            continue

        report =({
            'user_id':obj_emp.user_id,
            'number' : obj_emp.EMP_ID,
            'name' : obj_emp.EMP_NAME,
            'misinsei' : '0',
            'mati' : '0',
            'sumi' : '0',
            'nippou' : '0',
            })
        obj_list.append(report)
    return obj_list
# 月次レポート,PdfView
def get_getuji_report(year, month, number, department, lodgment, employment, manager):
    obj_list = []
    # dt_now = dt.datetime.now()
    yearmonth = year * 100 + month
    
    q_objects = Q(TARGET_MONTH = yearmonth)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(EMP_ID=number)
    if department is not None and department != '':
        q_objects &= Q(LTD_CD=department)

    queryset = T_getuji_report.objects.filter(q_objects).order_by('LTD_CD', 'EMP_ID')
    obj_list = list(queryset.values())
    # for rec in obj_list:
    #     obj_emp =M_emp.objects. filter(
    #             LTD_CD = rec['LTD_CD'],
    #             EMP_ID = rec['EMP_ID']).first()
    #    rec['name'] = obj_emp.EMP_NAME

    for rec in obj_list:
        try:
            user = M_emp.objects.get(
                LTD_CD = rec['LTD_CD'],
                EMP_ID = rec['EMP_ID'],)
            rec['name'] = user.EMP_NAME
            rec['user_id'] = user.user_id
        except M_emp.DoesNotExist:
            continue
    return obj_list

# 休日管理レポート
def get_holiday_report(year, number, department, lodgment, employment, manager):
    # obj_list = []
    # dt_now = dt.datetime.now()
    
    report_list = []

    queryset = M_emp.objects.exclude(DEL_FLG=1).order_by('LTD_CD', 'EMP_ID')

    for rec in queryset: 
        month1_list = []
        month2_list = []
        sum11 = 0
        sum12 = 0
        sum13 = 0
        sum14 = 0
        sum15 = 0
        sum16 = 0
        sum17 = 0
        for j in range(12):
            if j < 9:
                month = j + 4
                yearmonth = year * 100 + month
            else:
                month = j - 8
                yearmonth = (year + 1) * 100 + month
            q_object_getuji = Q(TARGET_MONTH = yearmonth)
            q_object_getuji &= Q(EMP_ID=rec.EMP_ID)
            q_object_getuji &= Q(LTD_CD=rec.LTD_CD)
            obj = T_getuji_report.objects.filter(q_object_getuji).order_by('LTD_CD', 'EMP_ID').first()
            month1 =({
                    'day11' : 0,
                    'day12' : 0,
                    'day13' : 0,
                    'day14' : 0,
                    'day15' : 0,
                    'day16' : 0,
                    'day17' : 0,
                    })
            if obj != None:
                month2 =({
                    'month': month,
                    'day11' : obj.KEKKIN_COUNT,
                    'day12' : obj.HOLIDAY_COUNT,
                    'day13' : obj.YUKYU_COUNT,
                    'day14' : obj.KAKIKYU_COUNT,
                    'day15' : obj.FURIKYU_COUNT,
                    'day16' : obj.DAIKYU_COUNT,
                    'day17' : obj.TOKUKYU_COUNT,
                    })
                sum11 += int(obj.KEKKIN_COUNT)
                sum12 += int(obj.HOLIDAY_COUNT)
                sum13 += int(obj.YUKYU_COUNT)
                sum14 += int(obj.KAKIKYU_COUNT)
                sum15 += int(obj.FURIKYU_COUNT)
                sum16 += int(obj.DAIKYU_COUNT)
                sum17 += int(obj.TOKUKYU_COUNT)
            else:
                month2 =({
                    'month': month,
                    'day11' : '',
                    'day12' : '',
                    'day13' : '',
                    'day14' : '',
                    'day15' : '',
                    'day16' : '',
                    'day17' : '',
                    })
            month1_list.append(month1)
            month2_list.append(month2)
        # 合計
        month1 =({
                    'day11' : 0,
                    'day12' : 0,
                    'day13' : 0,
                    'day14' : 0,
                    'day15' : 0,
                    'day16' : 0,
                    'day17' : 0,
                    })
        month2 =({
                    'month':0,
                    'day11' : sum11,
                    'day12' : sum12,
                    'day13' : sum13,
                    'day14' : sum14,
                    'day15' : sum15,
                    'day16' : sum16,
                    'day17' : sum17,
                    })
        month1_list.append(month1)
        month2_list.append(month2)

        report =({
            'user_id': rec.user_id,
            'name' : rec.EMP_NAME,
            'yotei' : month1_list,
            'jisseki' : month2_list,
         })
        report_list.append(report)
    return report_list

# 月次集計データ出力
def get_output_month(year, month, number, department, lodgment, employment, manager):
    yearmonth = year * 100 + month
    
    q_objects = Q(TARGET_MONTH = yearmonth)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(EMP_ID=number)
    if department is not None and department != '':
        q_objects &= Q(LTD_CD=department)

    queryset = M_emp.objects.filter().order_by('LTD_CD', 'EMP_ID')
    return queryset


# ['日付','ユーザID','社員番号','氏名','勤務区分','勤務区分名',
#  '出勤時刻','前日/翌日','退勤時刻','前日/翌日','休憩1開始','前日/翌日','休憩1終了','前日/翌日',
#  '休憩2開始','前日/翌日','休憩2終了','前日/翌日','経費','備考','所属長コメント','申請承認',
#  '打刻出勤','前日/翌日','打刻退勤','前日/翌日','打刻休憩1開始','前日/翌日','打刻休憩1終了','前日/翌日',
#  '打刻休憩2開始','前日/翌日','打刻休憩2終了','前日/翌日']

def get_csv_list(obj_emp, year, month, type):
    csv_list = []
    cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
    # その月の全ての日、月初や月末の週には前後の月の月末や月初が入ってくることがある
    month_days = cal.itermonthdates(year, month)

    # try:
    #     dt_now = dt.datetime.now()
    #     date = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    #     if month != dt_now.month:
    #         date = year * 10000 + month * 100 + calendar.monthrange(year, month)[1]
    #     obj_getuji = T_getuji_kintai.objects.get(
    #         LTD_CD = obj_emp.LTD_CD,
    #         EMP_ID = obj_emp.EMP_ID,
    #         TARGET_DATE = date,)
    # except T_getuji_kintai.DoesNotExist:
    #     return csv_list

    dt_now = dt.datetime.now()
    today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    holidays = M_holiday.objects.values_list('HOLIDAY_YMD', flat=True).order_by('HOLIDAY_YMD')

    for day in month_days:
        if day.month == month:  # 前後月の日付は除外
            target_date = year * 10000 + month * 100 + day.day
            if (day.weekday() >= 5 or target_date in holidays):
                holiday=True
            else:
                holiday=False
            obj_timestamp = T_time_stamp.objects. filter(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date).first()
            if obj_timestamp != None:
                start = get_date2time_str(obj_timestamp.START_TIME)
                end = get_date2time_str(obj_timestamp.END_TIME)
                corret_start = get_date2time_str(obj_timestamp.CORRET_START_TIME)
                corret_end = get_date2time_str(obj_timestamp.CORRET_END_TIME)
                kbn = obj_timestamp.KBN
                work_stat = obj_timestamp.WORK_STAT
                times = get_times(obj_timestamp.CORRET_START_TIME,obj_timestamp.CORRET_END_TIME,obj_emp.WORK_PAT_CD)
            else:
                start = ''
                end = ''
                corret_start = ''
                corret_end = ''
                kbn = 7 if holiday else 1
                work_stat = 0
                times =get_times(None,None,None)
            if kbn == 7 and target_date < today and (work_stat == 0 or work_stat == None):
                work_stat = 2
            stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請'

            kbn_name = get_kbn_name(kbn)
            try:
                obj_request = T_request.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    TARGET_DATE = target_date,)
            except T_request.DoesNotExist:
                obj_request = None

            if obj_request == None:
                expenses = 0
                memo = ''
                comment = ''
                work_stat = 0
            else:
                expenses = obj_request.EXPENSES
                memo = obj_request.MEMO
                comment = obj_request.AGREE_COMMENT
                work_stat = obj_request.WORK_STAT
            # stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請',

            queryset=T_request_rest.objects.filter(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date).order_by('REST_NO')
            rest_list = list(queryset.values())
            rest1_start = ''
            rest1_end = ''
            rest2_start = ''
            rest2_end = ''
            for i,rec in enumerate(rest_list):
                rec['REST_START_TIME'] = get_date2time_str(rec['REST_START_TIME'])
                rec['REST_END_TIME'] = get_date2time_str(rec['REST_END_TIME'])
                if i == 0:
                    rest1_start = rec['REST_START_TIME']
                    rest1_end = rec['REST_END_TIME']
                if i == 1:
                    rest2_start = rec['REST_START_TIME']
                    rest2_end = rec['REST_END_TIME']
            if type == 1:
                td = str(year) + '/' + str(month) + '/' + str(day.day)    # CSV
            else:
                td = str(day.day).zfill(2) + '  ' + MonthCalendarMixin.week_names[day.weekday()]   # PDF

            data =({
                'date' : td,
                'userid' : obj_emp.EMP_ID,
                'number': obj_emp.EMP_ID,
                'name' : obj_emp.EMP_NAME,
                'kbn' : kbn,
                'kbn_name' : kbn_name,
                'start' : start,
                'end' : end,
                'corret_start' : corret_start,
                'corret_end' : corret_end,
                'times' : times,
                'expenses' : expenses,
                'memo' : memo,
                'comment' : comment,
                'work_stat' : work_stat,
                'stat' : stat,
                'rest1_start' : rest_list[0]['REST_START_TIME'] if 0 < len(rest_list) else '',
                'rest1_end' : rest_list[0]['REST_END_TIME'] if 0 < len(rest_list) else '',
                'rest2_start' : rest_list[1]['REST_START_TIME'] if 1 < len(rest_list) else '',
                'rest2_end' : rest_list[1]['REST_START_TIME'] if 1 < len(rest_list) else '',
                'rest_list' : rest_list,
                })
            csv_list.append(data)
    return csv_list

def get_pdf_list(obj_emp, year, month):
    pdf_list = []
    dt_now = dt.datetime.now()
    today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    holidays = M_holiday.objects.values_list('HOLIDAY_YMD', flat=True).order_by('HOLIDAY_YMD')

    cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
    # その月の全ての日、月初や月末の週には前後の月の月末や月初が入ってくることがある
    month_days = cal.itermonthdates(year, month)

    for day in month_days:
        if day.month == month:  # 前後月の日付は除外
            target_date = year * 10000 + month * 100 + day.day
            if (day.weekday() >= 5 or target_date in holidays):
                holiday=True
            else:
                holiday=False
            obj_timestamp = T_time_stamp.objects. filter(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date).first()
            if obj_timestamp != None:
                start = get_date2time_str(obj_timestamp.START_TIME)
                end = get_date2time_str(obj_timestamp.END_TIME)
                corret_start = get_date2time_str(obj_timestamp.CORRET_START_TIME)
                corret_end = get_date2time_str(obj_timestamp.CORRET_END_TIME)
                kbn = obj_timestamp.KBN
                work_stat = obj_timestamp.WORK_STAT
                times = get_times(obj_timestamp.CORRET_START_TIME,obj_timestamp.CORRET_END_TIME,obj_emp.WORK_PAT_CD)
            else:
                start = ''
                end = ''
                corret_start = ''
                corret_end = ''
                kbn = 7 if holiday else 1
                work_stat = 0
                times =get_times(None,None,None)
            if kbn == 7 and target_date < today and (work_stat == 0 or work_stat == None):
                work_stat = 2
            stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請'

            kbn_name = get_kbn_name(kbn)
            try:
                obj_request = T_request.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    TARGET_DATE = target_date,)
            except T_request.DoesNotExist:
                obj_request = None

            if obj_request == None:
                expenses = 0
                memo = ''
                comment = ''
                work_stat = 0
            else:
                expenses = obj_request.EXPENSES
                memo = obj_request.MEMO
                comment = obj_request.AGREE_COMMENT
                work_stat = obj_request.WORK_STAT
            # stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請',

            queryset=T_request_rest.objects.filter(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date).order_by('REST_NO')
            rest_list = list(queryset.values())
            rest1_start = ''
            rest1_end = ''
            rest2_start = ''
            rest2_end = ''
            for i,rec in enumerate(rest_list):
                rec['REST_START_TIME'] = get_date2time_str(rec['REST_START_TIME'])
                rec['REST_END_TIME'] = get_date2time_str(rec['REST_END_TIME'])
                if i == 0:
                    rest1_start = rec['REST_START_TIME']
                    rest1_end = rec['REST_END_TIME']
                if i == 1:
                    rest2_start = rec['REST_START_TIME']
                    rest2_end = rec['REST_END_TIME']
            td = str(day.day).zfill(2) + '  ' + MonthCalendarMixin.week_names[day.weekday()]

            data =({
                'date' : td,
                'userid' : obj_emp.EMP_ID,
                'number': obj_emp.EMP_ID,
                'name' : obj_emp.EMP_NAME,
                'kbn' : kbn,
                'kbn_name' : kbn_name,
                'start' : start,
                'end' : end,
                'corret_start' : corret_start,
                'corret_end' : corret_end,
                'times' : times,
                'expenses' : expenses,
                'memo' : memo,
                'comment' : comment,
                'work_stat' : work_stat,
                'stat' : stat,
                'rest1_start' : rest_list[0]['REST_START_TIME'] if 0 < len(rest_list) else '',
                'rest1_end' : rest_list[0]['REST_END_TIME'] if 0 < len(rest_list) else '',
                'rest2_start' : rest_list[1]['REST_START_TIME'] if 1 < len(rest_list) else '',
                'rest2_end' : rest_list[1]['REST_START_TIME'] if 1 < len(rest_list) else '',
                'rest_list' : rest_list,
                })
            pdf_list.append(data)
    return pdf_list

# 休暇情報リスト
def get_paid_holiday_list(obj_emp, year, kbn):
    lists = []
    if not obj_emp:
        return lists
    q_objects = Q(LTD_CD=obj_emp.LTD_CD)   # 「Q object」複雑な処理を実装できるクエリ
    q_objects &= Q(EMP_ID=obj_emp.EMP_ID)
    q_objects &= Q(KBN=kbn)
    start_td = year * 10000 + 401
    end_td = (year + 1) * 10000 + 331
    q_objects &= Q(TARGET_DATE__range=(start_td, end_td))

    timestamps = T_time_stamp.objects.filter(q_objects).order_by('EMP_ID', 'TARGET_DATE')
    try:
        obj_yukyu = M_yukyu.objects.get(
            LTD_CD = obj_emp.LTD_CD,
            EMP_ID = obj_emp.EMP_ID,
            NENDO = year,)
    except M_yukyu.DoesNotExist:
        obj_yukyu = None
    if obj_yukyu:
        new_count = obj_yukyu.NEW_COUNT or 0    # 当年度付与数
        carry_over = obj_yukyu.CARRY_OVER or 0  # 前年繰越日数
        all_count = obj_yukyu.ALL_COUNT or 0    # 当年度総数
        used_count = obj_yukyu.USED_COUNT or 0  # 当年度取得数
    else:
        new_count = 0
        carry_over = 0
        all_count = 0
        used_count = 0
    expiration_count = carry_over + new_count - all_count
    if expiration_count < 0:
        expiration_count = 0

    start_date = get_int2datestr(start_td)
    data = ({
        'date' : start_date,        # 日付
        'carry_over' : carry_over,  # 繰越
        'new_count' : new_count,    # 付与
        'used_count' : '',          # 取得
        'expiration_count' : expiration_count,  # 失効
        'adjust_count' : all_count,     # 残数調整
        'remaining_count' : all_count,  # 残
        })  
    lists.append(data)
    count = 0
    for obj_timestamp in timestamps:
        name = obj_emp.EMP_NAME
        user_id = obj_emp.user_id
        kbn = obj_timestamp.KBN
        kbn_name = get_kbn_name(kbn)
        all_count -= 1
        count += 1
        data = ({
            'date' : obj_timestamp.TARGET_DATE,   # 日付
            'carry_over' : '',    # 繰越
            'new_count' : '',  # 付与
            'used_count' : 1,    # 取得
            'expiration_count' : '',  # 失効
            'adjust_count' : '',  # 残数調整
            'remaining_count' : all_count,   # 残
            })  
        lists.append(data)
    data = ({
        'date' : '計',          # 日付
        'carry_over' : '-',     # 繰越
        'new_count' : '-',      # 付与
        'used_count' : count,       # 取得
        'expiration_count' : '-',   # 失効
        'adjust_count' : '-',       # 残数調整
        'remaining_count' : all_count,  # 残
        })  
    lists.append(data)
    
    return lists
# 休暇情報
def get_yukyu(obj_emp, year, kbn):
    if not obj_emp:
        return None
    try:
        obj_yukyu = M_yukyu.objects.get(
            LTD_CD = obj_emp.LTD_CD,
            EMP_ID = obj_emp.EMP_ID,
            NENDO = year,)
    except M_yukyu.DoesNotExist:
        obj_yukyu = None
    return obj_yukyu

