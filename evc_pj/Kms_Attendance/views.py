import datetime
import logging

# import locale
# import urllib
# import csv
import uuid

# from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Q  # Qオブジェクト

# from django.http import HttpResponse,Http404
from django.shortcuts import redirect, render

# Create your views here.
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView

# 日次勤怠
from commons.mixins import MonthCalendarMixin
from commons.utils import (
    ut_get_client_ip,
    ut_get_hash,
    ut_get_localdate,
    ut_get_localtime,
    ut_get_localtoday,
    ut_get_timezone_now,
)
from Kms_Attendance.commons.utils import (
    bulk_request_time_stamp,
    check_time,
    get_date2int,
    get_date2time_str,
    get_kbn_name,
    get_str2datetime,
    get_time2date_str,
    get_time_stamp,
    get_times,
    is_holiday,
    is_nextday,
    sv_get_kbn_choices,
    sv_get_name_choices,
)
from Kms_Attendance.forms import (
    ApprovalForm,
    ClockForm,
    EditEmpForm,
    EvcLoginForm,
    RequestEditForm,
    TimeStampEditForm,
)

# from dateutil.relativedelta import relativedelta
from Kms_Attendance.models import (
    M_emp,
    T_getuji_report,
    T_request,
    T_request_holiday,
    T_request_rest,
    T_time_stamp,
)

logger = logging.getLogger(__name__)

# 出退勤ログイン画面
# EvcUserでログイン
# Djangoにはアカウント認証のための標準クラスが存在しているため、標準クラスを承継して認証機能を実装
class KLoginView(LoginView):
    template_name = 'Kms_Attendance/login.html'
    form_class = EvcLoginForm
    """
    LoginView  で定義されているフォーム
    form_class = AuthenticationForm
    """
    def get_success_url(self):
        # settings.pyでメインメニューに遷移するように
        # LOGIN_REDIRECT_URL = 'accounts:redirect_url'
        # を設定しているのでここで出退勤に遷移するよう変更
        return reverse_lazy('Kms_Attendance:index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_name'] = 'klogin'
        return context

    def form_valid(self, form):
        # セッションに入力データを格納する。
        # self.request.session['form_data'] = self.request.POST
        self.request.session.clear()    # セッションをクリア

        # ログイン情報のログ出力(ハッシュ値を使ってログ出力)
        user_id = form.cleaned_data.get('username')
        user_id_hash = ut_get_hash(user_id)
        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'出退勤ログインしました: {user_id_hash=}')
        return super().form_valid(form)
    def form_invalid(self, form):
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                       f'出退勤ログインに失敗しました {err}')
        return super().form_invalid(form)
    # def form_invalid(self, form):
    #     user_id = form.cleaned_data.get('username')
    #     if not check_email(user_id):
    #         messages.error(self.request, "メールアドレスが正しくありません")
    #     # return self.render_to_response(self.get_context_data(form=form))
    #     return super().form_invalid(form)

# Viewクラス get()、post()などHTTPメソッドに特化したビュー
# 打刻画面
class IndexView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            # EvcUserとリンクするuser_id
            obj_emp = M_emp.objects.get(user_id = self.request.user.user_id)
        except M_emp.DoesNotExist:  # getはデータなしの例外が発生する
            # レコードがなければ新規画面へ
            return redirect('Kms_Attendance:add_emp')

        dt_now = ut_get_localtoday()
        today = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
        # 打刻レコード取得（ボタンの無効設定のため)
        try:
            obj_timestamp = T_time_stamp.objects.get(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = today)
            if obj_timestamp.START_TIME == None:
                in_out = 0  # 打刻なし
            else:
                in_out = 1 if obj_timestamp.END_TIME == None else 2 # 1:出勤打刻済　2:退勤打刻済
            initial_dict = dict(name_field=obj_emp.EMP_NAME)
            form = ClockForm(initial=initial_dict, instance=obj_timestamp)
        except T_time_stamp.DoesNotExist:  # getはデータなしの例外が発生する
            in_out = 0
            # uuid4 ランダムな UUID を生成する。(128ビットの乱数を生成)
            # id = uuid.uuid4()
            initial_dict = dict(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                name_field = obj_emp.EMP_NAME,
                TARGET_DATE = today)
            form = ClockForm(initial=initial_dict)

        # テンプレートコンテキスト作成
        context = {
            'form': form,
            'name' : obj_emp.EMP_NAME,
            'in_out': in_out,
        }
        return render(request, 'Kms_Attendance/index.html', context)

