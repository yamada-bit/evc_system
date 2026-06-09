import calendar
import logging

#from django.db import connection
from django.db.models import Q  # Qオブジェクト
from django.utils import timezone

from commons.mixins import MonthCalendarMixin
from Kms_Attendance.commons.utils import (
    add_weekday_to_date,
    get_date2time_str,
    get_kbn_name,
    get_times,
    is_holiday,
)
from Kms_Attendance.models import (
    M_emp,
    M_holiday,
    M_yukyu,
    T_daily_report,
    T_getuji_report,
    T_request,
    T_request_rest,
    T_time_stamp,
)

logger = logging.getLogger(__name__)

def get_int2datestr(date):
    try:
        str_date = str(date)
        return f'{str_date[:4]}/{str_date[4:6]}/{str_date[6:]}'
    except Exception:
        return ''

# 日報
def get_daily_report(obj_emp, year, month):
    report_list = []
    holidays = M_holiday.objects.values_list('holiday_ymd', flat=True).order_by('holiday_ymd')
    cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
    # その月の全ての日、月初や月末の週には前後の月の月末や月初が入ってくることがある
    month_days = cal.itermonthdates(year, month)

    for day in month_days:
        if day.month == month:  # 前後月の日付は除外
    # for week in days2:
    #     for day in week:
            target_date = year * 10000 + month * 100 + day.day
            obj_report = T_daily_report.objects. filter(
                ltd_cd = obj_emp.ltd_cd,
                emp_id = obj_emp.emp_id,
                target_date = target_date).first()

            if obj_report != None:
                # gyomu_yotei = obj_report.GYOMU_YOTEI_TIME
                # gyomu_jisseki = obj_report.GYOMU_JISEKI_TIME
                # diff_time = obj_report.GYOMU_YOTEI_TIME
                report = obj_report.report  # 日報
                com_LTD_CD = obj_report.com_ltd_cd  # コメント所属CD
                com_EMP_ID = obj_report.com_emp_id # コメント社員番号
                comment = obj_report.comment   # コメント
            else:
                report=''
                # gyomu_yotei = ''
                # gyomu_jisseki = ''
                # diff_time = ''
                com_LTD_CD = ''
                com_EMP_ID = ''
                comment = ''

            obj_timestamp = T_time_stamp.objects. filter(
                ltd_cd = obj_emp.ltd_cd,
                emp_id = obj_emp.emp_id,
                target_date = target_date).first()
            if obj_timestamp != None:
                times = get_times(obj_timestamp.corret_start_time, obj_timestamp.corret_end_time, obj_emp.work_pat_cd)
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
    dt_now = timezone.localdate()
    today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day

    q_objects = Q(target_date = today)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(emp_id=number)
    if department is not None and department != '':
        q_objects &= Q(ltd_cd=department)

    queryset = T_time_stamp.objects. filter(q_objects).order_by('ltd_cd', 'emp_id')

    for obj_timestamp in queryset:
        start = get_date2time_str(obj_timestamp.start_time)
        end = get_date2time_str(obj_timestamp.end_time)
        corret_start = get_date2time_str(obj_timestamp.corret_start_time)
        corret_end = get_date2time_str(obj_timestamp.corret_end_time)
        kbn = obj_timestamp.kbn
        work_stat = obj_timestamp.work_stat
        stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請'
        kbn_name = get_kbn_name(kbn)

        try:
            obj_emp = M_emp.objects.get(
                ltd_cd = obj_timestamp.ltd_cd,
                emp_id = obj_timestamp.emp_id,)
        except M_emp.DoesNotExist:
            continue

        timestamp =({
            'user_id':obj_emp.user_id,
            'kbn_name' : kbn_name,
            'start' : start,
            'end' : end,
            'corret_start' : corret_start,
            'corret_end' : corret_end,
            'number' : obj_timestamp.emp_id,
            'name' : obj_emp.emp_name,
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

    q_objects = Q(target_month = yearmonth)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(emp_id=number)
    if department is not None and department != '':
        q_objects &= Q(ltd_cd=department)

    queryset = T_getuji_report.objects.filter(q_objects).order_by('ltd_cd', 'emp_id')

    for obj_getuji_report in queryset:
        try:
            obj_emp = M_emp.objects.get(
                ltd_cd = obj_getuji_report.ltd_cd,
                emp_id = obj_getuji_report.emp_id,)
        except M_emp.DoesNotExist:
            continue

        report =({
            'user_id':obj_emp.user_id,
            'number' : obj_emp.emp_id,
            'name' : obj_emp.emp_name,
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
    # dt_now = timezone.localtime()
    yearmonth = year * 100 + month

    q_objects = Q(target_month = yearmonth)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(emp_id=number)
    if department is not None and department != '':
        q_objects &= Q(ltd_cd=department)

    queryset = T_getuji_report.objects.filter(q_objects).order_by('ltd_cd', 'emp_id')
    obj_list = list(queryset.values())
    # for rec in obj_list:
    #     obj_emp =M_emp.objects. filter(
    #             ltd_cd = rec['ltd_cd'],
    #             emp_id = rec['emp_id']).first()
    #    rec['name'] = obj_emp.emp_name

    for rec in obj_list:
        try:
            user = M_emp.objects.get(
                ltd_cd = rec['ltd_cd'],
                emp_id = rec['emp_id'],)
            rec['name'] = user.emp_name
            rec['user_id'] = user.user_id
        except M_emp.DoesNotExist:
            continue
    return obj_list

# 休日管理レポート
def get_holiday_report(year, number, department, lodgment, employment, manager):
    # obj_list = []
    # dt_now = timezone.localtime()

    report_list = []

    queryset = M_emp.objects.exclude(del_flg=1).order_by('ltd_cd', 'emp_id')

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
            q_object_getuji = Q(target_month = yearmonth)
            q_object_getuji &= Q(emp_id=rec.emp_id)
            q_object_getuji &= Q(ltd_cd=rec.ltd_cd)
            obj = T_getuji_report.objects.filter(q_object_getuji).order_by('ltd_cd', 'emp_id').first()
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
                    'day11' : obj.kekkin_count,
                    'day12' : obj.holiday_count,
                    'day13' : obj.yukyu_count,
                    'day14' : obj.kakikyu_count,
                    'day15' : obj.furikyu_count,
                    'day16' : obj.daikyu_count,
                    'day17' : obj.tokukyu_count,
                    })
                sum11 += int(obj.kekkin_count)
                sum12 += int(obj.holiday_count)
                sum13 += int(obj.yukyu_count)
                sum14 += int(obj.kakikyu_count)
                sum15 += int(obj.furikyu_count)
                sum16 += int(obj.daikyu_count)
                sum17 += int(obj.tokukyu_count)
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
            'name' : rec.emp_name,
            'yotei' : month1_list,
            'jisseki' : month2_list,
         })
        report_list.append(report)
    return report_list

