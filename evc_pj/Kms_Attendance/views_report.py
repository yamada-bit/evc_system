import logging
import datetime
import urllib
import csv

# from django.shortcuts import render

# Create your views here.
from django.urls import reverse_lazy,reverse
from django.http import HttpResponse,Http404
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import (ListView,
                                  DetailView,
                                  CreateView,
                                  DeleteView,
                                  UpdateView,
                                  TemplateView)
from django.contrib import messages

from .models import Company, Employee

from Kms_Attendance.models import (
    M_emp,T_getuji_report,T_daily_report,M_yukyu
)
from Kms_Attendance.forms import DailyReportEditForm,PaidHolidayEditForm

# 日次勤怠
from commons.mixins import MonthCalendarMixin
from commons.utils import ut_get_hash,ut_get_client_ip,ut_get_localdate

from Kms_Attendance.commons.utils_report import (get_int2datestr,
    get_today_stamp,get_shime_status,get_getuji_report,get_csv_list,get_pdf_list,
    get_paid_holiday_list,get_yukyu,
    get_daily_report,get_holiday_report,get_output_month)

from Kms_Attendance.commons.pdfmodule import create_pdf

logger = logging.getLogger(__name__)

# 休暇管理
class PaidHoliday(LoginRequiredMixin, MonthCalendarMixin, TemplateView):
    template_name = 'Kms_Attendance/paid_holiday.html'
    def get(self, request, *args, **kwargs):
        if 'cancel' in self.request.GET:   # 勤怠承認画面からの遷移の場合の戻るボタン
            redirect_url = self.request.session.pop('redirect_monthly', '/')
            if redirect_url:
                return redirect(redirect_url)
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '休暇管理'
        # ログインユーザ以外のユーザを選択遷移
        user_id = self.request.session.get('user_id', self.request.user.user_id)

        year = self.kwargs.get('year')
        KBN = 2#self.request.POST.get('paid_holiday')
        if not year:
            dt_today = datetime.date.today()
            year = dt_today.year
        try:
            obj_emp = M_emp.objects.get(user_id=user_id)
            username = obj_emp.EMP_NAME
            emp_id = obj_emp.EMP_ID
            joined_date = get_int2datestr(obj_emp.JOINED_DATE)
        except M_emp.DoesNotExist:
            obj_emp = None
            username = ''
            emp_id = ''
            joined_date = ''
        if obj_emp != None:
            try:
                obj_yukyu = M_yukyu.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    NENDO = year,)
            except M_yukyu.DoesNotExist:
                obj_yukyu = None
        else:
            obj_yukyu = None

        number = self.request.GET.get('number', '')
        name = self.request.GET.get('name', '')
        department = self.request.GET.get('department', '')
        lodgment = self.request.GET.get('lodgment', '')
        employment = self.request.GET.get('employment', '')
        manager = self.request.GET.get('manager', '')
        if obj_yukyu:
            new_count = obj_yukyu.NEW_COUNT
            carry_over = obj_yukyu.CARRY_OVER
            all_count = obj_yukyu.ALL_COUNT
            used_count = obj_yukyu.USED_COUNT
        else:
            new_count = 0
            carry_over = 0
            all_count = 0
            used_count = 0
        lists = get_paid_holiday_list(obj_emp, year, KBN)
        years = [i for i in range(year, year + 3)]
        context.update({
            'target_year': year,
            'years': years,
            'number': emp_id,
            'name': username,
            'joined_date': joined_date,
            'new_count': new_count,
            'carry_over': carry_over,
            'all_count':all_count,
            'user_count': used_count,
            'reports': lists
            })
        calendar_context = self.get_month_calendar(year, 1)
        context.update(calendar_context)

        return context
