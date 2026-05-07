import datetime as dt
import calendar
import jpholiday
import logging

from commons.mixins import MonthCalendarMixin
from Kms_Attendance.models import M_emp,M_kbn,M_holiday,M_work_pat,T_time_stamp

#from django.db import connection
from django.db.models import Q # Qオブジェクト

FORMAT_D = '%#d'
FORMAT_MD = '%#m/%#d'
FORMAT_HM = '%#H:%M'
WEEKRY_LIST = ['月', '火', '水', '木', '金', '土', '日']

logger = logging.getLogger(__name__)

# '%Y/%m/%d %H:%M:%S'
def get_str2datetime(str_datetime):
    try:
        dt_datetime = dt.datetime.strptime(str_datetime, '%Y/%m/%d %H:%M:%S')
    except Exception:
        dt_datetime = None
    return dt_datetime

# 休日チェック
def is_holiday(day):
    # jpholiday パッケージを使えば祝日判定が簡単にできます。
    is_holiday = jpholiday.is_holiday(day)
    return is_holiday
# def is_holiday(year, month, day):
#     try:
#         date = dt.datetime(year, month, day, 0, 0, 0)
#         if date.weekday() >= 5:
#             return True
#     except ValueError:
#         return False
#     date = year * 10000 + month * 100 + day
#     if M_holiday.objects.filter(HOLIDAY_YMD=date).exists():
#         return True
#     return False
# 日付と曜日を結合
def add_weekday_to_date(date_obj):
    try:
        date_str = str(date_obj.day).zfill(2)
        # 曜日リスト
        weekdays = WEEKRY_LIST
        # 曜日を取得
        weekday_str = weekdays[date_obj.weekday()]
        # 日付と曜日を結合して返す
        return f'{date_str}（{weekday_str}）'
    except Exception:
        logger.exception('Exception')
    return ''

def get_kbn_name(kbn):
    obj_kbn =M_kbn.objects. filter(
        ZOKUSEI_CD = 2,
        KBN = kbn).first()
    kbn_name = obj_kbn.KBN_NAME if obj_kbn != None else ''
    return kbn_name

# 月間日次勤怠リスト
def get_time_stamp(obj_emp, year, month):
    cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
    # その月の全ての日、月初や月末の週には前後の月の月末や月初が入ってくることがある
    month_days = cal.itermonthdates(year, month)

    timestamp_list = []
    dt_now = dt.datetime.now()
    today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
    holidays = M_holiday.objects.values_list('HOLIDAY_YMD', flat=True).order_by('HOLIDAY_YMD')
    for day in month_days:
        if day.month == month:  # 前後月の日付は除外
    # for week in days2:
    #     for day in week:
    #         if (day[0] != 0):
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
                times = get_times(obj_timestamp.CORRET_START_TIME, obj_timestamp.CORRET_END_TIME, obj_emp.WORK_PAT_CD)
            else:
                start = ''
                end = ''
                corret_start = ''
                corret_end = ''
                kbn = 7 if holiday else 1
                work_stat = 0
                times =get_times(None, None, None)
            if kbn == 7 and target_date < today and (work_stat == 0 or work_stat == None):
                work_stat = 2
            stat = '申請取消' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請'

            kbn_name = get_kbn_name(kbn)
            timestamp =({
                'w' : MonthCalendarMixin.week_names[day.weekday()],
                'd' : str(day.day).zfill(2),
                'datew' : add_weekday_to_date(day),
                'is_saturday': day.weekday() == 5,
                'is_sunday': day.weekday() == 6,
                'is_holiday': is_holiday(day),
                'date' : target_date,
                'kbn_name' : kbn_name,
                'kbn_name2' : '休日' if holiday else '出勤',
                'start' : start,
                'end' : end,
                'corret_start' : corret_start,
                'corret_end' : corret_end,
                'times' : times,
                'work_stat' : work_stat,
                'stat' : stat,
                })
            timestamp_list.append(timestamp)
    return timestamp_list