# 打刻実行結果画面
class ResultView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            obj_timestamp = T_time_stamp.objects.get(pk=self.request.POST.get('id'))
            form = ClockForm(self.request.POST, instance=obj_timestamp)
            # instanceにobjを渡すと更新/update
            # instanceなしだと新規作成となりform.is_valid()で、unique制約により「重複している」となる
        except T_time_stamp.DoesNotExist:       # データなしの例外が発生
            form = ClockForm(self.request.POST)      # 新規作成/create
        if form.is_valid():
            # cleaned_dataには適切なデータとして確認されたデータ
            # POSTで送信されるデータは、self.request.POSTで受け取ることができる
            id = self.request.POST.get('id') # form.cleaned_data['id']
            ltd_cd = self.request.POST.get('LTD_CD')
            emp_id = self.request.POST.get('EMP_ID')
            emp_name = self.request.POST.get('name_field')
            target_date = self.request.POST.get('TARGET_DATE')
            str_time = self.request.POST.get('showTime2')
            now2 = get_str2datetime(str_time) or ut_get_localtime()
            month = now2.month
            day = now2.day
            hour = now2.hour
            minute = now2.minute
            try:
                obj_timestamp,created = T_time_stamp.objects.get_or_create(
                    LTD_CD = ltd_cd,
                    EMP_ID = emp_id,
                    TARGET_DATE = target_date,
                    defaults = dict(
                        id = id,
                        KBN = 1,    # 出勤
                    ),
                )
                if created:
                    obj_timestamp.INS_DATE = ut_get_timezone_now()
                    obj_timestamp.INS_ID = self.request.user.user_id  # ログイン中のユーザ
                    obj_timestamp.DEL_FLG = 0
                    obj_timestamp.WORK_STAT = 0
                else:
                    ins_date = ut_get_localdate(obj_timestamp.INS_DATE)
                    obj_timestamp.INS_DATE = ins_date or ut_get_timezone_now()

                obj_timestamp.UPDATE_DATE = ut_get_timezone_now()
                obj_timestamp.UPDATE_ID = self.request.user.user_id
                # obj_timestamp.KBN = 1
                if 'start' in self.request.POST:
                    comment = f'{month}月{day}日{hour}時{minute}分 出勤確認しました。'
                    obj_timestamp.START_TIME = str_time
                    obj_timestamp.CORRET_START_TIME = str_time
                else:
                    comment = f'{month}月{day}日{hour}時{minute}分 退勤確認しました。'
                    obj_timestamp.END_TIME = str_time
                    obj_timestamp.CORRET_END_TIME = str_time
                obj_timestamp.save()
            except Exception:
                comment = '登録できませんでした！'
                logger.exception('exception')
        else:
            emp_name = ''
            comment = '登録できませんでした！'

        context = {
            'name' : emp_name,
            'comment': comment,
        }
        return render(request, 'Kms_Attendance/result.html', context)

# 社員マスタ新規登録画面
class AddEmp(LoginRequiredMixin, CreateView):
    model = M_emp   # 社員マスタテーブル連携
    template_name = 'Kms_Attendance/emp_form.html'  # テンプレートファイル連携
    form_class = EditEmpForm    # フォームクラス
    success_url = '/kintai/index'   # 作成後のリダイレクト先
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) # 継承元のメソッド
        context['process_title'] = '社員マスタ新規登録'
        if self.request.POST:
            # context['form'] = self.form
            context['form'] = EditEmpForm(self.request.POST)
        else:
            # テンプレートに変数を渡す
            context['form'] = EditEmpForm(initial={'user_id':self.request.user.user_id})
        return context
    def form_valid(self, form):
        object = form.save(commit=False)    # データベースに保存する前のモデルインスタンスを取得
        object.save()
        messages.success(self.request, 'データを登録しました。')
        return super().form_valid(form)
    def form_invalid(self, form):
        self.form = form
        # err = form.errors.as_text()
        # messages.error(self.request, '保存に失敗しました')
        # logger.error(f'{ut_get_client_ip(self.request)}'
        #                f'保存に失敗しました {err}')
        return super().form_invalid(form)

# 社員マスタ編集画面
class EditEmp(LoginRequiredMixin, FormView):
    model = M_emp
    template_name = 'Kms_Attendance/emp_form.html'
    form_class = EditEmpForm
    success_url = '/kintai/edit_emp'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        try:
            obj_emp = M_emp.objects.get(user_id = self.request.user.user_id)
            kwargs['instance'] = obj_emp  # フォームのインスタンスとしてオブジェクトを渡す
        except Exception:
            logger.exception('M_emp exception')
            # レコードがなければ新規画面へ
            return redirect('Kms_Attendance:add_emp')
        return kwargs
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '社員マスタ編集'
    #     obj = kwargs.get('object')
    #     if obj:
    #         context['form'] = EditEmpForm(instance=obj)
    #     else:
    #         if 'form' not in kwargs:
    #             # テンプレートに変数を渡す
    #             context['form'] = EditEmpForm(initial={'user_id':self.request.user.user_id})
        return context
    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'データを登録しました。')
        return super().form_valid(form)
    def form_invalid(self, form):
        # err = form.errors.as_text()
        # messages.error(self.request, '保存に失敗しました')
        # logger.error(f'{ut_get_client_ip(self.request)}'
        #                f'保存に失敗しました {err}')
        return super().form_invalid(form)