# 休暇管理-編集
class PaidHolidayEdit(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/paid_holiday_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)    # 継承元のメソッド
        context['process_title'] = '休暇管理'
        # user_id = self.kwargs.get('pk')
        # ログインユーザ以外のユーザを選択遷移
        user_id = self.request.session.get('user_id', self.request.user.user_id)
        year = self.kwargs.get('year')
        try:
            obj_emp = M_emp.objects.get(user_id=user_id)
            username = obj_emp.EMP_NAME
        except M_emp.DoesNotExist:
            obj_emp = None
            username = ''
        if obj_emp != None:
            try:
                obj_yukyu = M_yukyu.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    NENDO = year,)
            except M_yukyu.DoesNotExist:
                obj_yukyu = None
        else:
            obj_yukyu = None
        # if obj_yukyu == None:
        #     report = ''
        # else:
        #     report = obj_yukyu.REPORT
        # td = datetime.datetime(year, month, day)
        context.update({
            'year': year,
            'user_id': user_id,
            # 'today': td.strftime('%Y/%m/%d'),
            'username': username
            })
        KBN = 2
        obj_yukyu = get_yukyu(obj_emp, year, KBN)

        initial_dict = dict(
            EMP_ID = obj_yukyu.EMP_ID,
            NENDO = obj_yukyu.NENDO,
            NEW_COUNT = obj_yukyu.NEW_COUNT,
            CARRY_OVER = obj_yukyu.CARRY_OVER,
            ALL_COUNT = obj_yukyu.ALL_COUNT,
            USED_COUNT = obj_yukyu.USED_COUNT,
            )
        form = PaidHolidayEditForm(None, initial=initial_dict)
        context['form'] = form

        return context

    def post(self, request, *args, **kwargs):
        # user_id = self.kwargs.get('pk')
        # ログインユーザ以外のユーザを選択遷移
        user_id = self.request.session.get('user_id', self.request.user.user_id)
        year = self.kwargs.get('year')
        if 'cancel' in self.request.POST:   # 勤怠承認画面からの遷移の場合の戻るボタン
            # redirect_url = self.request.META.get('HTTP_REFERER')
            # if redirect_url:
            #     return redirect(redirect_url)
            # return HttpResponseRedirect(referer)
            redirect_url = reverse('Kms_Attendance:paid_holiday', kwargs={'year':year,'mode':1})
            return redirect(redirect_url)
        ltd_cd = request.POST.get('LTD_CD')
        emp_id = request.POST.get('EMP_ID')
        target_date = request.POST.get('NENDO')
        id = request.POST.get('id')
        if ltd_cd != None and ltd_cd != '' and emp_id != None and emp_id != '':
            obj_yukyu,created= M_yukyu.objects.get_or_create(
                    LTD_CD = ltd_cd,
                    EMP_ID = emp_id,
                    NENDO = year,
                    defaults = dict(
                        id = id,
                    ),
            )
            if created:
                obj_yukyu.INS_DATE = datetime.datetime.now()
                obj_yukyu.INS_ID = emp_id
                obj_yukyu.DEL_FLG = 0
            else:
                ins_date = ut_get_localdate(obj_yukyu.INS_DATE)
                obj_yukyu.INS_DATE = ins_date or datetime.datetime.now()
            obj_yukyu.UPDATE_DATE = datetime.datetime.now()
            obj_yukyu.UPDATE_ID = emp_id

            # obj_yukyu.GYOMU = request.POST('GYOMU')
            # obj_yukyu.REPORT = request.POST.get('REPORT')
            # obj_yukyu.GYOMU_YOTEI_TIME = request.POST('GYOMU_YOTEI_TIME')
            # obj_yukyu.GYOMU_JISEKI_TIME = request.POST('GYOMU_JISEKI_TIME')
            comment = '登録しました！'
            obj_yukyu.save()
            messages.info(self.request, comment)
        else:
            messages.error(self.request, '保存できませんでした！' )
        # redirect_url = reverse('Kms_Attendance:paid_holiday', kwargs={'year':year,'mode':1})
        # return redirect(redirect_url)
        return self.get(request, *args, **kwargs)