# 月次集計データ出力
def get_output_month(year, month, number, department, lodgment, employment, manager):
    yearmonth = year * 100 + month

    q_objects = Q(target_month = yearmonth)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(emp_id=number)
    if department is not None and department != '':
        q_objects &= Q(ltd_cd=department)

    queryset = M_emp.objects.filter().order_by('ltd_cd', 'emp_id')
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
    #     dt_now = timezone.localtime()
    #     date = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    #     if month != dt_now.month:
    #         date = year * 10000 + month * 100 + calendar.monthrange(year, month)[1]
    #     obj_getuji = T_getuji_kintai.objects.get(
    #         ltd_cd = obj_emp.ltd_cd,
    #         emp_id = obj_emp.emp_id,
    #         target_date = date,)
    # except T_getuji_kintai.DoesNotExist:
    #     return csv_list

    dt_now = timezone.localdate()
    today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    holidays = M_holiday.objects.values_list('holiday_ymd', flat=True).order_by('holiday_ymd')

    for day in month_days:
        if day.month == month:  # 前後月の日付は除外
            target_date = year * 10000 + month * 100 + day.day
            if (day.weekday() >= 5 or target_date in holidays):
                holiday=True
            else:
                holiday=False
            obj_timestamp = T_time_stamp.objects. filter(
                ltd_cd = obj_emp.ltd_cd,
                emp_id = obj_emp.emp_id,
                target_date = target_date).first()
            if obj_timestamp != None:
                start = get_date2time_str(obj_timestamp.start_time)
                end = get_date2time_str(obj_timestamp.end_time)
                corret_start = get_date2time_str(obj_timestamp.corret_start_time)
                corret_end = get_date2time_str(obj_timestamp.corret_end_time)
                kbn = obj_timestamp.kbn
                work_stat = obj_timestamp.work_stat
                times = get_times(obj_timestamp.corret_start_time,obj_timestamp.corret_end_time,obj_emp.work_pat_cd)
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
                    ltd_cd = obj_emp.ltd_cd,
                    emp_id = obj_emp.emp_id,
                    target_date = target_date,)
            except T_request.DoesNotExist:
                obj_request = None

            if obj_request == None:
                expenses = 0
                memo = ''
                comment = ''
                work_stat = 0
            else:
                expenses = obj_request.expenses
                memo = obj_request.memo
                comment = obj_request.agree_comment
                work_stat = obj_request.work_stat
            # stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請',

            queryset=T_request_rest.objects.filter(
                ltd_cd = obj_emp.ltd_cd,
                emp_id = obj_emp.emp_id,
                target_date = target_date).order_by('rest_no')
            rest_list = list(queryset.values())
            rest1_start = ''
            rest1_end = ''
            rest2_start = ''
            rest2_end = ''
            for i,rec in enumerate(rest_list):
                rec['rest_start_time'] = get_date2time_str(rec['rest_start_time'])
                rec['rest_end_time'] = get_date2time_str(rec['rest_end_time'])
                if i == 0:
                    rest1_start = rec['rest_start_time']
                    rest1_end = rec['rest_end_time']
                if i == 1:
                    rest2_start = rec['rest_start_time']
                    rest2_end = rec['rest_end_time']
            if type == 1:
                td = str(year) + '/' + str(month) + '/' + str(day.day)    # CSV
            else:
                td = str(day.day).zfill(2) + '  ' + MonthCalendarMixin.week_names[day.weekday()]   # PDF

            data =({
                'date' : td,
                'userid' : obj_emp.emp_id,
                'number': obj_emp.emp_id,
                'name' : obj_emp.emp_name,
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
                'rest1_start' : rest_list[0]['rest_start_time'] if 0 < len(rest_list) else '',
                'rest1_end' : rest_list[0]['rest_end_time'] if 0 < len(rest_list) else '',
                'rest2_start' : rest_list[1]['rest_start_time'] if 1 < len(rest_list) else '',
                'rest2_end' : rest_list[1]['rest_start_time'] if 1 < len(rest_list) else '',
                'rest_list' : rest_list,
                })
            csv_list.append(data)
    return csv_list