# 日次勤怠画面
class MonthCalendar(LoginRequiredMixin, MonthCalendarMixin, TemplateView):
    template_name = 'Kms_Attendance/monthly.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '日次勤怠'
        # URLのパラメータを使う
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        # day = self.kwargs.get('day')
        mode = self.kwargs.get('mode', 1)
        # ログインユーザ以外のユーザを選択遷移
        user_id = self.request.session.pop('user_id', self.request.user.user_id)
        if not year or not month:
            dt_today = ut_get_localtoday()
            year = dt_today.year
            month = dt_today.month
            # day = dt_today.day
            # user_id = self.request.user.user_id
        counter = self.kwargs.get('counter')    # user_idを取得するためforloop.counterをパラメータに含める
        if counter:
            lists = self.request.session.pop('id_list', None)
            if lists:
                if counter <= len(lists):
                    item = lists[counter - 1]
                    user_id = item.get('user_id')   # ログインユーザ以外のユーザを選択

        self.request.session['user_id'] = user_id

        # 月間カレンダー情報を取得
        calendar_context = self.get_month_calendar(year, month)    # MonthCalendarMixin
        try:
            obj_emp = M_emp.objects.get(user_id = user_id)
            # 月間日次勤怠リスト
            timestamp_list = get_time_stamp(obj_emp, year, month)
            name = obj_emp.EMP_NAME
        except M_emp.DoesNotExist:
            obj_emp = None
            timestamp_list = []
            name = ''
        calendar_context.update({'timestamp':timestamp_list})
        if obj_emp:
            try:
                target_month = year * 100 + month
                # 月次レポートテーブル
                obj_getuji = T_getuji_report.objects.get(
                    LTD_CD = obj_emp.LTD_CD,
                    EMP_ID = obj_emp.EMP_ID,
                    TARGET_MONTH = target_month)
                calendar_context.update({'obj_getuji':obj_getuji})
            except T_getuji_report.DoesNotExist:
                pass
        # dt_now = ut_get_localtoday()
        # date = dt_now.year * 10000 + dt_now.month * 100 + dt_now.day
        # if month_current.month != dt_now.month:
        #     td = self.get_last_date(month_current)
        #     date = td.year * 10000 + td.month * 100 + td.day
        # try:
        #     obj_getuji = T_getuji_kintai.objects.get(
        #         LTD_CD = obj_emp.LTD_CD,
        #         EMP_ID = obj_emp.EMP_ID,
        #         TARGET_DATE = date)
        # except T_getuji_kintai.DoesNotExist:
        #     obj_getuji = None
        context.update(calendar_context)
        context['name'] = name
        context['mode'] = mode
        self.request.session['redirect_monthly'] = self.request.build_absolute_uri()

        return context

    def post(self, request, *args, **kwargs):
        if 'cancel' in self.request.POST:   # 勤怠承認画面からの遷移の場合の戻るボタン
            year = self.kwargs.get('year')
            month = self.kwargs.get('month')
            day = self.kwargs.get('day')
            mode = self.kwargs.get('mode')
            # messages.info(self.request, 'キャンセル！')
            if mode == 4:   # 今日の出退勤レポート日次勤怠画面
                redirect_url = reverse('Kms_Attendance:report_today')
                return redirect(redirect_url)
            elif mode == 5:
                redirect_url = reverse('Kms_Attendance:report_tukishime', kwargs={'year':year,'month':month})
                return redirect(redirect_url)
            elif mode == 6:
                redirect_url = reverse('Kms_Attendance:report_getuji', kwargs={'year':year,'month':month})
                return redirect(redirect_url)
            elif mode == 8:
                redirect_url = reverse('Kms_Attendance:report_holiday', kwargs={'year':year})
                return redirect(redirect_url)
            elif mode == 9:
                redirect_url = reverse('Kms_Attendance:output_month')
                return redirect(redirect_url)
            elif mode == 10:
                redirect_url = reverse('Kms_Attendance:output_day')
                return redirect(redirect_url)
            if 'approval_date' in self.request.session:
                dt = self.request.session.pop('approval_date')
                if dt:
                    td = datetime.datetime.strptime(dt, "%Y/%m/%d")
                    day = td.day
                    redirect_url = reverse('Kms_Attendance:approval', kwargs={'year':year,'month':month,'day':day})
                    return redirect(redirect_url)
        elif 'bulk_request' in self.request.POST:    # 日時勤怠画面からの遷移の場合の一括申請ボタン
            date = self.request.POST.get('current_month')
            # ログインユーザ以外のユーザを選択
            user_id = self.request.session.pop('user_id', self.request.user.user_id)
            if date:
                try:
                    td = datetime.datetime.strptime(date, '%Y年%m月%d日')
                    obj_emp = M_emp.objects.get(user_id=user_id)
                    # 日次勤怠一括申請
                    bulk_request_time_stamp(obj_emp, td.year, td.month)
                    messages.success(self.request, "データを保存しました")
                except Exception:
                    messages.error(self.request, '保存できませんでした！' )
                    logger.exception('bulk_request exception ')
        return self.get(request, *args, **kwargs)