# レポート
class Report(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/report.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            obj_emp = M_emp.objects.get(user_id = self.request.user.user_id)  # プライマリーキー検索
            context['name'] = obj_emp.EMP_NAME
        except M_emp.DoesNotExist:      # getはデータなしの例外が発生する
            pass
        context['process_title'] = 'レポート'
        return context

# 今日の出退勤レポート
class ReportToday(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/report_today.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '今日の出退勤レポート'

        number = self.request.GET.get('number', '')
        name = self.request.GET.get('name', '')
        department = self.request.GET.get('department', '')
        lodgment = self.request.GET.get('lodgment', '')
        employment = self.request.GET.get('employment', '')
        manager = self.request.GET.get('manager', '')
        dt_now = datetime.datetime.now()

        lists = get_today_stamp(number, department, lodgment, employment, manager)
        context.update({
            'year': dt_now.year,
            'month': dt_now.month,
            'number': number,
            'name': name,
            'department': department,
            'lodgment': lodgment,
            'employment': employment,
            'manager': manager,
            'date': f'{dt_now.strftime("%Y/%m/%d %H:%M")}現在',
            'reports': lists
            })
        ids = []
        for obj in lists:
            uuid = ''
            user_id = obj.get('user_id', '')
            ids.append({'uuid':uuid, 'user_id':user_id})
        self.request.session['id_list'] = ids   # 対象データのユーザリスト
        
        return context
# 月締状況レポート
class ReportTukishime(LoginRequiredMixin, MonthCalendarMixin, TemplateView):
    template_name = 'Kms_Attendance/report_tukishime.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '月締状況レポート'
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        if not year or not month:
            dt_today = datetime.date.today()
            year = dt_today.year
            month = dt_today.month

        number = self.request.GET.get('number', '')
        name = self.request.GET.get('name', '')
        department = self.request.GET.get('department', '')
        lodgment = self.request.GET.get('lodgment', '')
        employment = self.request.GET.get('employment', '')
        manager = self.request.GET.get('manager', '')

        lists = get_shime_status(year, month, number, department, lodgment, employment, manager)
        ids = []
        for obj in lists:
            uuid = ''
            user_id = obj.get('user_id', '')
            ids.append({'uuid':uuid, 'user_id':user_id})
        self.request.session['id_list'] = ids   # 対象データのユーザリスト

        context.update({
            'year': year,
            'month': month,
            'number': number,
            'name': name,
            'department': department,
            'lodgment': lodgment,
            'employment': employment,
            'manager': manager,
            'reports': lists
            })
        calendar_context = self.get_month_calendar(year, month)
        context.update(calendar_context)

        return context
# 日報
class ReportDaily(LoginRequiredMixin, MonthCalendarMixin, TemplateView):
    template_name = 'Kms_Attendance/daily.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '日報'
        # pk = self.kwargs.get('pk')
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        if not year or not month:
            dt_today = datetime.date.today()
            year = dt_today.year
            month = dt_today.month
            username = ''

        number = ''
        department = ''
        lodgment = ''
        employment = ''
        manager = ''

        calendar_context = self.get_month_calendar(year, month)
        context.update(calendar_context)

        try:
            obj_emp = M_emp.objects.get(user_id = self.request.user.user_id)
            # 日報
            lists = get_daily_report(obj_emp, year, month)
            username = obj_emp.EMP_NAME
        except M_emp.DoesNotExist:
            lists=[]

        context.update({
            'year': year,
            'month': month,
            'number': number,
            'name': username,
            'department': department,
            'lodgment': lodgment,
            'employment': employment,
            'manager': manager,
            'reports': lists
            })

        return context
# 日報-日指定
class ReportDailyList(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/daily_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)    # 継承元のメソッド
        # user_id = self.kwargs.get('pk')
        user_id = self.request.user.user_id
        date =  self.request.GET.get('date', None)
        if date:
            td = datetime.datetime.strptime(date, '%Y/%m/%d')
            year = td.year
            month = td.month
            day = td.day
        else:
            year = self.kwargs.get('year')
            month = self.kwargs.get('month')
            day = self.kwargs.get('day')

        date = year * 10000 + month * 100 + day
        try:
            obj_emp = M_emp.objects.get(user_id=user_id)
        except M_emp.DoesNotExist:
            obj_emp = None
        if obj_emp != None:
            try:
                obj_report = T_daily_report.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    TARGET_DATE = date,)
            except T_daily_report.DoesNotExist:
                obj_report = None
        else:
            obj_report = None

        if obj_report == None:
            # gyomu_yotei = ''
            # gyomu_jisseki = ''
            # torihikisaki = ''
            # project = ''
            # gyomu = ''
            report=''
        else:
            report = obj_report.REPORT
            # gyomu_yotei = obj_report.GYOMU_YOTEI_TIME
            # gyomu_jisseki = obj_report.GYOMU_JISEKI_TIME
            # torihikisaki = obj_report.TORIHIKISAKI
            # project = obj_report.PROJECT
            # gyomu = obj_report.GYOMU
        td = datetime.datetime(year, month, day)
        context.update({
            'year': year,
            'month': month,
            'day': day,
            'user_id': user_id,
            'today': td.strftime('%Y/%m/%d')
            })
        return context

# 日報-編集
class ReportDailyEdit(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/daily_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)    # 継承元のメソッド
        context['process_title'] = '日報'
        # user_id = self.kwargs.get('pk')
        user_id = self.request.user.user_id
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        date = year * 10000 + month * 100 + day
        try:
            obj_emp = M_emp.objects.get(user_id=user_id)
            username = obj_emp.EMP_NAME
        except M_emp.DoesNotExist:
            obj_emp = None
            username = ''
        if obj_emp != None:
            try:
                obj_report = T_daily_report.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    TARGET_DATE = date,)
            except T_daily_report.DoesNotExist:
                obj_report = None
        else:
            obj_report = None
        if obj_report == None:
            # gyomu_yotei = ''
            # gyomu_jisseki = ''
            # torihikisaki = ''
            # project = ''
            # gyomu = ''
            report = ''
            com_ltd_cd = ''
            com_emp_id = ''
            comment = ''
        else:
            # gyomu_yotei = obj_report.GYOMU_YOTEI_TIME
            # gyomu_jisseki = obj_report.GYOMU_JISEKI_TIME
            # torihikisaki = obj_report.TORIHIKISAKI
            # project = obj_report.PROJECT
            # gyomu = obj_report.GYOMU
            report = obj_report.REPORT
            com_ltd_cd = obj_report.COM_LTD_CD
            com_emp_id = obj_report.COM_EMP_ID
            comment=obj_report.COMMENT
        td = datetime.datetime(year, month, day)
        context.update({
            'year': year,
            'month': month,
            'day': day,
            'user_id': user_id,
            'today': td.strftime('%Y/%m/%d'),
            'username': username
            })

        initial_dict = dict(
            LTD_CD = obj_emp.LTD_CD  if obj_emp != None else '',
            EMP_ID = obj_emp.EMP_ID  if obj_emp != None else '',
            TARGET_DATE = date,
            date_field =  td.strftime('%Y/%m/%d'),
            # TORIHIKISAKI=torihikisaki,
            # PROJECT = project,
            # GYOMU = gyomu,
            REPORT = report,
            # GYOMU_YOTEI_TIME=gyomu_yotei,
            # GYOMU_JISEKI_TIME=gyomu_jisseki,
            COM_LTD_CD = com_ltd_cd,
            COM_EMP_ID = com_emp_id,
            COMMENT = comment,
            )
        form = DailyReportEditForm(None, initial=initial_dict)
        context['form'] = form

        return context

    def post(self, request, **kwargs):
        # user_id = self.kwargs.get('pk')
        user_id = self.request.user.user_id
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')

        if 'cancel' in request.POST:
            redirect_url = reverse('Kms_Attendance:daily', kwargs={'year':year,'month':month,})
            return redirect(redirect_url)

        ltd_cd = request.POST.get('LTD_CD')
        emp_id = request.POST.get('EMP_ID')
        target_date = request.POST.get('TARGET_DATE')
        id = request.POST.get('id')
        if ltd_cd != None and ltd_cd != '' and emp_id != None and emp_id != '':
            obj_report,created= T_daily_report.objects.get_or_create(
                    LTD_CD = ltd_cd,
                    EMP_ID = emp_id,
                    TARGET_DATE = target_date,
                    defaults = dict(
                        id = id,
                    ),
            )
            if created:
                obj_report.INS_DATE = datetime.datetime.now()
                obj_report.INS_ID = emp_id
                obj_report.DEL_FLG = 0
            else:
                ins_date = ut_get_localdate(obj_report.INS_DATE)
                obj_report.INS_DATE = ins_date or datetime.datetime.now()
            obj_report.UPDATE_DATE = datetime.datetime.now()
            obj_report.UPDATE_ID = emp_id

            # obj_report.GYOMU = request.POST('GYOMU')
            obj_report.REPORT = request.POST.get('REPORT')
            # obj_report.GYOMU_YOTEI_TIME = request.POST('GYOMU_YOTEI_TIME')
            # obj_report.GYOMU_JISEKI_TIME = request.POST('GYOMU_JISEKI_TIME')
            obj_report.COM_LTD_CD = request.POST.get('COM_LTD_CD')
            obj_report.COM_EMP_ID = request.POST.get('COM_EMP_ID')
            obj_report.COMMENT = request.POST.get('COMMENT')
            comment = '登録しました！'
            obj_report.save()
            messages.info(self.request, comment)
        else:
            messages.error(self.request, '保存できませんでした！' )

        redirect_url = reverse('Kms_Attendance:daily', kwargs={'year':year,'month':month,})
        return redirect(redirect_url)