# 日次勤怠一括申請
def bulk_request_time_stamp(obj_emp, year, month):
    cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
    # その月の全ての日、月初や月末の週には前後の月の月末や月初が入ってくることがある
    month_days = cal.itermonthdates(year, month)

    for day in month_days:
        if day.month == month:  # 前後月の日付は除外
            target_date = year * 10000 + month * 100 + day.day
            try:
                obj_timestamp = T_time_stamp.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    TARGET_DATE = target_date)
                if obj_timestamp.WORK_STAT == 0:
                    obj_timestamp.WORK_STAT = 1 # 0:申請／1:申請中／2:承認済
                    obj_timestamp.save()
            except T_time_stamp.DoesNotExist:
                continue
    return True
def sv_get_name_choices():
    choices = []
    try:
        objs = M_emp.objects.exclude(DEL_FLG=1).order_by('EMP_ID')
        choices.append(('', '氏名'))
        if objs:
            for obj in objs:
                choices.append((obj.EMP_ID, obj.EMP_NAME))
    except Exception as e:
        logger.exception('M_emp exception : ')
    return choices
# 出退勤区分選択リストの設定
def sv_get_kbn_choices():
    choices = []
    try:
        kbns = M_kbn.objects.filter(ZOKUSEI_CD=2).order_by('KBN_ORDER')
        choices.append(('', '出退勤区分'))
        if kbns:
            for obj in kbns:
                choices.append((obj.KBN, obj.KBN_NAME))
    except Exception as e:
        logger.exception('M_kbn exception : ')
    return choices
# 勤怠承認List
def get_approvals(year, month, day, works_status, number, kbn):
    timestamp_list = []
    target_date = year * 10000 + month * 100 + day
    holidays = M_holiday.objects.values_list('HOLIDAY_YMD', flat=True).order_by('HOLIDAY_YMD')
    
    q_objects = Q(TARGET_DATE=target_date)   # 「Q object」複雑な処理を実装できるクエリ
    if number is not None and number !='' and number != 0:
        q_objects &= Q(EMP_ID=number)
    if works_status is not None and works_status != '':
        if works_status == '0':
            q_objects &= Q(WORK_STAT=0) | Q(WORK_STAT=None)
        else:
            q_objects &= Q(WORK_STAT=int(works_status))
    if kbn is not None and kbn != 0:
        q_objects &= Q(KBN=kbn)

    timestamps = T_time_stamp.objects.filter(q_objects).order_by('TARGET_DATE','EMP_ID')

    td = dt.datetime(year, month, day)
    w = MonthCalendarMixin.week_names[td.weekday()]

    if is_holiday(td):
        holiday = True
    else:
        holiday = False

    for obj_timestamp in timestamps:
        try:
            obj_emp = M_emp.objects.get(LTD_CD=obj_timestamp.LTD_CD, EMP_ID=obj_timestamp.EMP_ID)
            name = obj_emp.EMP_NAME
            user_id = obj_emp.user_id
            times = get_times(obj_timestamp.CORRET_START_TIME, obj_timestamp.CORRET_END_TIME, obj_emp.WORK_PAT_CD)
        except M_emp.DoesNotExist:
            continue
        start = get_date2time_str(obj_timestamp.START_TIME)
        end = get_date2time_str(obj_timestamp.END_TIME)
        corret_start = get_date2time_str(obj_timestamp.CORRET_START_TIME)
        corret_end = get_date2time_str(obj_timestamp.CORRET_END_TIME)
        kbn = obj_timestamp.KBN
        work_stat = obj_timestamp.WORK_STAT
        stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請待ち'
        kbn_name = get_kbn_name(kbn)
        timestamp =({
            'id' : user_id,
            'name' : name,
            'w' : w,
            'd' : str(month).zfill(2) + '/' + str(day).zfill(2),
            'date' : target_date,
            'kbn_name' : kbn_name,
            'kbn_name2' : '休日' if holiday else '出勤',
            'start' : start,
            'end' : end,
            'corret_start' : corret_start,
            'corret_end' : corret_end,
            'times' : times,
            'work_stat' : work_stat,
            'stat' : stat,
            })
        timestamp_list.append(timestamp)

    return timestamp_list

