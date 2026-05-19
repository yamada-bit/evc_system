import calendar
import datetime
import requests
import jpholiday
# import csv
import logging

from django.shortcuts import redirect,render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse,JsonResponse
from django.conf import settings

from google_auth_oauthlib.flow import Flow
# from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from dateutil.relativedelta import relativedelta
from collections import defaultdict

from commons.mixins import MonthCalendarMixin
from commons.utils import ut_get_client_ip,ut_get_localtoday

from Kms_Calendar.google_calendar import (
    get_calendar_service,dict_to_credentials,credentials_to_dict
)
from Kms_Calendar.excel_calendar import (
    create_attendance_data,process_work_events,calendar_to_excel,update_attendance_to_excel
)
from Evc_App.sv_file import sv_get_user_name
# from Kms_Attendance.models import M_holiday

FORMAT_DATE = '%Y/%m/%d %H:%M:%S'
FORMAT_MD = '%#m/%#d'
FORMAT_HM = '%#H:%M'
WEEKRY_LIST = ['月', '火', '水', '木', '金', '土', '日']

logger = logging.getLogger(__name__)

"""認証状態を確認し、認証されていない場合はGoogle認証画面にリダイレクト"""
def ensure_authenticated(request):
    # セッションに保存したアクセストークンを取得
    credentials_dict = request.session.get('google_credentials')
    # トークンがない場合、認証フローを開始
    if not credentials_dict:
        # # 現在アクセスされているページのURLをセッションに保存
        # request.session['redirect_after_auth'] = request.build_absolute_uri()
        # STGでリダイレクト先が https://stg.example.com/calendar/calendar/
        # 変更（pathだけ保存する）
        request.session['redirect_after_auth'] = request.get_full_path()
        return redirect('Kms_Calendar:google_auth')
    # トークンが有効か確認
    try:
        # 辞書形式から credentials オブジェクトを復元(expiryをdatetimeで取得)
        credentials = dict_to_credentials(credentials_dict)
        # credentials = Credentials(**credentials_dict)
        if credentials.expired:
            # トークンの有効期限が切れた場合、自動的に更新
            credentials.refresh(Request())
            request.session['google_credentials'] = credentials_to_dict(credentials)
    except Exception as e:
        # 認証エラー時に再認証をトリガー
        logger.exception('exception credentials')
        # request.session['redirect_after_auth'] = request.build_absolute_uri()
        # STGでリダイレクト先が https://stg.example.com/calendar/calendar/
        # 変更（pathだけ保存する）
        request.session['redirect_after_auth'] = request.get_full_path()
        return redirect('Kms_Calendar:google_auth')
    # 認証されている
    return None
# 認証フロー
def google_auth(request):
    # client_secrets.jsonファイルからgoogle_auth_oauthlibのFlowオブジェクトを作成
    # この JSON 形式のファイルには、クライアント ID、クライアント シークレット、
    # およびその他の OAuth 2.0 パラメーターが格納
    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_CREDENTIALS_FILE,
        scopes=settings.GOOGLE_SCOPES,
    )
    # 認証を終えた後にリダイレクトするURL
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    # 認証URLを生成
    # ユーザーにGoogleの認証ページにリダイレクトするためのURLを取得
    auth_url, state = flow.authorization_url(
        access_type='offline',
        # include_granted_scopes='true',    # すでにユーザーが許可したスコープが自動で追加される
                                            # ユーザーがすでに許可したスコープを維持したい場合
        include_granted_scopes='false',     # 「常に指定したスコープだけを適用したい」場合
        # promptは、2回目の同意画面の関して制限できるオプション
        # OAuth認証時に毎回同意画面が表示
        prompt='consent'
    )
    # セッションにstateを保存
    request.session['oauth_state'] = state
    # ユーザーを認証ページにリダイレクト
    return redirect(auth_url)

