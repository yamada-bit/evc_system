import datetime
import os

from django import forms
from django.contrib.auth.forms import AuthenticationForm


class AttendanceLoginForm(AuthenticationForm):
    """ログオンフォーム"""
    username = forms.EmailField(label='メールアドレス', required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = field.label


# ---------------------------------------------------------------------------
# 外勤報告書フォーム（旧 Kms_Calendar/forms.py から移植）
# ---------------------------------------------------------------------------

_GAIKIN_VALID_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff']


def _check_ym(ym: str) -> str | bool:
    """YYYY-MM または YYYYMM 形式の文字列を YYYYMM 形式に正規化して返す。不正な場合は False。"""
    if ym:
        dt = ym.replace('/', '').replace('-', '')
        if len(dt) > 6:
            return False
        if len(dt) == 5:
            dt = dt[:4] + '0' + dt[-1]
        try:
            bom = datetime.datetime.strptime(dt + '01', '%Y%m%d')
            return bom.strftime('%Y%m')
        except Exception:
            return False
    return False


class _MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class _MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', _MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)


class GaikinUploadForm(forms.Form):
    """外勤報告書ファイルアップロードフォーム（複数ファイル対応）。"""
    file = _MultipleFileField(label='ファイル')

    def clean_file(self):
        files = self.files.getlist('file')
        file = self.cleaned_data['file']
        for f in files:
            ext = os.path.splitext(f.name)[1]
            if ext.lower() not in _GAIKIN_VALID_EXTENSIONS:
                raise forms.ValidationError(f'{f.name} はサポートされていないファイル形式です。')
        return file


class GaikinListForm(forms.Form):
    """外勤報告書一覧の検索フォーム。"""
    report_month = forms.CharField(
        label='処理年月',
        required=True,
        widget=forms.TextInput(attrs={'type': 'month', 'min': '2000-01'}),
    )
    page_size = forms.CharField(required=False, widget=forms.HiddenInput)
    page_size_choice = forms.ChoiceField(
        label='表示件数',
        choices=[(1, '1'), (5, '5'), (10, '10'), (50, '50'), (100, '100')],
        required=False,
    )

    def clean_report_month(self):
        val = self.cleaned_data['report_month']
        normalized = _check_ym(val)
        if not normalized:
            raise forms.ValidationError('年月を正しく入力してください（例: 2026-06）')
        if normalized < '200001':
            raise forms.ValidationError('年月は2000年1月以降を入力してください')
        return normalized


class GaikinEditForm(forms.Form):
    """外勤報告書情報編集フォーム。"""
    report_id   = forms.CharField(widget=forms.HiddenInput)
    report_name = forms.CharField(max_length=50, required=False, label='報告書名',
                                  widget=forms.TextInput(attrs={'size': 50}))
    report_month = forms.CharField(
        label='処理年月',
        required=True,
        widget=forms.TextInput(attrs={'type': 'month', 'min': '2000-01'}),
    )
    notes = forms.CharField(required=False, label='備考', widget=forms.Textarea(attrs={'rows': 3}))

    def clean_report_month(self):
        val = self.cleaned_data['report_month']
        normalized = _check_ym(val)
        if not normalized:
            raise forms.ValidationError('年月を正しく入力してください（例: 2026-06）')
        if normalized < '200001':
            raise forms.ValidationError('年月は2000年1月以降を入力してください')
        return normalized