# 月次レポート
class ReportGetuji(LoginRequiredMixin, MonthCalendarMixin, ListView):
    model = T_getuji_report
    context_object_name = 'obj_reports'
    template_name = 'Kms_Attendance/report_getuji.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '月次レポート'
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        if not year or not month:
            dt_today = datetime.date.today()
            year = dt_today.year
            month = dt_today.month

        number = ''
        department = ''
        lodgment = ''
        employment = ''
        manager = ''
        if self.request.GET.get('number', None):
            number = self.request.GET.get('number', None)
        if self.request.GET.get('department', None):
            department = self.request.GET.get('department', None)
        if self.request.GET.get('lodgment', None):
            lodgment = self.request.GET.get('lodgment', None)
        if self.request.GET.get('employment', None):
            employment = self.request.GET.get('employment', None)
        if self.request.GET.get('manager', None):
            manager = self.request.GET.get('manager', None)

        lists = get_getuji_report(year, month, number, department, lodgment, employment, manager)
        ids = []
        for obj in lists:
            uuid = ''
            user_id = obj.get('user_id', '')
            ids.append({'uuid':uuid, 'user_id':user_id})
        self.request.session['id_list'] = ids   # 対象データのユーザリスト

        context.update({
            'year': year,
            'month': month,
            'number': number,
            'department': department,
            'lodgment': lodgment,
            'employment': employment,
            'manager': manager,
            'obj_reports': lists
            })

        calendar_context = self.get_month_calendar(year, month)
        context.update(calendar_context)

        return context