"""Google認証フローのリダイレクトを処理し、トークンを保存後、元のページに戻る"""
# OAuth認証の疎通テストではログイン画面とリダイレクト先のホスト名が異なってしまうと、
# 同一セッションとみなされなくなり上手く動かない
def oauth2callback(request):
    error = request.GET.get("error")  # キャンセルされた場合、"access_denied" になる    
    if error == "access_denied":
        return redirect('Kms_Calendar:calendar_model')

    # OAuth 2.0 フローを再構築
    state = request.session.get('oauth_state')

    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_CREDENTIALS_FILE,
        scopes=settings.GOOGLE_SCOPES,
        state=state
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    # # ↓ デバッグ用に追加
    # logger.info(f'redirect_uri: {flow.redirect_uri}')
    # logger.info(f'build_absolute_uri: {request.build_absolute_uri()}')
    # logger.info(f'callback_uri: {settings.GOOGLE_REDIRECT_URI}?{request.GET.urlencode()}')
    
    # Googleからのリダイレクトを処理
    # アクセストークンを取得し、セッションに保存
    try:
        # flow.fetch_token(authorization_response=request.build_absolute_uri())
        ##STG(http) nginxからDjangoへは `HTTP/1.0` で届いているため、`build_absolute_uri()` が
        ## 実際に生成されるURI
        ## http://stg.example.com/calendar/oauth2callback/?state=...&code=...
        # settings.GOOGLE_REDIRECT_URI と完全一致させる
        callback_uri = settings.GOOGLE_REDIRECT_URI + '?' + request.GET.urlencode()
        flow.fetch_token(authorization_response=callback_uri)
        logger.info(f'fetch callback_uri: {callback_uri}')  # ← 追加

        credentials = flow.credentials
        # アクセストークンをセッションに保存
        request.session['google_credentials'] = credentials_to_dict(credentials)
    except Exception as e:
        logger.exception('fetch_token Exception')
    # # トークンを保存
    # creds = flow.credentials
    # token_path = settings.GOOGLE_TOKEN_FILE
    # with open(token_path, 'w') as token_file:
    #     token_file.write(creds.to_json())

    # # CSVアップロードの処理の場合
    # if 'google_csv_file' in request.session:
    #     # CSVアップロードの処理
    #     # CSVファイルパスを取得(値を取り出し、セッションから取り除く)
    #     file_path = request.session.pop('google_csv_file')
    #     url = register_events_to_calendar(request, file_path)
    #     # リダイレクト元でないURL
    #     return url

    # リダイレクト元のURLを取得(値を取り出し、セッションから取り除く)
    redirect_url = request.session.pop('redirect_after_auth', '/')
    # logger.info(f'redirect_url: {redirect_url}')  # ← 追加
    return redirect(redirect_url)
    # return JsonResponse({'message': 'Authentication successful!'})

def google_logout(request):
    """トークンを無効化してログアウト"""
    try:
        credentials_dict = request.session.get('google_credentials')
        if credentials_dict:
            access_token = credentials_dict['token']
            if access_token:
                # トークン無効化リクエスト
                requests.post(
                    'https://oauth2.googleapis.com/revoke',
                    params={'token': access_token},
                    headers={'content-type': 'application/x-www-form-urlencoded'}
                )
    except Exception:
        logger.exception('Exception')
    
    # セッション情報を削除
    # request.session.flush()
    if 'google_credentials' in request.session:
        del request.session['google_credentials']
    if 'redirect_after_auth' in request.session:
        del request.session['redirect_after_auth']
    if 'oauth_state' in request.session:
        del request.session['oauth_state']
    # if 'google_csv_file' in request.session:
    #     del request.session['google_csv_file']

    # ログアウト後のリダイレクト先
    # return redirect('/')
    return redirect('accounts:mainmenu')
    # return redirect('Kms_Calendar:google_calendar')

# 時刻のフォーマット変換
def formatted_time(date_obj):
    try:
        time_formatted = date_obj.strftime(FORMAT_HM)
    except ValueError:  # 例: 終日イベントの場合は 'YYYY-MM-DD'
        time_formatted = '00:00'
    return time_formatted

