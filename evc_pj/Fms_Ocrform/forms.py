import datetime
import os

from django import forms

# from django.core.exceptions import ValidationError

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']

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

# ファイルアップロード
class EvcSaveOcrformForm(forms.Form):
    # title = forms.CharField(max_length=50)
    file = forms.FileField()
    # 複数のファイルをアップロード
    # file = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

    def clean_file(self):
        files = self.files.getlist('file')
        file = self.cleaned_data['file']
        for f in files:
            extension = os.path.splitext(f.name)[1]  # 拡張子を取得
            if extension.lower() not in VALID_EXTENSIONS:
                raise forms.ValidationError(f.name + ' ファイル形式が正しくありません')
        return file
# フォーム編集画面
class EvcEditOcrformForm(forms.Form):
    postext = forms.CharField(required=False, widget=forms.HiddenInput)
    pagebtn = forms.CharField(required=False, widget=forms.HiddenInput)

    # ocrform_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            # 'disabled': 'disabled',
        })
    )
# フォーム一覧表示画面
class EvcOcrformListForm(forms.Form):
    name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'フォーム名を入力',
            'type': 'text',
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
class EvcUploadEntryForm(forms.Form):
    # title = forms.CharField(max_length=50)
    # file = forms.FileField()
    # 複数のファイルをアップロード
    # file = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))
    file = MultipleFileField()
    evidence_kubuns = forms.ChoiceField(
        label='エビデンス区分',
        required=False,
        widget=forms.RadioSelect,
        choices=(
            ('page', 'ページごと'),
            ('file', '全ページ一括'),
            ('specif', 'ページ指定'),
        ),
        initial='page'
    )
    specif = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '例: 1,3-5',
            'type': 'text',
            'pattern': '^[0-9-,]+$',
            'size': 20,
        })
    )

    ocrform =forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select,
    )

    def clean_file(self):
        files = self.files.getlist('file')
        file = self.cleaned_data['file']
        for f in files:
            extension = os.path.splitext(f.name)[1]  # 拡張子を取得
            if extension.lower() not in VALID_EXTENSIONS:
                raise forms.ValidationError(f.name + ' ファイル形式が正しくありません')
        return file
    def __init__(self, ocrforms=None, *args, **kwargs):
        if ocrforms:
            self.base_fields['ocrform'].choices = ocrforms
        super().__init__(*args, **kwargs)

# エントリー一覧表示画面
class EvcEntryListForm(forms.Form):
    pdf_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'ファイル名*',
            'type': 'text',
        })
    )
    shori_date = forms.CharField(
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs={
            'placeholder': 'yyyy/mm',
            'type': 'text',
            'size': 7,
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
    def check_ym(self, ym):
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


    def clean_shori_date(self):
        shori_date = self.cleaned_data['shori_date']
        if shori_date:
            shori_date = check_ym(shori_date)
            if not shori_date:
                raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
        return shori_date
# エントリー編集画面
class EvcEditEntryForm(forms.Form):
    ocrdata_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            # 'disabled': 'disabled',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# 勤務表一覧表示画面
class EvcTimesheetListForm(forms.Form):
    office_cd = forms.ChoiceField(
        widget=forms.widgets.Select,
        required=False
    )
    office = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 25,
        })
    )
    # emp_id = forms.CharField(
    #     max_length=50,
    #     required=False,
    #     widget=forms.TextInput(attrs={
    #         'type': 'search',
    #         'size': 25,
    #     })
    # )
    # emp_id_cd = forms.ChoiceField(
    #     widget=forms.widgets.Select,
    #     required=False
    # )
    # shori_date = forms.CharField(
    #     required=False,
    #     max_length=7,
    #     widget=forms.TextInput(attrs={
    #         'placeholder': 'yyyy/mm',
    #         'type': 'text',
    #         'size': 7,
    #     })
    # )
    shori_date = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )
    create_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    category = forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select
    )
    # partner_cd = forms.ModelChoiceField(queryset=MtPartner.objects.all().order_by('partner_id'))
    # partner = forms.CharField(
    #     max_length=50,
    #     required=False,
    #     widget=forms.TextInput(attrs={
    #         'placeholder': '取引先を入力*',
    #         'type': 'text',
    #     })
    # )
    office_name = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '事業所名を入力*',
            'type': 'text',
        })
    )
    emp_id = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '社員コードを入力*',
            'type': 'text',
        })
    )
    emp_name = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '氏名を入力*',
            'type': 'text',
        })
    )
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

    # class Meta:
    #     model = TtEvidence
    #     fields = ['pdf_name', 'processed_date', 'category_name',
    #     'total_amount','partner_name',
    #     'create_date','result']
    #     # fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['page_size'].initial = 10
        # for field in self.fields.values():
        #     field.widget.attrs['class'] = 'form-control'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'

    def clean_shori_date(self):
        shori_date = self.cleaned_data['shori_date']
        if shori_date:
            shori_date = check_ym(shori_date)
            if not shori_date:
                raise forms.ValidationError('処理年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if shori_date < '200001':
                raise forms.ValidationError('処理年月は2000年1月以降を入力してください')
        return shori_date


# 検索条件編集画面
class EvcEditTimesheetForm(forms.Form):
    ocrdata_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            'disabled': 'disabled',
        })
    )
    category =forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select,
    )

    target_month = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2020-01'
        })
    )
    office_name = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '事業所名を入力*',
            'type': 'search',
        })
    )
    emp_id = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '社員コードを入力*',
            'type': 'search',
        })
    )
    emp_name = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '氏名を入力*',
            'type': 'search',
        })
    )
    def __init__(self, categories=None, partners=None, publishers=None, accounts=None, *args, **kwargs):
        if categories:
            self.base_fields['category'].choices = categories
        super().__init__(*args, **kwargs)
    #     self.fields['fulltext'].widget.attrs['id'] = 'shiori_text'

    def clean_target_month(self):
        target_month = self.cleaned_data['target_month']
        if target_month:
            target_month = check_ym(target_month)
            if not target_month:
                raise forms.ValidationError('年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if target_month < '200001':
                raise forms.ValidationError('年月は2000年1月以降を入力してください')
        return target_month
# Ocr文書一覧表示画面
class EvcOcrDataListForm(forms.Form):
    shori_date = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )
    create_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    tr_no = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'お問い合わせ番号を入力*',
            'type': 'text',
        })
    )
    nx_tr_no = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'NNXお問い合わせ番号を入力*',
            'type': 'text',
        })
    )
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

    def clean_shori_date(self):
        shori_date = self.cleaned_data['shori_date']
        if shori_date:
            shori_date = check_ym(shori_date)
            if not shori_date:
                raise forms.ValidationError('処理年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if shori_date < '200001':
                raise forms.ValidationError('処理年月は2000年1月以降を入力してください')
        return shori_date

# 検索条件編集画面
class EvcEditOcrDataForm(forms.Form):
    ocrdata_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            'disabled': 'disabled',
        })
    )
    tr_no = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'お問い合わせ番号を入力*',
            'type': 'search',
        })
    )
    nx_tr_no = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'NXお問い合わせ番号を入力*',
            'type': 'search',
        })
    )
    def __init__(self, categories=None,  *args, **kwargs):
        if categories:
            self.base_fields['category'].choices = categories
        super().__init__(*args, **kwargs)
    #     self.fields['fulltext'].widget.attrs['id'] = 'shiori_text'