# 休日管理レポート
class ReportHoliday(LoginRequiredMixin, MonthCalendarMixin, TemplateView):
    template_name = 'Kms_Attendance/report_holiday.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '休日管理レポート'
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        if not year:
            dt_today = datetime.date.today()
            year = dt_today.year
        if not month:
            dt_today = datetime.date.today()
            month = dt_today.month

        number = ''
        department = ''
        lodgment = ''
        employment = ''
        manager = ''
        if self.request.GET.get('number', None):
            number = self.request.GET.get('number', None)
        if self.request.GET.get('department', None):
            department = self.request.GET.get('department', None)
        if self.request.GET.get('lodgment', None):
            lodgment = self.request.GET.get('lodgment', None)
        if self.request.GET.get('employment', None):
            employment = self.request.GET.get('employment', None)
        if self.request.GET.get('manager', None):
            manager = self.request.GET.get('manager', None)

        calendar_context = self.get_month_calendar(year, month)
        context.update(calendar_context)

        reports = get_holiday_report(year, number, department, lodgment, employment, manager)
        ids = []
        for obj in reports:
            uuid = ''
            user_id = obj.get('user_id', '')
            ids.append({'uuid':uuid, 'user_id':user_id})
        self.request.session['id_list'] = ids   # 対象データのユーザリスト

        context.update({
            'year': year,
            'number': number,
            'department': department,
            'lodgment': lodgment,
            'employment': employment,
            'manager': manager,
            'cur_year': str(year),
            'next_year': str(year + 1),
            'year1': str(year),
            'year2': str(year + 1),
            'year3': str(year + 2),
            'reports': reports
            })

        return context