# 時間のフォーマット変換
def timedelta_to_hm(td):
    try:
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f'{hours}:{minutes:02}'
    except Exception:
        logger.exception('Exception')
    return ''

# 日付と曜日を結合
def add_weekday_to_date(date_obj):
    try:
        date_str = date_obj.strftime(FORMAT_MD)
        # 曜日リスト
        weekdays = WEEKRY_LIST
        # 曜日を取得
        weekday_str = weekdays[date_obj.weekday()]
        # 日付と曜日を結合して返す
        return f'{date_str}（{weekday_str}）'
    except Exception:
        logger.exception('Exception')
    return ''

"""GoogleカレンダーAPIの認証情報をロード"""
# def load_credentials():
#     creds_path = os.path.join(os.getcwd(), 'credentials.json')
#     creds = Credentials.from_authorized_user_file(creds_path, settings.GOOGLE_SCOPES)
#     return creds

"""GoogleカレンダーAPIを使用してイベントを取得"""
class GoogleCalendarView(LoginRequiredMixin, MonthCalendarMixin, TemplateView):
    template_name = 'Kms_Calendar/Kms_Calendar.html'
    def get(self, request, *args, **kwargs):
        # 認証状態を確認
        auth_check = ensure_authenticated(request)
        if auth_check:
            return auth_check  # 未認証の場合、Google認証画面にリダイレクト
        else:
            return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.debug('GoogleCalendarView start')

        context['process_title'] = 'Googleカレンダー連携　外勤報告書'

        # セッションに保存したアクセストークンを取得
        credentials_dict = self.request.session.get('google_credentials')
        if not credentials_dict:
            logger.debug('GoogleCalendarView not credentials_dict')
            return JsonResponse({'error': 'User not authenticated'}, status=401)

        # Google Calendar APIクライアントの作成
        service = get_calendar_service(credentials_dict)

        try:
            target_year = self.kwargs['year']
            target_month = self.kwargs['month']
        except KeyError:
            target_year = ut_get_localtoday().year
            target_month = ut_get_localtoday().month

        logger.info(f'{ut_get_client_ip(self.request)} '
                    f'GoogleCalendarView {target_year}/{target_month}')
        # Google Calendar APIを使ってイベントを取得
        events = get_calendar_events(service, target_year, target_month)
        # 勤怠データを収集
        attendance = process_work_events(events)    # 勤務イベントを日ごとに整理し、勤務時間を計算
        # attendance = create_attendance_data(events) # 勤務時間を個別に集計
        # HTML表示データを収集
        calendar_data = get_monthly_attendance_data(attendance, target_year, target_month)

        # 2024年4月以前には遷移できないように制限
        can_go_prev = not (target_year == 2024 and target_month == 4)
        can_go_next = True  # not (target_year == 2026 and target_month == 3)
        context.update({
            'year': target_year,
            'month': target_month,
            'calendar_data': calendar_data,
            'can_go_prev': can_go_prev,
            'can_go_next': can_go_next,
            })

        # 月間カレンダー情報の入った辞書を返す
        # commons/mixins.py MonthCalendarMixin
        calendar_context = self.get_month_calendar(target_year, target_month)
        context.update(calendar_context)

        # 認証ログインを要求するためセッション情報を削除
        # google_logout(self.request)
        return context

