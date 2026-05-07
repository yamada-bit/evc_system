import os
import datetime
from django import forms
from django.contrib.auth.forms import AuthenticationForm,UserCreationForm
from users.models import EvcUser,SysOwner,MtPartner,MtFolder

# from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
# from django.utils.translation import gettext as _

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']

# def check_email(value):
#     try:
#         if value:
#             validate_email(value)
#             return True
#     except ValidationError:
#         pass
#         # raise ValidationError('Email error.')
#     return False
def check_ym(ym):
    if ym:
        dt = ym.replace('/', '').replace('-', '')
        if 6 < len(dt):
            return False
        if len(dt) == 5:
            dt = dt[:4] + '0' + dt[-1]
        try:
            bom = datetime.datetime.strptime(dt + '01','%Y%m%d')
            ym = bom.strftime('%Y%m')
            return ym
        except Exception:
            return False
    return False

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

# ファイルアップロード
class UploadReportForm(forms.Form):
    # title = forms.CharField(max_length=50)
    # file = forms.FileField()
    # 複数のファイルをアップロード
    # file = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))
    file = MultipleFileField()

    def clean_file(self):
        files = self.files.getlist('file')
        file = self.cleaned_data['file']
        for f in files:
            extension = os.path.splitext(f.name)[1]  # 拡張子を取得
            if not extension.lower() in VALID_EXTENSIONS:
                raise forms.ValidationError(f.name + ' ファイル形式が正しくありません')
        return file
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
# 外勤報告書情報一覧表示
class ReportListForm(forms.Form):
    # report_month = forms.CharField(
    #     required=False,
    #     max_length=7,
    #     widget=forms.TextInput(attrs={
    #         'placeholder': 'yyyy/mm',
    #         'type': 'text',
    #         'size': 7,
    #     })
    # )
    report_month = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )

    page_size = forms.CharField(required=False, widget=forms.HiddenInput)

    page_size_choice = forms.fields.ChoiceField(
        label='表示件数',
        choices=(
            (1, '1'),
            (5, '5'),
            (10, '10'),
            (50, '50'),
            (100, '100'),
        ),
        # initial=10,
        required=False,
        widget=forms.widgets.Select
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['page_size'].initial = 10
        # for field in self.fields.values():
        #     field.widget.attrs['class'] = 'form-control'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'

    def clean_report_month(self):
        report_month = self.cleaned_data['report_month']
        if report_month:
            report_month = check_ym(report_month)
            if not report_month:
                raise forms.ValidationError('年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if report_month < '200001':
                raise forms.ValidationError('年月は2000年1月以降を入力してください')
        return report_month

# 情報編集画面
class EditReportForm(forms.Form):
    report_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            'disabled': 'disabled',
        })
    )
    report_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'report_name',
            'type': 'search',
            'size': 50,
        })
    )
    processed_ym = forms.CharField(
        max_length=6,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 6,
        })
    )

    report_month = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'report_notes',
        })
    )
    def __init__(self, categories=None, *args, **kwargs):
        if categories:
            self.base_fields['category'].choices = categories
        super().__init__(*args, **kwargs)
    def clean_report_month(self):
        report_month = self.cleaned_data['report_month']
        if report_month:
            report_month = check_ym(report_month)
            if not report_month:
                raise forms.ValidationError('年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if report_month < '200001':
                raise forms.ValidationError('年月は2000年1月以降を入力してください')
        return report_month