# JAふくおか八女 文書一覧表示画面
class EvcJafyameListForm(forms.Form):
    dept_cd = forms.ChoiceField(
        widget=forms.widgets.Select,
        required=False
    )
    shori_date = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )
    create_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    dept = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '部名を入力*',
            'type': 'text',
        })
    )
    section = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '課名を入力*',
            'type': 'text',
        })
    )
    spine = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '背表紙を入力*',
            'type': 'text',
        })
    )
    username = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '氏名を入力*',
            'type': 'text',
        })
    )
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

    # class Meta:
    #     model = TtEvidence
    #     fields = ['pdf_name', 'processed_date', 'category_name',
    #     'total_amount','partner_name',
    #     'create_date','result']
    #     # fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['page_size'].initial = 10
        # for field in self.fields.values():
        #     field.widget.attrs['class'] = 'form-control'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'

    def clean_shori_date(self):
        shori_date = self.cleaned_data['shori_date']
        if shori_date:
            shori_date = check_ym(shori_date)
            if not shori_date:
                raise forms.ValidationError('処理年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if shori_date < '200001':
                raise forms.ValidationError('処理年月は2000年1月以降を入力してください')
        return shori_date


# JAふくおか八女 文書検索条件編集画面
class EvcEditJafyameForm(forms.Form):
    ocrdata_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            'disabled': 'disabled',
        })
    )
    category =forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select,
    )

    processed_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    dept = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '部名を入力*',
            'type': 'search',
        })
    )
    section = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '課名を入力*',
            'type': 'search',
        })
    )
    spine = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '背表紙を入力*',
            'type': 'search',
        })
    )
    username = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '氏名を入力*',
            'type': 'search',
        })
    )
    def __init__(self, categories=None, partners=None, publishers=None, accounts=None, *args, **kwargs):
        if categories:
            self.base_fields['category'].choices = categories
        super().__init__(*args, **kwargs)
    #     self.fields['fulltext'].widget.attrs['id'] = 'shiori_text'

    # def clean_target_month(self):
    #     target_month = self.cleaned_data['target_month']
    #     if target_month:
    #         target_month = check_ym(target_month)
    #         if not target_month:
    #             raise forms.ValidationError('年月を正しく入力してください')
    #             # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
    #         if target_month < '200001':
    #             raise forms.ValidationError('年月は2000年1月以降を入力してください')
    #     return target_month