def get_pdf_list(obj_emp, year, month):
    pdf_list = []
    dt_now = timezone.localdate()
    today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    holidays = M_holiday.objects.values_list('holiday_ymd', flat=True).order_by('holiday_ymd')

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
                ltd_cd = obj_emp.ltd_cd,
                emp_id = obj_emp.emp_id,
                target_date = target_date).first()
            if obj_timestamp != None:
                start = get_date2time_str(obj_timestamp.start_time)
                end = get_date2time_str(obj_timestamp.end_time)
                corret_start = get_date2time_str(obj_timestamp.corret_start_time)
                corret_end = get_date2time_str(obj_timestamp.corret_end_time)
                kbn = obj_timestamp.kbn
                work_stat = obj_timestamp.work_stat
                times = get_times(obj_timestamp.corret_start_time,obj_timestamp.corret_end_time,obj_emp.work_pat_cd)
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
                    ltd_cd = obj_emp.ltd_cd,
                    emp_id = obj_emp.emp_id,
                    target_date = target_date,)
            except T_request.DoesNotExist:
                obj_request = None

            if obj_request == None:
                expenses = 0
                memo = ''
                comment = ''
                work_stat = 0
            else:
                expenses = obj_request.expenses
                memo = obj_request.memo
                comment = obj_request.agree_comment
                work_stat = obj_request.work_stat
            # stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請',

            queryset=T_request_rest.objects.filter(
                ltd_cd = obj_emp.ltd_cd,
                emp_id = obj_emp.emp_id,
                target_date = target_date).order_by('rest_no')
            rest_list = list(queryset.values())
            rest1_start = ''
            rest1_end = ''
            rest2_start = ''
            rest2_end = ''
            for i,rec in enumerate(rest_list):
                rec['rest_start_time'] = get_date2time_str(rec['rest_start_time'])
                rec['rest_end_time'] = get_date2time_str(rec['rest_end_time'])
                if i == 0:
                    rest1_start = rec['rest_start_time']
                    rest1_end = rec['rest_end_time']
                if i == 1:
                    rest2_start = rec['rest_start_time']
                    rest2_end = rec['rest_end_time']
            td = str(day.day).zfill(2) + '  ' + MonthCalendarMixin.week_names[day.weekday()]

            data =({
                'date' : td,
                'userid' : obj_emp.emp_id,
                'number': obj_emp.emp_id,
                'name' : obj_emp.emp_name,
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
                'rest1_start' : rest_list[0]['rest_start_time'] if 0 < len(rest_list) else '',
                'rest1_end' : rest_list[0]['rest_end_time'] if 0 < len(rest_list) else '',
                'rest2_start' : rest_list[1]['rest_start_time'] if 1 < len(rest_list) else '',
                'rest2_end' : rest_list[1]['rest_start_time'] if 1 < len(rest_list) else '',
                'rest_list' : rest_list,
                })
            pdf_list.append(data)
    return pdf_list