# 時間計算
def get_times(start, end, work_pat_cd):
    work1='0:00'
    rest1='0:00'
    over1='0:00'
    over36='0:00'
    jitu_work='0:00'
    syoteinai_work='0:00'
    hoteinai_jikangai='0:00'
    hotei_jikangai='0:00'
    hoteigai_kyu='0:00'
    hotei_kyu='0:00'
    midnight='0:00'

    if work_pat_cd != None:
        try:
            obj_work_pat = M_work_pat.objects.get(WORK_PAT_CD = work_pat_cd,)
        except M_work_pat.DoesNotExist:
             obj_work_pat = None
    else:
        obj_work_pat = None
    if start == None or start == '' or end == None or end == '' or obj_work_pat == None:
        pass
    else:
        try:
            td1 = dt.datetime.strptime(start, '%Y/%m/%d %H:%M:%S')
            td2 = dt.datetime.strptime(end, '%Y/%m/%d %H:%M:%S')
            td = td2 - td1
            sec = td.total_seconds()
        
            rd1 = get_time2date(obj_work_pat.REST1_START_TIME, td1.year, td1.month, td1.day)
            rd2 = get_time2date(obj_work_pat.REST1_END_TIME, td1.year, td1.month, td1.day)

            if td1 < rd1 and rd2 < td2:
                sec = sec - float(obj_work_pat.REST1_TIME) * 60 * 60
                rest1= get_hour2HMstr(obj_work_pat.REST1_TIME)
            work1 = get_sec2HMstr(sec)
        except Exception:
            pass
    times =({
            'work_time' : work1,    # 総労働時間
            'rest1' : rest1,        # 休憩時間
            'over_time' : over1,    # 残業時間
            'over_time36' : over36, # 残業時間:36
            'jitu_work':jitu_work,   #実働時間
            'syoteinai_work':syoteinai_work,        # 所定内労働
            'hoteinai_jikangai':hoteinai_jikangai,  # 法定内時間外労働
            'hotei_jikangai':hotei_jikangai,        # 法定時間外労働
            'hoteigai_kyu':hoteigai_kyu,            # 法定外休日労働
            'hotei_kyu':hotei_kyu,                  # 法定休日労働
            'midnight_time':midnight,               # 深夜労働
            })
    return times
# 総労働時間
def get_work1(start, end, work_pat_cd):
    try:
        obj_work_pat = M_work_pat.objects.get(WORK_PAT_CD = work_pat_cd,)
    except M_work_pat.DoesNotExist:
        obj_work_pat = None

    if start == None or start == '' or end == None or end == '' or obj_work_pat == None:
        return '0:00'
    try:
        td1 = dt.datetime.strptime(start, '%Y/%m/%d %H:%M:%S')
        td2 = dt.datetime.strptime(end, '%Y/%m/%d %H:%M:%S')
        td = td2 - td1
        sec = td.total_seconds()
        
        rd1 = get_time2date(obj_work_pat.REST1_START_TIME, td1.year, td1.month, td1.day)
        rd2 = get_time2date(obj_work_pat.REST1_END_TIME, td1.year, td1.month, td1.day)

        if td1 < rd1 and rd2 < td2:
            sec = sec - float(obj_work_pat.REST1_TIME) * 60 * 60
        return get_sec2HMstr(sec)
    except Exception:
        return '0:00'