# Google Calendar イベント取得
"""Googleカレンダーから指定期間のイベントを取得"""
def get_calendar_events(service, year, month):
    # today = datetime.datetime.now(datetime.timezone.utc) 
    # start_of_day = datetime.datetime.combine(today, datetime.time.min).isoformat() + 'Z'
    # end_of_day = datetime.datetime.combine(today, datetime.time.max).isoformat() + 'Z'

    # 指定月の開始日と終了日を計算
    start_date = datetime.datetime(year, month, 1)
    # # 月末 (来月の1日に合わせて1日分戻る)
    # end_date = start_date + relativedelta(months=+1, day=1, days=-1)
    # 月末 (来月の1日の00:00:00まで)
    end_date = start_date + relativedelta(months=+1, day=1)

    # ISO 8601形式の文字列に変換
    time_min = start_date.isoformat() + 'Z'
    time_max = end_date.isoformat() + 'Z'

    # カレンダーID（デフォルトカレンダーの場合は 'primary'）
    calendar_id = 'primary'  # メインのカレンダー
    # カレンダーのイベントを取得
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,   # 取得する開始時刻
        timeMax=time_max,
        # maxResults=100, 
        singleEvents=True,  # 繰り返しインスタンスを展開
        orderBy='startTime'
    ).execute()

    logger.debug(f'events {time_min}-{time_max}')

    events = events_result.get('items', [])
    return events

# 休日チェック
def is_holiday(day):
    # jpholiday パッケージを使えば祝日判定が簡単にできます。
    is_holiday = jpholiday.is_holiday(day)
    return is_holiday
    # # 休日マスタで休日チェック
    # date = day.year * 10000 + day.month * 100 + day.day
    # if M_holiday.objects.filter(HOLIDAY_YMD=date).exists():
    #     return True
    # return False

# HTMLに表示する勤怠データを収集
def get_monthly_attendance_data(attendance, year, month):
    cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
    # その月の全ての日、月初や月末の週には前後の月の月末や月初が入ってくることがある
    month_days = cal.itermonthdates(year, month)

    calendar_data = []
    for day in month_days:
        is_event = False
        if day.month == month:  # 前後月の日付は除外
            try:
                if day in attendance:
                    event = attendance[day]
                    if event:               # 勤務イベントを日ごとに整理
                    # for i, event in enumerate(attendance[day]): # 勤務時間を個別に集計
                        record = {
                            'day': day,
                            # 'in_month': True,
                            'is_saturday': day.weekday() == 5,
                            'is_sunday': day.weekday() == 6,
                            'is_holiday': is_holiday(day),
                            'date': add_weekday_to_date(day),
                            'title': event.get('title', ''),
                            'location': event.get('location', ''),  # '場所が指定されていません ')
                            'description': event.get('description', '')    # '内容が指定されていません ')
                        }
                        if event.get('allday') == '終日':
                            record['start'] = '終日'
                        else:
                            start_dt = event.get('start')
                            end_dt = event.get('end')
                            record['start'] = formatted_time(start_dt)
                            record['end'] = formatted_time(end_dt)
                            if start_dt and end_dt:
                                duration = end_dt - start_dt
                                # 作業時間（昼休憩１時間を引く）
                                # duration = end_dt - start_dt - datetime.timedelta(hours=1)
                                record['work_hours'] = timedelta_to_hm(duration)

                        calendar_data.append(record)
                        is_event = True
            except Exception:
                logger.exception(f'Exception {day}')
            if not is_event:    # イベントデータがない日
                record = {
                    'day': day,
                    # 'in_month': True,
                    'is_saturday': day.weekday() == 5,
                    'is_sunday': day.weekday() == 6,
                    'is_holiday': is_holiday(day),
                    'date': add_weekday_to_date(day),
                }
                calendar_data.append(record)
    return calendar_data