# 日次勤怠状態申請
class TimeStampStat(LoginRequiredMixin, View):
    def get(self, request, **kwargs):
        # user_id = self.kwargs.get('pk')
        # ログインユーザ以外のユーザを選択
        user_id = self.request.session.get('user_id', self.request.user.user_id)
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        mode = self.kwargs.get('mode')
        try:
            target_date = year * 10000 + month * 100 + day
            obj_emp = M_emp.objects.get(user_id=user_id)
            obj_timestamp = T_time_stamp.objects.filter(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date).first()
            if obj_timestamp != None and obj_timestamp.WORK_STAT == 1:
                obj_timestamp.WORK_STAT = 0 # 0:申請／1:申請中／2:承認済
                obj_timestamp.save()
            elif obj_timestamp != None and obj_timestamp.WORK_STAT == 0:
                obj_timestamp.WORK_STAT = 1 # 0:申請／1:申請中／2:承認済
                obj_timestamp.save()
            else:
                messages.error(self.request, '設定できませんでした！' )
        except Exception:
            messages.error(self.request, '保存できませんでした！' )
            logger.exception('TimeStampStat exception ')

        redirect_url = reverse('Kms_Attendance:monthly', kwargs={'year':year,'month':month,'mode':mode})
        # mode == 2:   # 勤怠承認日次勤怠画面->日次勤怠状態申請->勤怠承認日次勤怠画面
        # mode == 4:   # 今日の出退勤レポート日次勤怠画面->日次勤怠状態申請->今日の出退勤レポート日次勤怠画面
        # mode == 5:   # 月締状況レポート->日次勤怠状態申請->月締状況レポート
        # mode == 6:   # 月次レポート->日次勤怠状態申請->月次レポート
        # mode == 8:   # 休日管理レポート->日次勤怠状態申請->休日管理レポート
        # mode == 9:   # 月次集計データ出力->日次勤怠状態申請->月次集計データ出力
        # mode == 10:  # 日次勤怠データ出力->日次勤怠状態申請->日次勤怠データ出力
        # mode == 1:   # 日次勤怠画面->日次勤怠状態申請->日次勤怠画面

        return redirect(redirect_url)

# 勤怠承認画面
class Approval(LoginRequiredMixin, MonthCalendarMixin, ListView):
    template_name = 'Kms_Attendance/approval.html'
    model = T_time_stamp
    ordering = ['LTD_CD','EMP_ID','TARGET_DATE']

    def get_queryset(self):
        queryset = super().get_queryset()
        date =  self.request.POST.get('date')
        if date:
            td = datetime.datetime.strptime(date, '%Y/%m/%d')
        else:
            year = self.kwargs.get('year')
            month = self.kwargs.get('month')
            day = self.kwargs.get('day')
            if not year or not month or not day:
                td = ut_get_localtoday()
            else:
                td = datetime.date(year, month, day)

        number = self.request.POST.get('number')
        works_status = self.request.POST.get('works_status')
        full_name = self.request.POST.get('name')

        # month = ut_get_localtoday().strftime('%Y-%m')
        # max_month = (ut_get_localtoday() + relativedelta(years=10)).strftime('%Y-%m')

        self.extra_context = {
            'year': td.year,
            'month': td.month,
            'day': td.day,
            'date': td.strftime("%Y/%m/%d"),
            'number': number or '',
            'works_status': works_status or '',
            'full_name': full_name or ''
        }

        # 選択された出退勤区分
        kbn = self.request.POST.get('kbn')
        kbn = int(kbn) if kbn else 0
        if self.request.method == 'POST':
            # request.POST : requestの情報を辞書型のデータで取得
            form = ApprovalForm(self.request.POST or None)
        else:
            form = ApprovalForm(None)

        # ChoiceFieldに選択肢の設定
        form.fields['kbn'].choices = sv_get_kbn_choices()
        form.fields['kbn'].initial = kbn
        form.fields['name'].choices = sv_get_name_choices()
        form.fields['name'].initial = number
        self.form = form
        # 勤怠承認List
        approval_list = self.get_approvals(queryset, td, works_status, number, kbn, full_name)
        ids = []
        for obj in approval_list:
            uuid = str(obj.get('uuid', ''))
            user_id = obj.get('user_id', '')
            ids.append({'uuid':uuid, 'user_id':user_id})
        self.request.session['id_list'] = ids   # 一括承認で使用する対象データのリスト
        # 月次勤怠画面からの戻りで遷移する日付をセッション変数に
        self.request.session['approval_date'] = td.strftime("%Y/%m/%d")

        return approval_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['process_title'] = '勤怠承認'

        context['form'] = self.form
        return context
    def post(self, request, *args, **kwargs):
        if 'bulk_approval' in self.request.POST: # 一括承認
            # セッション変数からリストデータを取得(値を取り出し、セッションから取り除く)
            lists = self.request.session.pop('id_list', None)
            if lists:
                cnt = 0
                for item in lists:
                    try:
                        id = item.get('uuid')
                        obj_timestamp = T_time_stamp.objects.get(pk = uuid.UUID(id))
                        if obj_timestamp.WORK_STAT != 2:
                            obj_timestamp.WORK_STAT = 2 # 0:申請／1:申請中／2:承認済
                            obj_timestamp.save()
                            cnt += 1
                    except Exception:
                        continue
                messages.success(self.request, f'{cnt}件データを保存しました')

            # object_list = self.request.POST.getlist('object_items')  # フォームデータとして送信された場合
            # for id in object_list:
            #     try:
            #         obj = T_time_stamp.objects.get(pk=id)
            #         name = obj.EMP_ID
            #         date = obj.TARGET_DATE
            #     except T_time_stamp.DoesNotExist:
            #         continue
        else:
            # セッションデータクリア
            if 'id_list' in self.request.session:
                del self.request.session['id_list']

        return self.get(request, *args, **kwargs)

    # 勤怠承認List
    def get_approvals(self, queryset, td, works_status, number, kbn, full_name):
        timestamp_list = []
        year = td.year
        month = td.month
        day = td.day
        target_date = year * 10000 + month * 100 + day
        # holidays = M_holiday.objects.values_list('HOLIDAY_YMD', flat=True).order_by('HOLIDAY_YMD')

        q_objects = Q(TARGET_DATE=target_date)   # 「Q object」複雑な処理を実装できるクエリ
        if number is not None and number !='' and number != 0:
            q_objects &= Q(EMP_ID=number)
        if full_name is not None and full_name !='':
            q_objects &= Q(EMP_ID=full_name)
        if works_status is not None and works_status != '':
            if works_status == '0':
                q_objects &= Q(WORK_STAT=0) | Q(WORK_STAT=None)
            else:
                q_objects &= Q(WORK_STAT=int(works_status))
        if kbn is not None and kbn != 0:
            q_objects &= Q(KBN=kbn)

        timestamps = queryset.filter(q_objects).order_by('TARGET_DATE','EMP_ID')

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
                # 時間計算
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
                'uuid': obj_timestamp.id,
                'user_id' : user_id,
                'name' : name,
                'w' : w,
                # 'd' : str(month).zfill(2) + '/' + str(day).zfill(2),
                'd' : str(day).zfill(2),
                'is_saturday': td.weekday() == 5,
                'is_sunday': td.weekday() == 6,
                'is_holiday': holiday,
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