def get_rest1(start, end, work_pat_cd):
    try:
        obj_work_pat = M_work_pat.objects.get(WORK_PAT_CD = work_pat_cd,)
    except M_work_pat.DoesNotExist:
        obj_work_pat = None

    if start == None or start == '' or end == None or end == '' or obj_work_pat == None:
        return '0:00'
    try:
        td1 = dt.datetime.strptime(start, '%Y/%m/%d %H:%M:%S')
        td2 = dt.datetime.strptime(end, '%Y/%m/%d %H:%M:%S')
        rd1 = get_time2date(obj_work_pat.REST1_START_TIME, td1.year, td1.month, td1.day)
        rd2 = get_time2date(obj_work_pat.REST1_END_TIME, td1.year, td1.month, td1.day)

        if td1 < rd1 and rd2 < td2:
            return get_hour2HMstr(obj_work_pat.REST1_TIME)
        else:
            return '0:00'
    except Exception:
        return '0:00'
# 秒->'%H:%M'
def get_sec2HMstr(sec):
    h = int(sec / 3600)
    m = int((sec - h * 3600) / 60)
    return str(h) + ':' + str(m).zfill(2)
# 時間->'%H:%M'
def get_hour2HMstr(hour):
    h = int(float(hour))
    m = int((float(hour) - h) * 60)
    return str(h) + ':' + str(m).zfill(2)

# %H:%M
def get_compare_time_str(tstr1, tstr2):
    if (tstr1 == None or tstr1 == ''):
        return 0
    if (tstr2 == None or tstr2 == ''):
        return 0
    try:
        h = int(tstr1.split(':')[0])
        m =  int(tstr1.split(':')[1])
        td1 = dt.time(h, m, 0)
    except Exception as e:
        return 0
    try:
        h = int(tstr2.split(':')[0])
        m =  int(tstr2.split(':')[1])
        td2 = dt.time(h, m, 0)
    except Exception as e:
        return 0

    return 1 if td1 < td2 else 2

# '%Y/%m/%d %H:%M:%S' --> '%H:%M'
def get_date2time_str(tstr):
    if (tstr == None or tstr == ''):
        return ''
    try:
        td = dt.datetime.strptime(tstr, '%Y/%m/%d %H:%M:%S')
    except ValueError as e:
        return ''
    return td.strftime('%H:%M')

# '%H:%M' --> '%Y/%m/%d %H:%M:%S'
def get_time2date_str(tstr, year, month, day, nextday=False):
    if (tstr == None or tstr == ''):
        return ''
    try:
        h = int(tstr.split(':')[0])
        m =  int(tstr.split(':')[1])
        td = dt.datetime(year, month, day, h, m, 0)
        if nextday:
            td = td + dt.timedelta(days=1)
    except ValueError as e:
        return ''
    except Exception as e:
        return ''

    return td.strftime('%Y/%m/%d %H:%M:%S')
# '%H:%M' --> 'date
def get_time2date(tstr, year, month, day, nextday=False):
    if (tstr == None or tstr == ''):
        h = 0
        m = 0
    else:
        try:
            h = int(tstr.split(':')[0])
            m =  int(tstr.split(':')[1])
        except ValueError as e:
            h = 0
            m = 0
        except Exception as e:
            h = 0
            m = 0
    td = dt.datetime(year, month, day, h, m, 0)
    if nextday:
        td = td + dt.timedelta(days=1)
    return td

def get_date2int(date):
    return  date.year * 10000 + date.month * 100 + date.day

def check_time(start_time, end_time):
    try:
        h = int(start_time.split(':')[0])
        m =  int(start_time.split(':')[1])
        start = dt.time(h, m, 0)
    except Exception as e:
        return str(e)
    if end_time == None or end_time == '':
        return ''
    try:
        h = int(end_time.split(':')[0])
        m =  int(end_time.split(':')[1])
        end = dt.time(h, m, 0)
    except Exception as e:
        return str(e)

    if start >= end:
        return '出社時刻は退社時刻より過去にする必要があります。'
    return ''

def is_nextday(start, end):
    if (start == None or start == '' or end == None or end == ''):
        return False
    try:
        td1 = get_date2int(dt.datetime.strptime(start, '%Y/%m/%d %H:%M:%S'))
        td2 = get_date2int(dt.datetime.strptime(end, '%Y/%m/%d %H:%M:%S'))
        return True if td1 < td2 else False
    except Exception as e:
        return False

