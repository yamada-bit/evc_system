import calendar
import datetime
from collections import deque
# import itertools
# from django import forms
from django.utils import timezone

class BaseCalendarMixin:
    """カレンダー関連Mixinの、基底クラス"""
    first_weekday = 6  # 0は月曜から、1は火曜から。6なら日曜日からになります。
    week_names = ['月', '火', '水', '木', '金', '土', '日'] 

    def setup_calendar(self):
        """内部カレンダーの設定処理

        calendar.Calendarクラスの機能を利用するため、インスタンス化します。
        Calendarクラスのmonthdatescalendarメソッドを利用していますが、デフォルトが月曜日からで、
        火曜日から表示したい場合(first_weekday=1)、といったケースに対応するためのセットアップ処理

        """
        self._calendar = calendar.Calendar(self.first_weekday)

    def get_week_names(self):
        """first_weekday(最初に表示される曜日)にあわせて、week_namesをシフトする"""
        week_names = deque(self.week_names)
        week_names.rotate(-self.first_weekday)
        return week_names

"""月間カレンダーの機能を提供するMixin"""
class MonthCalendarMixin(BaseCalendarMixin):

    def get_previous_month(self, date):
        """前月を返す"""
        if date.month == 1:
            return date.replace(year=date.year-1, month=12, day=1)
        else:
            return date.replace(month=date.month-1, day=1)

    def get_next_month(self, date):
        """次月を返す"""
        if date.month == 12:
            return date.replace(year=date.year+1, month=1, day=1)
        else:
            return date.replace(month=date.month+1, day=1)

    def get_month_days(self, date):
        """その月の全ての日を返す"""
        # year 年 month 月の週のリストを返します。
        # 週は全て七つの datetime.date オブジェクトからなるリスト
        # [datetime.date(2025, 2, 23), datetime.date(2025, 2, 24), datetime.date(2025, 2, 25), datetime.date(2025, 2, 26), datetime.date(2025, 2, 27), datetime.date(2025, 2, 28), datetime.date(2025, 3, 1)]
        # [datetime.date(2025, 3, 2), datetime.date(2025, 3, 3), datetime.date(2025, 3, 4), datetime.date(2025, 3, 5), datetime.date(2025, 3, 6), datetime.date(2025, 3, 7), datetime.date(2025, 3, 8)]
        return self._calendar.monthdatescalendar(date.year, date.month)

    def get_month_days2(self, year, month):
        """その月の全ての週の日付と曜日のタプルからなるリストを返す"""
        # year 年 month 月の週のリストを返します。
        # 週は全て七つの日付の数字と曜日を表す数字のタプルからなるリスト
        # タプルを要素とするカレンダーをリストで取得できる。
        # 各タプルは(日付, 曜日)の値を持つ。存在しない日付は0
        # [(0, 6), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 5)]
        # [(2, 6), (3, 0), (4, 1), (5, 2), (6, 3), (7, 4), (8, 5)]
        return self._calendar.monthdays2calendar(year, month)
        #days2 = self._calendar.monthdays2calendar(date.year, date.month)
        #days_list = []
        #for week in days2:
        #    for day in week:
        #        if (day[0] != 0):
        #            days_list.append({'w':self.week_names[day[1]], 'd':str(day[0]).zfill(2),})

        #return days_list

    def get_month_range(self, date):
        # year と month で指定された月の (月の初日の曜日, 月の日数)のタプルを返す
        # 例(5, 31) 5は土曜日、31はその月の日数
        month_days = calendar.monthrange(date.year, date.month)
        #month_days = range(calendar.monthrange(date.year, date.month)[1])
        return month_days
 
    def get_current_month(self, year, month):
        """現在の月を返す"""
        if month and year:
            month = datetime.date(year=int(year), month=int(month), day=1)
        else:
            month = timezone.localdate().replace(day=1)
        return month
    # 任意の日付（datetime, date）の月の最終日
    def get_last_date(self, date):
        return date.replace(day=calendar.monthrange(date.year, date.month)[1])

    def get_month_calendar(self, year, month):
        """月間カレンダー情報の入った辞書を返す"""
        self.setup_calendar()
        current_month = self.get_current_month(year, month)
        calendar_data = {
            'now': timezone.localdate(),
            'month_days': self.get_month_days(current_month),
            'month_current': current_month,
            'month_previous': self.get_previous_month(current_month),
            'month_next': self.get_next_month(current_month),
            'week_names': self.get_week_names(),
        }
        return calendar_data
