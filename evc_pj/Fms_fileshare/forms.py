
# from .models import SharedFile
import os

from django import forms

# from django.core.validators import validate_email
# from django.utils.translation import gettext as _
from Evc_App.forms import MultipleFileField, check_ym

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
# class FileUploadForm(forms.ModelForm):
#     class Meta:
#         model = SharedFile
#         fields = ['file']

# ファイルアップロード
class FileUploadForm(forms.Form):
    # title = forms.CharField(max_length=50)
    # file = forms.FileField()
    # 複数のファイルをアップロード
    # file = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))
    file = MultipleFileField()
    shared_types = forms.ChoiceField(
        label='区分',
        required=False,
        widget=forms.RadioSelect,
        choices=(
            (1, '重要'),
            (2, '通知（会社）'),
            (3, '共有（一般）'),
        ),
        # choices=(
        #     ('important', '重要'),
        #     ('notice', '通知（会社）'),
        #     ('share', '共有（一般）'),
        # ),
        initial=3
    )

    def clean_file(self):
        files = self.files.getlist('file')
        file = self.cleaned_data['file']
        for f in files:
            extension = os.path.splitext(f.name)[1]  # 拡張子を取得
            if extension.lower() not in VALID_EXTENSIONS:
                raise forms.ValidationError(f.name + ' ファイル形式が正しくありません')
        return file
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# 一覧表示
class FileListForm(forms.Form):
    # shared_month = forms.CharField(
    #     required=False,
    #     max_length=7,
    #     widget=forms.TextInput(attrs={
    #         'placeholder': 'yyyy/mm',
    #         'type': 'text',
    #         'size': 7,
    #     })
    # )
    # shared_month = forms.CharField(
    #     required=True,
    #     widget=forms.TextInput(attrs={
    #         'type': 'month',
    #         'min': '2000-01'
    #     })
    # )
    process_date1 = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    process_date2 = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    category = forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select
    )
    shared_type = forms.fields.ChoiceField(
        required=False,
        choices=(
            (0, ''),
            (1, '重要'),
            (2, '通知（会社）'),
            (3, '共有（一般）'),
        ),
        # choices=(
        #     ('none', ''),
        #     ('important', '重要'),
        #     ('notice', '通知（会社）'),
        #     ('share', '共有（一般）'),
        # ),
        widget=forms.widgets.Select
    )
    shared_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 25,
        })
    )
    file_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 25,
        })
    )
    uploader_cd = forms.ChoiceField(
        widget=forms.widgets.Select,
        required=False
    )
    uploader = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 25,
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

    def clean_shared_month(self):
        shared_month = self.cleaned_data['shared_month']
        if shared_month:
            shared_month = check_ym(shared_month)
            if not shared_month:
                raise forms.ValidationError('年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if shared_month < '200001':
                raise forms.ValidationError('年月は2000年1月以降を入力してください')
        return shared_month

# 編集画面
class FileEditForm(forms.Form):
    shared_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            'disabled': 'disabled',
        })
    )
    shared_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'shared_name',
            'type': 'search',
            'size': 50,
        })
    )
    shared_type = forms.fields.ChoiceField(
        required=False,
        choices=(
            # ('0', ''),
            (1, '重要'),
            (2, '通知（会社）'),
            (3, '共有（一般）'),
        ),
        # choices=(
        #     ('none', ''),
        #     ('important', '重要'),
        #     ('notice', '通知（会社）'),
        #     ('share', '共有（一般）'),
        # ),
        widget=forms.widgets.Select
    )
    # processed_ym = forms.CharField(
    #     max_length=6,
    #     required=False,
    #     widget=forms.TextInput(attrs={
    #         'type': 'search',
    #         'size': 6,
    #     })
    # )

    # shared_month = forms.CharField(
    #     required=True,
    #     widget=forms.TextInput(attrs={
    #         'type': 'month',
    #         'min': '2000-01'
    #     })
    # )
    shared_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'size': 10,
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shared_notes',
        })
    )
    def __init__(self, categories=None, *args, **kwargs):
        if categories:
            self.base_fields['category'].choices = categories
        super().__init__(*args, **kwargs)
    def clean_shared_month(self):
        shared_month = self.cleaned_data['shared_month']
        if shared_month:
            shared_month = check_ym(shared_month)
            if not shared_month:
                raise forms.ValidationError('年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if shared_month < '200001':
                raise forms.ValidationError('年月は2000年1月以降を入力してください')
        return shared_month