# 休暇情報リスト
def get_paid_holiday_list(obj_emp, year, kbn):
    lists = []
    if not obj_emp:
        return lists
    q_objects = Q(ltd_cd=obj_emp.ltd_cd)   # 「Q object」複雑な処理を実装できるクエリ
    q_objects &= Q(emp_id=obj_emp.emp_id)
    q_objects &= Q(kbn=kbn)
    start_td = year * 10000 + 401
    end_td = (year + 1) * 10000 + 331
    q_objects &= Q(TARGET_DATE__range=(start_td, end_td))

    timestamps = T_time_stamp.objects.filter(q_objects).order_by('emp_id', 'target_date')
    try:
        obj_yukyu = M_yukyu.objects.get(
            ltd_cd = obj_emp.ltd_cd,
            emp_id = obj_emp.emp_id,
            nendo = year,)
    except M_yukyu.DoesNotExist:
        obj_yukyu = None
    if obj_yukyu:
        new_count = obj_yukyu.new_count or 0    # 当年度付与数
        carry_over = obj_yukyu.carry_over or 0  # 前年繰越日数
        all_count = obj_yukyu.all_count or 0    # 当年度総数
        used_count = obj_yukyu.used_count or 0  # 当年度取得数
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
        name = obj_emp.emp_name
        user_id = obj_emp.user_id
        kbn = obj_timestamp.kbn
        kbn_name = get_kbn_name(kbn)
        all_count -= 1
        count += 1
        data = ({
            'date' : obj_timestamp.target_date,   # 日付
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
            ltd_cd = obj_emp.ltd_cd,
            emp_id = obj_emp.emp_id,
            nendo = year,)
    except M_yukyu.DoesNotExist:
        obj_yukyu = None
    return obj_yukyu