"""Googleカレンダー連携前表示"""
class GoogleCalendarModelView(LoginRequiredMixin, MonthCalendarMixin, TemplateView):
    template_name = 'Kms_Calendar/Kms_CalendarModel.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.debug('GoogleCalendarModelView start')

        context['process_title'] = '外勤報告書(カレンダー連携前)'

        try:
            target_year = self.kwargs['year']
            target_month = self.kwargs['month']
        except KeyError:
            target_year = ut_get_localtoday().year
            target_month = ut_get_localtoday().month

        logger.debug(f'{ut_get_client_ip(self.request)} '
                    f'GoogleCalendarModelView {target_year}/{target_month}')
        attendance = {}
        # HTML表示データを収集
        calendar_data = get_monthly_attendance_data(attendance, target_year, target_month)

        # 2024年4月以前には遷移できないように制限
        can_go_prev = not (target_year == 2024 and target_month == 4)
        can_go_next = True  # not (target_year == 2026 and target_month == 3)

        context.update({
            'year': target_year,
            'month': target_month,
            'calendar_data': calendar_data,
            'can_go_prev': can_go_prev,
            'can_go_next': can_go_next,
            })

        # 月間カレンダー情報の入った辞書を返す
        # commons/mixins.py MonthCalendarMixin
        calendar_context = self.get_month_calendar(target_year, target_month)
        context.update(calendar_context)

        return context

"""CSVデータをGoogleカレンダーに登録"""
# def register_events_to_calendar(request, csv_file_path):
#     # creds = load_credentials()
#     # service = build('calendar', 'v3', credentials=creds)
#     auth_check = ensure_authenticated(request)
#     if auth_check:
#         return auth_check  # 未認証の場合、Google認証画面にリダイレクト
#     # セッションに保存したアクセストークンを取得
#     credentials_dict = request.session.get('google_credentials')
#     if not credentials_dict:
#         return JsonResponse({'error': 'User not authenticated'}, status=401)
#     service = get_calendar_service(credentials_dict)

#     # CSVを読み込んでイベントを登録
#     with open(csv_file_path, 'r', encoding='utf-8') as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             event = {
#                 'summary': row['summary'],
#                 'description': row['description'],
#                 'location': row['location'],
#                 'start': {
#                     'dateTime': f'{row["start_date"]}T{row["start_time"]}:00',
#                     'timeZone': 'Asia/Tokyo',
#                 },
#                 'end': {
#                     'dateTime': f'{row["end_date"]}T{row["end_time"]}:00',
#                     'timeZone': 'Asia/Tokyo',
#                 },
#             }
#             service.events().insert(calendarId='primary', body=event).execute()
#     # 認証ログインを要求するためセッション情報を削除
#     # google_logout(request)

#     return render(request, 'Kms_Calendar/success.html')
""""""
"""CSVファイルをアップロードしてGoogleカレンダーに登録"""
""""""
# def upload_csv_and_register(request):
#     # 認証リダイレクトでCSVアップロードを処理するためのセッション変数を削除
#     if 'google_csv_file' in request.session:
#         del request.session['google_csv_file']

#     if request.method == 'POST' and request.FILES['csv_file']:
#         csv_file = request.FILES['csv_file']
#         file_path = f'../data/{csv_file.name}'

#         # ファイルを保存
#         with open(file_path, 'wb+') as destination:
#             for chunk in csv_file.chunks():
#                 destination.write(chunk)

#         # 認証リダイレクトでCSVアップロードを処理するためのセッション変数を保存
#         request.session['google_csv_file'] = file_path
#         # イベント登録
#         url = register_events_to_calendar(request, file_path)
#         return url
#         # return render(request, 'Kms_Calendar/success.html')
#     return render(request, 'Kms_Calendar/upload.html')

"""勤務表をExcelとしてダウンロード"""
def export_calendar_to_excel(request):
    auth_check = ensure_authenticated(request)
    if auth_check:
        # return auth_check  # 未認証の場合、Google認証画面にリダイレクト
        # 未認証の場合でGoogle認証画面にリダイレクト後の戻り画面が指定できないためエラーに
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    # セッションに保存したアクセストークンを取得
    credentials_dict = request.session.get('google_credentials')
    if not credentials_dict:
        return JsonResponse({'error': 'User not authenticated'}, status=401)

    # Google Calendar APIクライアントの作成         
    service = get_calendar_service(credentials_dict)
    this_year=ut_get_localtoday().year
    this_month=ut_get_localtoday().month
    events = get_calendar_events(service, this_year, this_month)
    # データを日ごとにグループ化
    grouped_events = group_events_by_day(events)

    output = calendar_to_excel(grouped_events)
    if not output:
        return JsonResponse({'error': 'データ作成中にエラーが発生しました。'}, status=500)
    logger.info(f'{ut_get_client_ip(request)} '
                'export_calendar_to_excel')

    # HTTPレスポンスでExcelを返す
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="calendar.xlsx"'
    # wb.save(response)
    response.write(output.getvalue())  # メモリからデータを書き込む
    return response

