import datetime as dt

from django import forms
from django.contrib.auth.forms import AuthenticationForm

#from .models import SubmitAttendance
from .models import (
    M_emp,
    M_kbn,
    M_yukyu,
    T_daily_report,
    T_request,
    T_request_rest,
    T_time_stamp,
)


class EvcLoginForm(AuthenticationForm):
    """ログオンフォーム"""
    # class AuthenticationForm(forms.Form):
    # username = UsernameField(widget=forms.TextInput(attrs={'autofocus': True}))
    # password = forms.CharField(
    #     label=_("Password"),
    #     strip=False,
    #     widget=forms.PasswordInput,
    # )
    username = forms.EmailField(label='メールアドレス', required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = field.label

class EditEmpForm(forms.ModelForm):
    class Meta:
        # モデルクラスを指定
        model = M_emp
        # 使用するモデルフィールドの指定(フォーム上で入力可能な項目として表示)
        fields = ('id','ltd_cd','emp_id','emp_name','kbn','emp_kana','user_id','tofuken_cd','add_1','work_pat_cd','tel_no','mobile_no','mail_add','sex','birthday','joined_date','memo')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # hidden属性のフィールドとして生成
        self.fields['id'].widget = forms.HiddenInput()

class ClockForm(forms.ModelForm):
    name_field = forms.CharField(label='氏名')

    class Meta:
        model = T_time_stamp
        fields = ('id','ltd_cd','emp_id','name_field','target_date')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['ltd_cd'].widget = forms.HiddenInput()
        self.fields['emp_id'].widget = forms.HiddenInput()
        self.fields['name_field'].widget = forms.HiddenInput()
        self.fields['target_date'].widget = forms.HiddenInput()

class TimeStampEditForm(forms.ModelForm):
    # 追加のフィールド
    date_field = forms.CharField(label='日付')
    kbns_cd = forms.ModelChoiceField(
        label='勤務区分',
        queryset=M_kbn.objects.filter(zokusei_cd=2).order_by('kbn_order'),
        to_field_name='kbn',
        empty_label=None)
    stat = forms.CharField(label='申請承認')
    class Meta:
        model = T_time_stamp
        fields = ('id','ltd_cd','emp_id','target_date','date_field','kbns_cd','kbn','corret_start_time','start_time','corret_end_time','end_time','stat')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['ltd_cd'].widget = forms.HiddenInput()
        self.fields['emp_id'].widget = forms.HiddenInput()
        self.fields['target_date'].widget = forms.HiddenInput()
        self.fields['kbn'].widget = forms.HiddenInput()
        # self.fields['corret_start_time'].widget.attrs['pattern'] = '^[0-9:]+$'
        self.fields['corret_start_time'].widget.attrs={
               'placeholder':'時:分(半角)',
               'pattern':'^[0-9:]+$'}
        self.fields['corret_end_time'].widget.attrs={
               'placeholder':'時:分(半角)',
               'pattern':'^[0-9:]+$'}
        self.fields['date_field'].widget.attrs['readonly'] = 'readonly'
        self.fields['start_time'].widget.attrs['readonly'] = 'readonly'
        self.fields['end_time'].widget.attrs['readonly'] = 'readonly'


    # clean()で複数のカラム（フィールド）によるバリデーション
    # clean()は特定のカラムに対してバリデーションが実行された後に実行
    def clean(self):
        kbn = self.cleaned_data['kbns_cd']
        if kbn.kbn == 2 or kbn.kbn == 3 or kbn.kbn == 5 or kbn.kbn == 7:
            return self.cleaned_data
        start_time = self.cleaned_data['corret_start_time']
        try:
            h = int(start_time.split(':')[0])
            m =  int(start_time.split(':')[1])
            start = dt.datetime(2000, 1, 1, h, m, 0)
            # td = dt.datetime.strptime(start_time, '%Y/%m/%d %H:%M:%S')
        except Exception:
            raise forms.ValidationError("正しい値を入力してください\n出社時刻不正")
        end_time = self.cleaned_data['corret_end_time']
        if end_time == None or end_time == '':
            return self.cleaned_data
        try:
            h = int(end_time.split(':')[0])
            m =  int(end_time.split(':')[1])
            end = dt.datetime(2000, 1, 1, h, m, 0)
            # td = dt.datetime.strptime(end_time, '%Y/%m/%d %H:%M:%S')
        except Exception:
            raise forms.ValidationError('正しい値を入力してください\n退社時刻不正')
        if start >= end:
            raise forms.ValidationError('正しい値を入力してください\n出社時刻は退社時刻より過去にする必要があります。')
        return self.cleaned_data
"""
    def clean_CORRET_START_TIME(self):
        start_time = self.cleaned_data['corret_start_time']
        try:
            h = int(start_time.split(':')[0])
            m =  int(start_time.split(':')[1])
            start = dt.datetime(2000, 1, 1, h, m, 0)
            #td = dt.datetime.strptime(start_time, '%Y/%m/%d %H:%M:%S')
        except ValueError as e:
            raise forms.ValidationError('catch TypeError:')
        except Exception as e:
            raise forms.ValidationError('Tags are not allowed.')
        return start_time
    def clean_CORRET_END_TIME(self):
        end_time = self.cleaned_data['corret_end_time']
        try:
            h = int(end_time.split(':')[0])
            m =  int(end_time.split(':')[1])
            start = dt.datetime(2000, 1, 1, h, m, 0)
            #td = dt.datetime.strptime(end_time, '%Y/%m/%d %H:%M:%S')
        except TypeError as e:
            raise forms.ValidationError('catch TypeError:')
        except Exception as e:
            raise forms.ValidationError('Tags are not allowed.')
        return end_time
"""
class TimeStampEdit2Form(forms.ModelForm):

    class Meta:
        model = T_time_stamp
        fields = ('id','ltd_cd','emp_id','target_date','i_do','ke_id')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['ltd_cd'].widget = forms.HiddenInput()
        self.fields['emp_id'].widget = forms.HiddenInput()
        self.fields['target_date'].widget = forms.HiddenInput()

class RequestEditForm(forms.ModelForm):
    # 追加のフィールド
    stat = forms.CharField(label='申請承認')

    class Meta:
        model = T_request
        # fields = ('id','ltd_cd','emp_id','target_date',
        #           'expenses','memo','agree_comment','stat')
        fields = ('expenses','memo','agree_comment')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['id'].widget = forms.HiddenInput()
        # self.fields['ltd_cd'].widget = forms.HiddenInput()
        # self.fields['emp_id'].widget = forms.HiddenInput()
        # self.fields['target_date'].widget = forms.HiddenInput()
        # self.fields['stat'].widget.attrs['readonly'] = 'readonly'

# RequestRestFormset = forms.inlineformset_factory(
#     T_request,T_request_rest,
#     fields = ('rest_start_time','rest_start_next_flg','rest_end_time','rest_end_next_flg'),
#     extra=1, can_delete=False
# )
class RequestRestForm(forms.ModelForm):
    # start = forms.CharField(label='開始',max_length=5)
    # end = forms.CharField(label='終了',max_length=5)

    # start_check = forms.BooleanField(label='翌日')
    # end_check = forms.BooleanField(label='翌日')
    class Meta:
        model = T_request_rest
        fields = ('id','ltd_cd','emp_id','target_date','rest_no',
                  # 'start','start_check','end','end_check',
                  'rest_start_time','rest_start_next_flg','rest_end_time','rest_end_next_flg')
        # widgets = {
        #     'rest_start_time': forms.CharField(label='開始',max_length=5),
        #     'rest_end_time': forms.CharField(label='開始',max_length=5),
        #     'rest_start_next_flg' : forms.BooleanField(label='翌日'),
        #     'rest_end_next_flg' : forms.BooleanField(label='翌日'),
        # }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # for field in self.fields.values():
        #     field.widget.attrs['class'] = 'form-control'
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['ltd_cd'].widget = forms.HiddenInput()
        self.fields['emp_id'].widget = forms.HiddenInput()
        self.fields['target_date'].widget = forms.HiddenInput()
        self.fields['rest_no'].widget = forms.HiddenInput()
        # self.fields['rest_start_time'].widget = forms.CharField(label='開始',max_length=5)
        # self.fields['rest_start_next_flg'].widget = forms.BooleanField(label='翌日')
        # self.fields['rest_end_time'].widget = forms.CharField(label='終了',max_length=5)
        # self.fields['rest_end_next_flg'].widget =forms.BooleanField(label='翌日')

RequestRestFormset = forms.modelformset_factory(
    T_request_rest,
    form=RequestRestForm,
    extra=1
)

class DailyReportEditForm(forms.ModelForm):
    # 追加のフィールド
    date_field = forms.CharField(label='日付')

    class Meta:
        model = T_daily_report

        fields = ('id','ltd_cd','emp_id','target_date',
                  'date_field',
                  # 'TORIHIKISAKI','PROJECT','GYOMU',
                  'report',
                  # 'GYOMU_YOTEI_TIME','GYOMU_JISEKI_TIME',
                  'com_ltd_cd', 'com_emp_id','comment'
                  )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['ltd_cd'].widget = forms.HiddenInput()
        # self.fields['emp_id'].widget = forms.HiddenInput()
        self.fields['emp_id'].widget.attrs['readonly'] = 'readonly'
        self.fields['target_date'].widget = forms.HiddenInput()
        self.fields['date_field'].widget.attrs['readonly'] = 'readonly'
        self.fields['com_ltd_cd'].widget.attrs['readonly'] = 'readonly'
        self.fields['com_emp_id'].widget.attrs['readonly'] = 'readonly'
        self.fields['comment'].widget.attrs['readonly'] = 'readonly'

# class GetujiKintaiForm(forms.ModelForm):
#     class Meta():
#         model = T_getuji_kintai
#         fields = ('id','ltd_cd','emp_id','target_date',
#                 'shotei_count','work_count','hoteigai_work_count','kekkin_count','late_count','early_count',
#                 'all_work_time','jitu_work_time','overtime_time','hoteikyu_time','midnight_time',
#                 'late_time','early_time','shotei_less_time','holiday_count','yukyu_count','yukyu_zan_count',
#                 'kakikyu_count','kakikyu_zan_count','furikyu_count','furikyu_zan_count','daikyu_count','daikyu_zan_count',
#                 'kyushoku_count','month_yukyu_count','month_kakikyu_count')
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['id'].widget = forms.HiddenInput()
#         self.fields['ltd_cd'].widget = forms.HiddenInput()
#         self.fields['emp_id'].widget = forms.HiddenInput()
#         self.fields['target_date'].widget = forms.HiddenInput()

# class SubmitAttendanceForm(forms.ModelForm):
#     class Meta:
#         model = SubmitAttendance
#         fields = ('place', 'in_out')

# 勤怠承認
class ApprovalForm(forms.Form):
    # 出退勤区分
    name = forms.fields.ChoiceField(
        choices = (
            ('1', 'name1'),
            ('2', 'name2')
        ),
        required=False,
        widget=forms.widgets.Select
    )

    # 出退勤区分
    kbn = forms.fields.ChoiceField(
        choices = (
            ('1', 'Kbn1'),
            ('2', 'Kbn2')
        ),
        required=False,
        widget=forms.widgets.Select
    )
    scope = forms.fields.ChoiceField(
        choices = (
            ('1', 'Scope1'),
            ('2', 'Scope2')
        ),
        required=False,
        widget=forms.widgets.Select
    )
    katsudo = forms.fields.ChoiceField(
        choices = (
            ('1', 'Katsudo1'),
            ('2', 'Katsudo2')
        ),
        required=False,
        widget=forms.widgets.Select
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PaidHolidayEditForm(forms.ModelForm):
    # 追加のフィールド
    date_field = forms.CharField(label='日付')

    class Meta:
        model = M_yukyu

        fields = ('id','ltd_cd','emp_id','nendo',
                    'new_count','carry_over','all_count','used_count'
                  )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['ltd_cd'].widget = forms.HiddenInput()
        # self.fields['emp_id'].widget = forms.HiddenInput()
        self.fields['emp_id'].widget.attrs['readonly'] = 'readonly'
        self.fields['nendo'].widget.attrs['readonly'] = 'readonly'
        self.fields['new_count'].widget.attrs['readonly'] = 'readonly'
        self.fields['carry_over'].widget.attrs['readonly'] = 'readonly'
        self.fields['all_count'].widget.attrs['readonly'] = 'readonly'
        self.fields['used_count'].widget = forms.HiddenInput()
