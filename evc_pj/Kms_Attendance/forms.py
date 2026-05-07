from django import forms
from django.contrib.auth.forms import AuthenticationForm

#from .models import SubmitAttendance
from .models import M_emp,T_time_stamp,T_request,T_request_rest,M_kbn,T_daily_report,M_yukyu
import datetime as dt

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
    class Meta():
        # モデルクラスを指定
        model = M_emp
        # 使用するモデルフィールドの指定(フォーム上で入力可能な項目として表示)
        fields = ('id','LTD_CD','EMP_ID','EMP_NAME','KBN','EMP_KANA','user_id','TDFUKEN_CD','ADD_1','WORK_PAT_CD','TEL_NO','MOBILE_NO','MAIL_ADD','SEX','BIRTHDAY','JOINED_DATE','MEMO')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # hidden属性のフィールドとして生成
        self.fields['id'].widget = forms.HiddenInput()

class ClockForm(forms.ModelForm):
    name_field = forms.CharField(label='氏名')

    class Meta():
        model = T_time_stamp
        fields = ('id','LTD_CD','EMP_ID','name_field','TARGET_DATE')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['LTD_CD'].widget = forms.HiddenInput()
        self.fields['EMP_ID'].widget = forms.HiddenInput()
        self.fields['name_field'].widget = forms.HiddenInput()
        self.fields['TARGET_DATE'].widget = forms.HiddenInput()

class TimeStampEditForm(forms.ModelForm):
    # 追加のフィールド
    date_field = forms.CharField(label='日付')
    kbns_cd = forms.ModelChoiceField(
        label='勤務区分',
        queryset=M_kbn.objects.filter(ZOKUSEI_CD=2).order_by('KBN_ORDER'),
        to_field_name='KBN',
        empty_label=None)
    stat = forms.CharField(label='申請承認')
    class Meta():
        model = T_time_stamp
        fields = ('id','LTD_CD','EMP_ID','TARGET_DATE','date_field','kbns_cd','KBN','CORRET_START_TIME','START_TIME','CORRET_END_TIME','END_TIME','stat')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['LTD_CD'].widget = forms.HiddenInput()
        self.fields['EMP_ID'].widget = forms.HiddenInput()
        self.fields['TARGET_DATE'].widget = forms.HiddenInput()
        self.fields['KBN'].widget = forms.HiddenInput()
        # self.fields['CORRET_START_TIME'].widget.attrs['pattern'] = '^[0-9:]+$'
        self.fields['CORRET_START_TIME'].widget.attrs={
               'placeholder':'時:分(半角)',
               'pattern':'^[0-9:]+$'}
        self.fields['CORRET_END_TIME'].widget.attrs={
               'placeholder':'時:分(半角)',
               'pattern':'^[0-9:]+$'}
        self.fields['date_field'].widget.attrs['readonly'] = 'readonly'
        self.fields['START_TIME'].widget.attrs['readonly'] = 'readonly'
        self.fields['END_TIME'].widget.attrs['readonly'] = 'readonly'


    # clean()で複数のカラム（フィールド）によるバリデーション
    # clean()は特定のカラムに対してバリデーションが実行された後に実行
    def clean(self):
        kbn = self.cleaned_data['kbns_cd']
        if kbn.KBN == 2 or kbn.KBN == 3 or kbn.KBN == 5 or kbn.KBN == 7:
            return self.cleaned_data
        start_time = self.cleaned_data['CORRET_START_TIME']
        try:
            h = int(start_time.split(':')[0])
            m =  int(start_time.split(':')[1])
            start = dt.datetime(2000, 1, 1, h, m, 0)
            # td = dt.datetime.strptime(start_time, '%Y/%m/%d %H:%M:%S')
        except Exception as e:
            raise forms.ValidationError("正しい値を入力してください\n出社時刻不正")
        end_time = self.cleaned_data['CORRET_END_TIME']
        if end_time == None or end_time == '':
            return self.cleaned_data
        try:
            h = int(end_time.split(':')[0])
            m =  int(end_time.split(':')[1])
            end = dt.datetime(2000, 1, 1, h, m, 0)
            # td = dt.datetime.strptime(end_time, '%Y/%m/%d %H:%M:%S')
        except Exception as e:
            raise forms.ValidationError('正しい値を入力してください\n退社時刻不正')
        if start >= end:
            raise forms.ValidationError('正しい値を入力してください\n出社時刻は退社時刻より過去にする必要があります。')
        return self.cleaned_data