#月次集計データ出力
class OutputMonth(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/output_month.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '月次集計データ出力'
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        if not year or not month:
            dt_today = datetime.date.today()
            year = dt_today.year
            month = dt_today.month

        number = ''
        name=''
        department = ''
        lodgment = ''
        employment = ''
        manager = ''
        if self.request.GET.get('number', None):
            number = self.request.GET.get('number', None)
        if self.request.GET.get('name', None):
            name = self.request.GET.get('name', None)
        if self.request.GET.get('department', None):
            department = self.request.GET.get('department', None)
        if self.request.GET.get('lodgment', None):
            lodgment = self.request.GET.get('lodgment', None)
        if self.request.GET.get('employment', None):
            employment = self.request.GET.get('employment', None)
        if self.request.GET.get('manager', None):
            manager = self.request.GET.get('manager', None)

        lists = get_output_month(year, month, number, department, lodgment, employment, manager)
        ids = []
        for obj in lists:
            uuid = ''
            user_id = obj.user_id
            ids.append({'uuid':uuid, 'user_id':user_id})
        self.request.session['id_list'] = ids   # 対象データのユーザリスト

        context.update({
            'year': year,
            'month': month,
            'number': number,
            'name': name,
            'department': department,
            'lodgment': lodgment,
            'employment': employment,
            'manager': manager,
            'date': f'{datetime.datetime.now().strftime("%Y/%m/%d %H:%M")}現在',
            'reports': lists
            })

        return context
# 日次勤怠データ出力
class OutputDay(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/output_day.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '日次勤怠データ出力'
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        if not year or not month:
            dt_today = datetime.date.today()
            year = dt_today.year
            month = dt_today.month

        number = ''
        name=''
        department = ''
        lodgment = ''
        employment = ''
        manager = ''
        if self.request.GET.get('number', None):
            number = self.request.GET.get('number', None)
        if self.request.GET.get('name', None):
            name = self.request.GET.get('name', None)
        if self.request.GET.get('department', None):
            department = self.request.GET.get('department', None)
        if self.request.GET.get('lodgment', None):
            lodgment = self.request.GET.get('lodgment', None)
        if self.request.GET.get('employment', None):
            employment = self.request.GET.get('employment', None)
        if self.request.GET.get('manager', None):
            manager = self.request.GET.get('manager', None)

        lists = get_output_month(year, month, number, department, lodgment, employment, manager)
        ids = []
        for obj in lists:
            uuid = ''
            user_id = obj.user_id
            ids.append({'uuid':uuid, 'user_id':user_id})
        self.request.session['id_list'] = ids   # 対象データのユーザリスト

        context.update({
            'year': year,
            'month': month,
            'number': number,
            'name': name,
            'department': department,
            'lodgment': lodgment,
            'employment': employment,
            'manager': manager,
            'date': f'{datetime.datetime.now().strftime("%Y/%m/%d %H:%M")}現在',
            'reports': lists
            })
        return context


# csv形式でダウンロード
def CsvExport(request, year, month):
    try:
        user_id = request.user.user_id
        # ログインユーザ以外のユーザを選択
        user_id = request.session.get('user_id', user_id)
        obj_emp = M_emp.objects.get(user_id=user_id)
        emp_id = obj_emp.EMP_ID
    except M_emp.DoesNotExist:
        raise Http404("Data does not exist")

    csv_list = get_csv_list(obj_emp, year, month, 1)

    response = HttpResponse(content_type='text/csv; charset=CP932')
    # response = HttpResponse(content_type='text/csv')    # BOM付きのUTF-8のCSVファイル

    filename = urllib.parse.quote((u'勤怠_' + str(year) + str(month).zfill(2) + emp_id + '.csv').encode("utf8"))
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'{}'.format(filename)
    writer = csv.writer(response)
    # sio = io.StringIO()         # BOM付きのUTF-8のCSVファイル
    # writer = csv.writer(sio)    # BOM付きのUTF-8のCSVファイル

    # ヘッダー出力
    header = ['日付','ユーザID','社員番号','氏名','勤務区分','勤務区分名',
              '出勤時刻','前日/翌日','退勤時刻','前日/翌日','休憩1開始','前日/翌日','休憩1終了','前日/翌日',
              '休憩2開始','前日/翌日','休憩2終了','前日/翌日','経費','備考','所属長コメント','申請承認',
              '打刻出勤','前日/翌日','打刻退勤','前日/翌日','打刻休憩1開始','前日/翌日','打刻休憩1終了','前日/翌日',
              '打刻休憩2開始','前日/翌日','打刻休憩2終了','前日/翌日']

    writer.writerow(header)

    # データ出力
    for data in csv_list:

        row = [data['date'],data['userid'],data['number'],data['name'],data['kbn'],data['kbn_name'],
              data['corret_start'],'前日/翌日',data['corret_end'],'前日/翌日',
              data['rest1_start'],'前日/翌日',data['rest1_end'],'前日/翌日',
              data['rest2_start'],'前日/翌日',data['rest2_end'],'前日/翌日',
              data['expenses'],data['memo'],data['comment'],data['stat'],
              data['start'],'前日/翌日',data['end'],'前日/翌日',
              '打刻休憩1開始','前日/翌日','打刻休憩1終了','前日/翌日',
              '打刻休憩2開始','前日/翌日','打刻休憩2終了','前日/翌日']
        writer.writerow(row)
    # response.write(sio.getvalue().encode('utf_8_sig'))    # BOM付きのUTF-8のCSVファイル
    return response

class PdfView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        if not year or not month:
            pk = ''
            dt_today = datetime.date.today()
            year = dt_today.year
            month = dt_today.month
            # raise Http404("Data does not exist")
        try:
            user_id = request.user.user_id
            # ログインユーザ以外のユーザを選択
            user_id = self.request.session.get('user_id', user_id)
            obj_emp = M_emp.objects.get(user_id=user_id)
            emp_id = obj_emp.EMP_ID
            emp_name = obj_emp.EMP_NAME
        except M_emp.DoesNotExist:
            raise Http404("Data does not exist")

        filename = urllib.parse.quote((u'勤怠_' + str(year) + str(month).zfill(2) + emp_id + '.pdf').encode("utf8"))

        # PDF出力
        response = HttpResponse(status=200, content_type='application/pdf')
        # response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)  # ダウンロードする場合
        response['Content-Disposition'] = 'filename="{}"'.format(filename)  # 画面に表示する場合

        pdf_list = get_csv_list(obj_emp, year, month, 2)
        lists = get_getuji_report(year, month, emp_id, None, None, None, None)
        if len(lists) == 1:
            getuji = lists[0]
        else:
            getuji = None
        create_pdf(response, year, month, pdf_list, getuji, emp_id, emp_name)

        return response

"""

def profile(request, id):
    if User.objects.filter(pk=id).exists():
        user = User.objects.get(pk=id)
        context = {
            'user': user,
        }
        return render(request, 'myapp/profile.html', context)
    else:
        raise Http404('No User matches the given query.')
  
"""
# 一覧画面
class CompanyList(ListView):
    # Companyテーブル連携
    model = Company
    # レコード情報をテンプレートに渡すオブジェクト
    context_object_name = 'company_list'
    # テンプレートファイル連携
    template_name = 'Kms_Attendance/company_list.html'

# 詳細画面
class CompanyDetail(DetailView):
    # Companyテーブル連携
    model = Company
    # レコード情報をテンプレートに渡すオブジェクト
    context_object_name = 'company_detail'
    # テンプレートファイル連携
    template_name = 'Kms_Attendance/company_detail.html'

# Create(会社)画面
class CompanyCreateView(CreateView):
    # Companyテーブル連携
    model = Company
    # 入力項目定義
    fields = ('name','industory','location')
    # テンプレートファイル連携
    template_name = 'Kms_Attendance/company_form.html'
    # 更新後のリダイレクト先
    # def get_success_url(self):
    #     return reverse('Kms_Attendance:detail', kwargs={'pk': self.object.pk})

# Create(従業員)画面
class CompanyCreateView2(CreateView):
    # Companyテーブル連携
    model = Employee
    # 入力項目定義
    fields = ('name','age','company')
    # テンプレートファイル連携
    template_name = 'Kms_Attendance/company_form.html'
    # 作成後のリダイレクト先
    success_url = reverse_lazy('Kms_Attendance:list')

# Upadate画面(会社情報)
class CompanyUpdateView(UpdateView):
    # 入力項目定義
    fields = ('name','industory','location')
    # Companyテーブル連携
    model = Company
    # テンプレートファイル連携
    template_name = 'Kms_Attendance/company_form.html'
    # 更新後のリダイレクト先
    # def get_success_url(self):
    #     return reverse('Kms_Attendance:detail', kwargs={'pk': self.object.pk})

# 更新画面(従業員情報)
class CompanyUpdateView2(UpdateView):
    # 入力項目定義
    fields = ('name','age')
    # Employeeテーブル連携
    model = Employee
    # テンプレートファイル連携
    template_name = 'Kms_Attendance/company_form.html'
    # 更新後のリダイレクト先
    success_url = reverse_lazy('Kms_Attendance:list')

# 削除画面
class CompanyDeleteView(DeleteView):
    # Companyテーブル連携
    model = Company
    # テンプレートファイル連携
    template_name = 'Kms_Attendance/company_delete.html'
    # 削除後のリダイレクト先
    success_url = reverse_lazy('Kms_Attendance:list')