# データを日ごとにグループ化
def group_events_by_day(events):
    grouped_events = defaultdict(list)

    for event in events:
        try:
            start_time_str = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))
            end_time_str = event.get('end', {}).get('dateTime', event.get('end', {}).get('date'))

            if start_time_str:
                date_key = datetime.datetime.fromisoformat(start_time_str[:10]).strftime('%Y-%m-%d')

                # 時間のフォーマット
                if 'T' in start_time_str and 'T' in end_time_str:
                    start_time = datetime.datetime.fromisoformat(start_time_str).strftime('%H:%M')
                    end_time = datetime.datetime.fromisoformat(end_time_str).strftime('%H:%M')
                    time_range = f'{start_time} - {end_time}'
                else:
                    time_range = '終日'

                # イベント情報をリストに追加
                event_summary = event.get('summary', '（無題）')
                grouped_events[date_key].append(f'{time_range} {event_summary}')
        except Exception:
            logger.exception('Exception')

    return grouped_events

"""勤務表(未記入)をExcelとしてダウンロード"""
def export_calendar_model_to_excel(request, year, month):
    attendance = {}
    user_name = sv_get_user_name(request.user.user_id)
    # 勤務表テンプレートを読み込み、メモリに保存
    output = update_attendance_to_excel(attendance, year, month, user_name)
    if not output:
        return JsonResponse({'error': 'データ作成中にエラーが発生しました。'}, status=500)
    logger.info(f'{ut_get_client_ip(request)} '
                f'export_calendar_model_to_excel {year}/{month}')

    # HTTPレスポンスでExcelを返す
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="calendar_{year}_{month}.xlsx"'
    # wb.save(response)
    response.write(output.getvalue())  # メモリからデータを書き込む
    return response

"""指定された年月の勤務表をExcelとしてダウンロード"""
def export_work_schedule_to_excel(request, year, month):
    auth_check = ensure_authenticated(request)
    if auth_check:
        # return auth_check  # 未認証の場合、Google認証画面にリダイレクト
        # 未認証の場合でGoogle認証画面にリダイレクト後の戻り画面が指定できないためエラーに
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    # セッションに保存したアクセストークンを取得
    credentials_dict = request.session.get('google_credentials')
    if not credentials_dict:
        return JsonResponse({'error': 'User not authenticated'}, status=401)

    user_name = sv_get_user_name(request.user.user_id)

    # Google Calendar APIクライアントの作成
    service = get_calendar_service(credentials_dict)
    # this_year=ut_get_localtoday().year
    # this_month=ut_get_localtoday().month

    # Google Calendar APIを使ってイベントを取得
    events = get_calendar_events(service, year, month)

    # 勤怠データを収集
    attendance = process_work_events(events)    # 勤務イベントを日ごとに整理し、勤務時間を計算
    # attendance = create_attendance_data(events) # 勤務時間を個別に集計
    # 勤務表テンプレートを読み込み、出退勤情報を更新してメモリに保存
    output = update_attendance_to_excel(attendance, year, month, user_name)

    if not output:
        return JsonResponse({'error': 'データ作成中にエラーが発生しました。'}, status=500)
    logger.info(f'{ut_get_client_ip(request)} '
                f'export_work_schedule_to_excel {year}/{month}')

    # HTTPレスポンスでExcelを返す
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="work_schedule_{user_name}_{year}_{month}.xlsx"'
    # wb.save(response)
    response.write(output.getvalue())  # メモリからデータを書き込む
 
    return response