"""
    def clean_CORRET_START_TIME(self):
        start_time = self.cleaned_data['CORRET_START_TIME']
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
        end_time = self.cleaned_data['CORRET_END_TIME']
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

    class Meta():
        model = T_time_stamp
        fields = ('id','LTD_CD','EMP_ID','TARGET_DATE','I_DO','KE_ID')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['LTD_CD'].widget = forms.HiddenInput()
        self.fields['EMP_ID'].widget = forms.HiddenInput()
        self.fields['TARGET_DATE'].widget = forms.HiddenInput()

class RequestEditForm(forms.ModelForm):
    # 追加のフィールド
    stat = forms.CharField(label='申請承認')

    class Meta():
        model = T_request
        # fields = ('id','LTD_CD','EMP_ID','TARGET_DATE',
        #           'EXPENSES','MEMO','AGREE_COMMENT','stat')
        fields = ('EXPENSES','MEMO','AGREE_COMMENT')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['id'].widget = forms.HiddenInput()
        # self.fields['LTD_CD'].widget = forms.HiddenInput()
        # self.fields['EMP_ID'].widget = forms.HiddenInput()
        # self.fields['TARGET_DATE'].widget = forms.HiddenInput()
        # self.fields['stat'].widget.attrs['readonly'] = 'readonly'

# RequestRestFormset = forms.inlineformset_factory(
#     T_request,T_request_rest,
#     fields = ('REST_START_TIME','REST_START_NEXT_FLG','REST_END_TIME','REST_END_NEXT_FLG'),
#     extra=1, can_delete=False
# )
class RequestRestForm(forms.ModelForm):
    # start = forms.CharField(label='開始',max_length=5)
    # end = forms.CharField(label='終了',max_length=5)

    # start_check = forms.BooleanField(label='翌日')
    # end_check = forms.BooleanField(label='翌日')
    class Meta():
        model = T_request_rest
        fields = ('id','LTD_CD','EMP_ID','TARGET_DATE','REST_NO',
                  # 'start','start_check','end','end_check',
                  'REST_START_TIME','REST_START_NEXT_FLG','REST_END_TIME','REST_END_NEXT_FLG')
        # widgets = {
        #     'REST_START_TIME': forms.CharField(label='開始',max_length=5),
        #     'REST_END_TIME': forms.CharField(label='開始',max_length=5),
        #     'REST_START_NEXT_FLG' : forms.BooleanField(label='翌日'),
        #     'REST_END_NEXT_FLG' : forms.BooleanField(label='翌日'),
        # }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # for field in self.fields.values():
        #     field.widget.attrs['class'] = 'form-control'
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['LTD_CD'].widget = forms.HiddenInput()
        self.fields['EMP_ID'].widget = forms.HiddenInput()
        self.fields['TARGET_DATE'].widget = forms.HiddenInput()
        self.fields['REST_NO'].widget = forms.HiddenInput()
        # self.fields['REST_START_TIME'].widget = forms.CharField(label='開始',max_length=5)
        # self.fields['REST_START_NEXT_FLG'].widget = forms.BooleanField(label='翌日')
        # self.fields['REST_END_TIME'].widget = forms.CharField(label='終了',max_length=5)
        # self.fields['REST_END_NEXT_FLG'].widget =forms.BooleanField(label='翌日')

RequestRestFormset = forms.modelformset_factory(
    T_request_rest,
    form=RequestRestForm,
    extra=1
)

class DailyReportEditForm(forms.ModelForm):
    # 追加のフィールド
    date_field = forms.CharField(label='日付')

    class Meta():
        model = T_daily_report

        fields = ('id','LTD_CD','EMP_ID','TARGET_DATE',
                  'date_field',
                  # 'TORIHIKISAKI','PROJECT','GYOMU',
                  'REPORT',
                  # 'GYOMU_YOTEI_TIME','GYOMU_JISEKI_TIME',
                  'COM_LTD_CD', 'COM_EMP_ID','COMMENT'
                  )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['LTD_CD'].widget = forms.HiddenInput()
        # self.fields['EMP_ID'].widget = forms.HiddenInput()
        self.fields['EMP_ID'].widget.attrs['readonly'] = 'readonly'
        self.fields['TARGET_DATE'].widget = forms.HiddenInput()
        self.fields['date_field'].widget.attrs['readonly'] = 'readonly'
        self.fields['COM_LTD_CD'].widget.attrs['readonly'] = 'readonly'
        self.fields['COM_EMP_ID'].widget.attrs['readonly'] = 'readonly'
        self.fields['COMMENT'].widget.attrs['readonly'] = 'readonly'

# class GetujiKintaiForm(forms.ModelForm):
#     class Meta():
#         model = T_getuji_kintai
#         fields = ('id','LTD_CD','EMP_ID','TARGET_DATE',
#                 'SHOTEI_COUNT','WORK_COUNT','HOTEIGAI_WORK_COUNT','KEKKIN_COUNT','LATE_COUNT','EARLY_COUNT',
#                 'ALL_WORK_TIME','JITU_WORK_TIME','OVERTIME_TIME','HOTEIKYU_TIME','MIDNIGHT_TIME',
#                 'LATE_TIME','EARLY_TIME','SHOTEI_LESS_TIME','HOLIDAY_COUNT','YUKYU_COUNT','YUKYU_ZAN_COUNT',
#                 'KAKIKYU_COUNT','KAKIKYU_ZAN_COUNT','FURIKYU_COUNT','FURIKYU_ZAN_COUNT','DAIKYU_COUNT','DAIKYU_ZAN_COUNT',
#                 'KYUSHOKU_COUNT','MONTH_YUKYU_COUNT','MONTH_KAKIKYU_COUNT')
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['id'].widget = forms.HiddenInput()
#         self.fields['LTD_CD'].widget = forms.HiddenInput()
#         self.fields['EMP_ID'].widget = forms.HiddenInput()
#         self.fields['TARGET_DATE'].widget = forms.HiddenInput()

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

    class Meta():
        model = M_yukyu

        fields = ('id','LTD_CD','EMP_ID','NENDO',
                    'NEW_COUNT','CARRY_OVER','ALL_COUNT','USED_COUNT'
                  )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id'].widget = forms.HiddenInput()
        self.fields['LTD_CD'].widget = forms.HiddenInput()
        # self.fields['EMP_ID'].widget = forms.HiddenInput()
        self.fields['EMP_ID'].widget.attrs['readonly'] = 'readonly'
        self.fields['NENDO'].widget.attrs['readonly'] = 'readonly'
        self.fields['NEW_COUNT'].widget.attrs['readonly'] = 'readonly'
        self.fields['CARRY_OVER'].widget.attrs['readonly'] = 'readonly'
        self.fields['ALL_COUNT'].widget.attrs['readonly'] = 'readonly'
        self.fields['USED_COUNT'].widget = forms.HiddenInput()