# 日次勤怠申請画面
class RequestEdit(LoginRequiredMixin, TemplateView):
    template_name = 'Kms_Attendance/request_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)    # 継承元のメソッド
        context['process_title'] = '日次勤怠申請'
        # user_id = self.kwargs.get('pk')
        # ログインユーザ以外のユーザを選択
        user_id = self.request.session.get('user_id', self.request.user.user_id)
        counter = self.kwargs.get('counter')
        if counter:
            lists = self.request.session.pop('id_list', None)
            if lists:
                if counter <= len(lists):
                    item = lists[counter - 1]
                    user_id = item.get('user_id')  # ログインユーザ以外のユーザを選択
        self.request.session['user_id'] = user_id
        try:
            obj_emp = M_emp.objects.get(user_id=user_id)
        except M_emp.DoesNotExist:
            return context
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        if not year or not month or not day:
            dt_today = ut_get_localtoday()
            year = dt_today.year
            month = dt_today.month
            day = dt_today.day

        context = self.get_time_stamp_context(context, year, month, day, obj_emp)   # 打刻テーブルコンテキスト取得
        context = self.get_request_context(context, year, month, day, obj_emp)      # 申請テーブル・申請休憩テーブルコンテキスト取得
        return context

    def post(self, request, **kwargs):
        # user_id = self.kwargs.get('pk')
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        mode = self.kwargs.get('mode')

        if 'cancel' in self.request.POST:
            # messages.info(self.request, 'キャンセル！')
            if mode == 3:
                redirect_url = reverse('Kms_Attendance:approval', kwargs={'year':year,'month':month,'day':day,})
            else:
                redirect_url = reverse('Kms_Attendance:monthly', kwargs={'year':year,'month':month,'mode':mode})
            # mode == 1:    # 日次勤怠画面->日次勤怠申請画面->日次勤怠画面
            # mode == 2:    # 勤怠承認日次勤怠画面->日次勤怠申請画面->勤怠承認日次勤怠画面
            # mode == 3:    # 勤怠承認画面->日次勤怠申請画面->勤怠承認画面
            # mode == 4:    # 今日の出退勤レポート日次勤怠画面->日次勤怠申請画面->今日の出退勤レポート日次勤怠画面
            # mode == 5:    # 月締状況レポート->日次勤怠申請画面->月締状況レポート
            # mode == 6:    # 月次レポート->日次勤怠状態申請->月次レポート
            # mode == 8:    # 休日管理レポート->日次勤怠状態申請->休日管理レポート
            # mode == 9:    # 月次集計データ出力->日次勤怠状態申請->月次集計データ出力
            # mode == 10:   # 日次勤怠データ出力->日次勤怠状態申請->日次勤怠データ出力
            return redirect(redirect_url)

        id = self.request.POST.get('id')
        try:
            obj_timestamp = T_time_stamp.objects.get(pk = id)
            form = TimeStampEditForm(self.request.POST, instance=obj_timestamp)
            # instanceなしだと新規作成となりform.is_valid()で、unique制約により「重複している」となる
        except T_time_stamp.DoesNotExist:
            form = TimeStampEditForm(self.request.POST)      # 新規作成/create

        if form.is_valid():
            KBN = self.request.POST.get('kbns_cd')
            start_time = self.request.POST.get('CORRET_START_TIME')
            end_time = self.request.POST.get('CORRET_END_TIME')
            if KBN != '2' and KBN != '3' and KBN != '5' and KBN != '7':
                if (check_time(start_time, end_time) != ''):
                    messages.error(self.request, '時刻の指定が正しくありません！' )
                    # messages.error(self.request, form.errors)
                    return redirect(request.get_full_path())
            comment = self.save_time_stamp(year, month, day, start_time, end_time) # 打刻テーブル

            if comment: # 打刻テーブル保存成功
                messages.info(self.request, comment)

                self.save_request()  # 申請テーブル
                self.save_request_rest(year, month, day)   # 申請休憩テーブル
                if KBN == '2' or KBN == '3' or KBN == '5' or KBN == '7':
                    self.save_request_holiday(year, month, day)   # 申請休憩テーブル

                if mode == 3:   # 勤怠承認画面->日次勤怠申請画面->勤怠承認画面
                    redirect_url = reverse('Kms_Attendance:approval', kwargs= {'year':year,'month':month,'day':day,})
                else:
                    redirect_url = reverse('Kms_Attendance:monthly', kwargs={'year':year,'month':month,'mode':mode})
                return redirect(redirect_url)
        #
        # form invalid or save failed の場合
        #
        messages.error(self.request, '保存できませんでした！' )
        # messages.error(self.request, form.errors)
        form2 = RequestEditForm(self.request.POST)   # 申請テーブル情報

        # 休憩に入力された情報を引き継ぐ
        list_start = self.request.POST.getlist("rest_start")
        list_start_chk = self.request.POST.getlist("rest_start_chk")
        list_end = self.request.POST.getlist("rest_end")
        list_end_chk = self.request.POST.getlist("rest_end_chk")
        rest_list = []
        for i, start in enumerate(list_start):
            if get_time2date_str(start, year, month, day) == '':
                continue
            list = {
                'REST_START_TIME': start,
                'REST_START_NEXT_FLG': 1 if str(i+1) in list_start_chk else 0,
                'REST_END_TIME' : list_end[i],
                'REST_END_NEXT_FLG': 1 if str(i+1) in list_end_chk else 0
            }
            rest_list.append(list)

        context = { 'form': form,
                    'form2': form2,
                    'restlist': rest_list,
                    'year': year,
                    'month': month,
                    'day': day,
                    'mode': mode,
        }
        return render(request, 'Kms_Attendance/request_edit.html', context)
    # 打刻テーブルコンテキスト取得
    def get_time_stamp_context(self, context, year, month, day, obj_emp):
        target_date = year * 10000 + month * 100 + day
        try:
            obj_timestamp = T_time_stamp.objects.get(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date)
        except T_time_stamp.DoesNotExist:
            obj_timestamp = None

        if obj_timestamp == None:
            td = datetime.datetime(year, month, day)
            kbn = 7 if is_holiday(td) else 1
            start = ''
            end = ''
            corret_start = ''
            corret_end = ''
            work_stat = 0
        else:
            kbn = obj_timestamp.KBN
            start = get_date2time_str(obj_timestamp.START_TIME) # '%Y/%m/%d %H:%M:%S' --> '%H:%M'
            end = get_date2time_str(obj_timestamp.END_TIME)
            corret_start = get_date2time_str(obj_timestamp.CORRET_START_TIME)
            corret_end = get_date2time_str(obj_timestamp.CORRET_END_TIME)
            work_stat = obj_timestamp.WORK_STAT

        td = datetime.datetime(year, month, day)
        w = MonthCalendarMixin.week_names[td.weekday()]

        mode = self.kwargs.get('mode')

        initial_dict = dict(
            LTD_CD = obj_emp.LTD_CD,
            EMP_ID = obj_emp.EMP_ID,
            TARGET_DATE = target_date,
            date_field =  f'{td.strftime("%Y/%m/%d")}({w})',
            kbns_cd = kbn,
            KBN = kbn,
            CORRET_START_TIME = corret_start,
            START_TIME = start,
            CORRET_END_TIME = corret_end,
            END_TIME = end,
            stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請',
            )
        if obj_timestamp:
            # 指定したフィールドのみ object の値を適用
            # idを設定しないと新規作成となりform.is_valid()で、unique制約により「重複している」となる
            initial_dict['id'] = getattr(obj_timestamp, 'id')

            # form = TimeStampEditForm(None, initial=initial_dict, instance=obj_timestamp)
            # # 適用したいフィールド
            # apply_from_instance = ['id']
            # # 指定したフィールドのみ instance の値を適用
            # for field in apply_from_instance:
            #     initial_dict[field] = getattr(obj_timestamp, field)

        form = TimeStampEditForm(None, initial=initial_dict)

        if obj_timestamp == None:
            end_next_flg = False
        else:
            end_next_flg = is_nextday(obj_timestamp.CORRET_START_TIME,obj_timestamp.CORRET_END_TIME)

        context.update({
            'user_id': obj_emp.user_id,
            'year': year,
            'month': month,
            'day': day,
            'date': f'{td.strftime("%Y/%m/%d")}({w})',
            'mode': mode,
            'username': obj_emp.EMP_NAME,
            'number': obj_emp.EMP_ID,
            'form': form,
            'end_next_flg': end_next_flg
            })

        return context

    # 申請テーブル・申請休憩テーブルコンテキスト取得
    def get_request_context(self, context, year, month, day, obj_emp):
        target_date = year * 10000 + month * 100 + day
        try:
            obj_request = T_request.objects.get(
                LTD_CD = obj_emp.LTD_CD,
                EMP_ID = obj_emp.EMP_ID,
                TARGET_DATE = target_date)
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

        initial_dict2 = dict(
            LTD_CD = obj_emp.LTD_CD,
            EMP_ID = obj_emp.EMP_ID,
            TARGET_DATE = target_date,
            EXPENSES = expenses,
            MEMO = memo,
            AGREE_COMMENT = comment,
            stat = '申請中' if work_stat == 1 else '承認済み' if work_stat == 2 else '申請',
        )
        if obj_request:
            initial_dict2['id'] = getattr(obj_request, 'id')
        form2 = RequestEditForm(None, initial=initial_dict2)    # 申請テーブル情報
        context.update({'form2': form2})
        # 申請休憩テーブル
        queryset = T_request_rest.objects.filter(
            LTD_CD = obj_emp.LTD_CD,
            EMP_ID = obj_emp.EMP_ID,
            TARGET_DATE = target_date).order_by('REST_NO')
        rest_list = list(queryset.values())
        for rec in rest_list:
            rec['REST_START_TIME'] = get_date2time_str(rec['REST_START_TIME'])  # '%Y/%m/%d %H:%M:%S' --> '%H:%M'
            rec['REST_END_TIME'] = get_date2time_str(rec['REST_END_TIME'])
        context.update({'restlist': rest_list})

        return context
    # 打刻テーブル登録
    def save_time_stamp(self, year, month, day, start_time, end_time):
        id = self.request.POST.get('id')
        ltd_cd = self.request.POST.get('LTD_CD')
        emp_id = self.request.POST.get('EMP_ID')
        target_date = self.request.POST.get('TARGET_DATE')
        end_next_flg = True if 'next_day_end' in self.request.POST else False
        comment = ''
        try:
            obj_timestamp,created = T_time_stamp.objects.get_or_create(
                LTD_CD = ltd_cd,
                EMP_ID = emp_id,
                TARGET_DATE = target_date,
                defaults = dict(
                    id = id,
                    KBN = 1,
                ),
            )
            if created:
                obj_timestamp.INS_DATE = ut_get_timezone_now()
                obj_timestamp.INS_ID = self.request.user.user_id # emp_id
                obj_timestamp.DEL_FLG = 0
            else:
                ins_date = ut_get_localdate(obj_timestamp.INS_DATE)
                obj_timestamp.INS_DATE = ins_date or ut_get_timezone_now()

            obj_timestamp.UPDATE_DATE = ut_get_timezone_now()
            obj_timestamp.UPDATE_ID = self.request.user.user_id  # emp_id
            if start_time:
                obj_timestamp.CORRET_START_TIME = get_time2date_str(start_time, year, month, day)
            if end_time:
                obj_timestamp.CORRET_END_TIME = get_time2date_str(end_time, year, month, day, end_next_flg)
            obj_timestamp.KBN = self.request.POST.get('kbns_cd')
            if 'commit' in self.request.POST:
                comment = '登録しました！'
                obj_timestamp.WORK_STAT = 1 # 0:申請／1:申請中／2:承認済
            elif 'approval' in self.request.POST:
                comment = '承認しました！'
                obj_timestamp.WORK_STAT = 2
            elif 'add' in self.request.POST:
                comment = '申請しました！'
                obj_timestamp.WORK_STAT = 1
            obj_timestamp.save()
        except Exception:
            logger.exception('exception ')
        return comment
    # 申請テーブル
    def save_request(self):
        try:
            ltd_cd = self.request.POST.get('LTD_CD')
            emp_id = self.request.POST.get('EMP_ID')
            target_date = self.request.POST.get('TARGET_DATE')
            expenses = self.request.POST.get('EXPENSES')
            if expenses == None or expenses=='':
                expenses = 0
            memo = self.request.POST.get('MEMO')
            agree_comment = self.request.POST.get('AGREE_COMMENT')
            obj_request,created = T_request.objects.get_or_create(
                LTD_CD = ltd_cd,
                EMP_ID = emp_id,
                TARGET_DATE = target_date,
                defaults = dict(
                    # id = uuid.uuid4(),
                    KBN = 1,
                    END_NEXT_FLG = 0,
                    REQUEST_DATE = get_date2int(ut_get_localtime())
                ),
            )
            if created:
                obj_request.INS_DATE = ut_get_timezone_now()
                obj_request.INS_ID = self.request.user.user_id   # emp_id
                obj_request.DEL_FLG = 0
                obj_request.WORK_STAT = 0
            else:
                ins_date = ut_get_localdate(obj_request.INS_DATE)
                obj_request.INS_DATE = ins_date or ut_get_timezone_now()

            obj_request.UPDATE_DATE = ut_get_timezone_now()
            obj_request.UPDATE_ID = self.request.user.user_id    # emp_id
            obj_request.EXPENSES = expenses
            obj_request.MEMO = memo
            obj_request.AGREE_COMMENT = agree_comment
            obj_request.save()
        except Exception:
            logger.exception('exception ')
            return False
        return True
    # 申請休憩テーブル
    def save_request_rest(self, year, month, day):
        try:
            ltd_cd = self.request.POST.get('LTD_CD')
            emp_id = self.request.POST.get('EMP_ID')
            target_date = self.request.POST.get('TARGET_DATE')

            list_start = self.request.POST.getlist("rest_start")
            list_start_chk = self.request.POST.getlist("rest_start_chk")
            list_end = self.request.POST.getlist("rest_end")
            list_end_chk = self.request.POST.getlist("rest_end_chk")
            for i, start in enumerate(list_start):
                # '%H:%M' --> '%Y/%m/%d %H:%M:%S'
                start_str = get_time2date_str(start, year, month, day)
                if start_str == '':
                    continue
                obj_request_rest,created = T_request_rest.objects.get_or_create(
                        LTD_CD = ltd_cd,
                        EMP_ID = emp_id,
                        TARGET_DATE = target_date,
                        REST_NO = i + 1,
                        defaults = dict(
                            # id = uuid.uuid4(),
                            REST_START_NEXT_FLG = 0,
                            REST_END_NEXT_FLG = 0,
                        ),
                    )
                if created:
                    obj_request_rest.INS_DATE = ut_get_timezone_now()
                    obj_request_rest.INS_ID = self.request.user.user_id  # emp_id
                    obj_request_rest.DEL_FLG = 0
                else:
                    ins_date = ut_get_localdate(obj_request_rest.INS_DATE)
                    obj_request_rest.INS_DATE = ins_date or ut_get_timezone_now()

                obj_request_rest.UPDATE_DATE = ut_get_timezone_now()
                obj_request_rest.UPDATE_ID = self.request.user.user_id   # emp_id

                obj_request_rest.REST_START_TIME = start_str
                obj_request_rest.REST_START_NEXT_FLG = 1 if str(i+1) in list_start_chk else 0
                obj_request_rest.REST_END_TIME = get_time2date_str(list_end[i], year, month, day)
                obj_request_rest.REST_END_NEXT_FLG = 1 if str(i+1) in list_end_chk else 0
                obj_request_rest.save()
        except Exception:
            logger.exception('exception ')
            return False
        return True
    # 休暇申請テーブル
    def save_request_holiday(self, year, month, day):
        try:
            ltd_cd = self.request.POST.get('LTD_CD')
            emp_id = self.request.POST.get('EMP_ID')
            target_date = year * 10000 + month * 100 + day

            KBN = int(self.request.POST.get('kbns_cd', '0'))
            obj,created = T_request_holiday.objects.get_or_create(
                    LTD_CD = ltd_cd,
                    EMP_ID = emp_id,
                    TARGET_DATE = target_date,
                    defaults = dict(
                        # id = uuid.uuid4(),
                        # REST_START_NEXT_FLG = 0,
                        # REST_END_NEXT_FLG = 0,
                        KBN = KBN,
                        REQUEST_DATE = get_date2int(ut_get_localtime())
                    ),
                )
            if created:
                obj.INS_DATE = ut_get_timezone_now()
                obj.INS_ID = self.request.user.user_id  # emp_id
                obj.DEL_FLG = 0
            else:
                ins_date = ut_get_localdate(obj.INS_DATE)
                obj.INS_DATE = ins_date or ut_get_timezone_now()

            obj.UPDATE_DATE = ut_get_timezone_now()
            obj.UPDATE_ID = self.request.user.user_id   # emp_id

            obj.KBN = KBN
            obj.TRANSFER_DATE = target_date
            obj.REQUEST_DATE = get_date2int(ut_get_localtime())
            # obj.AGREE_DATE =
            # obj.AGREE_LTD_CD =
            # obj.AGREE_EMP_ID = ''
            obj.MEMO = ''
            obj.save()
        except Exception:
            logger.exception('exception ')
            return False
        return True

