import os
from django import forms
# from django.db import models
import datetime

# import random, string
# from django.conf import settings
# from django.core.files.storage import default_storage
# from users.models import EvcUser,SysOwner,TtEvidence,MtPartner,MtFolder
# from users.models import MtPartner,SysOwner

VALID_EXTENSIONS = ['.pdf','.jpg','.jpeg','.png','.bmp','.gif','.tif','.tiff']

# 契約会社一覧表示画面
class EvcSelectOwnerForm(forms.Form):
    # owner_cd = forms.ModelChoiceField(
    #     queryset=SysOwner.objects.all().order_by('owner_id'),
    #     required=False,
    #     empty_label='-契約会社を選択してください。-'
    #     )
    owner = forms.fields.ChoiceField(
        required=True,
        widget=forms.widgets.Select
    )
    def __init__(self, owners=None, *args, **kwargs):
        if owners:
            self.base_fields['owner'].choices = owners
        super().__init__(*args, **kwargs)
# 複数のファイルをアップロード
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
class EvcUploadFileForm(forms.Form):
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

    def clean_file(self):
        files = self.files.getlist('file')
        file = self.cleaned_data['file']
        for f in files:
            extension = os.path.splitext(f.name)[1]  # 拡張子を取得
            if not extension.lower() in VALID_EXTENSIONS:
                raise forms.ValidationError(f.name + ' ファイル形式が正しくありません')
        return file
    # def save(self):
    #     upload_files = self.files.getlist('file')
    #     temp_dir = os.path.join(settings.MEDIA_ROOT, self.create_dir(10)).replace(os.sep,'/')  # 一時フォルダの生成
    #     for pdf in upload_files:
    #         default_storage.save(os.path.join(temp_dir, pdf.name), pdf).replace(os.sep,'/')    # 一時フォルダにPDFを保存
    #     return temp_dir
    
    # def create_dir(self, n):
    #     return 'pdf\\' + ''.join(random.choices(string.ascii_letters + string.digits, k=n))

# ファイルアップロード画像分割
class EvcUploadAreaForm(forms.Form):
    postext = forms.CharField(required=False, widget=forms.HiddenInput)
    pagebtn = forms.CharField(required=False, widget=forms.HiddenInput)

# エビデンス一覧表示画面
class EvcEviListForm(forms.Form):
    pdf_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'ファイル名*',
            'type': 'text',
        })
    )
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
    # today_check = forms.BooleanField(label='本日のみ', required=False, initial=True)    
    # user_check = forms.BooleanField(label='ログインユーザのみ', required=False, initial=True)    

    today_kubuns = forms.ChoiceField(
        label='作成日区分', 
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ('today', '本日'),
            ('none', '指定なし'),
        ),
        initial='today'
    )
    user_kubuns = forms.ChoiceField(
        label='ユーザ区分', 
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ('loginuser', 'ログインユーザ'),
            ('none', '指定なし'),
        ),
        initial='loginuser'
    )

    category = forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select
    )
    account_choice = forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select
    )

    # partner_cd = forms.ModelChoiceField(queryset=MtPartner.objects.all().order_by('partner_id'))
    partner = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '取引先を入力*',
            'type': 'text',
        })
    )
    publisher = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '発行元を入力*',
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
    # amount = forms.CharField(max_length=12,
    #                             required=False,
    #                             widget=forms.TextInput(attrs={
    #                                 'placeholder': '取引金額',
    #                                 'type':'search',
    #                                 'size':12,
    #                             }))
    # amount = forms.IntegerField(required=False, min_length=5, max_length=10,
    #                             widget=forms.NumberInput(attrs={
    #                                 'placeholder': '取引金額',
    #                                 'size':12,
    #                             }))
    amount1 = forms.CharField(
        required=False,
        disabled=False,
        max_length=12,
        widget=forms.TextInput(attrs={
            'placeholder': '取引金額',
            'pattern': '^[0-9]+$',
            'type': 'search',
            'size': 12,
        }))
    amount2 = forms.CharField(
        required=False,
        disabled=False,
        max_length=12,
        widget=forms.TextInput(attrs={
            'placeholder': '取引金額',
            'pattern': '^[0-9]+$',
            'type': 'search',
            'size': 12,
        }))
    amount = forms.CharField(
        required=False,
        disabled=False,
        max_length=12,
        widget=forms.TextInput(attrs={
            'placeholder': '取引金額',
            'pattern': '^[0-9]+$',
            'type': 'search',
            'size': 12,
        }))                                
    # amount = forms.IntegerField(max_length=12)
    amount_choice = forms.fields.ChoiceField(
        choices=(
            ('1', '以下'),
            ('2', '以上'),
            ('3', '等しい'),
        ),
        required=False,
        widget=forms.widgets.Select
    )
    account = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '科目を入力*',
            'type': 'text',
        })
    )
    account_desc = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '摘要を入力*',
            'type': 'text',
        })
    )
    slip_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '伝票番号を入力*',
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
    duplist = forms.CharField(required=False, widget=forms.HiddenInput)
 
    # duplist = forms.MultipleChoiceField(
    #       label='チェック',
    #       required=False,
    #       disabled=False,
    #       initial=[],
    #       choices=(
    #         (1, '重複のみ検索'),
    #       ),
    #       widget=forms.CheckboxSelectMultiple(attrs={
    #            'id': 'duplist','class': 'form-check-duplist'}))    

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
class EvcSConCreateForm(forms.Form):
    evidence_id = forms.CharField(widget=forms.HiddenInput)
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

    partner_cd = forms.ChoiceField(
        widget=forms.widgets.Select,
        required=False
    )
    partner = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 25,
        })
    )
    publisher = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 25,
        })
    )
    publisher_cd = forms.ChoiceField(
        widget=forms.widgets.Select,
        required=False
    )
    corporate_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'size': 20,
        })
    )
    detect_partner = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.HiddenInput()
    )
    detect_publisher = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.HiddenInput()
    )
    process_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'size': 10,
        })
    )

    payment_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'size': 10,
        })
    )

    amount = forms.CharField(
        required=False,
        max_length=12,
        widget=forms.TextInput(attrs={
            'placeholder': '取引金額',
            'pattern': '^[0-9]+$',
            'type': 'search',
            'size': 12,
        }))                                

    # amount = forms.IntegerField(
    #     required=False,
    #     widget=forms.TextInput(attrs={
    #         'pattern': '^[0-9]+$',
    #         'type': 'search',
    #         'max': '999999999999',
    #         'size': 12,
    #     })
    # )
    account = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            # 'placeholder': '科目を入力*',
            'type': 'search',
            'size': 25,
        })
    )
    account_cd = forms.ChoiceField(
        widget=forms.widgets.Select,
        required=False
    )

    account_desc = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            # 'placeholder': '摘要を入力*',
            'type': 'search',
            'size': 50,
        })
    )
    slip_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            # 'placeholder': '伝票番号を入力*',
            'type': 'search',
        })
    )
    duplicate_check = forms.BooleanField(
        label='重複許可',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'duplicate-checkbox'}),
    )               
    def __init__(self, categories=None, partners=None, publishers=None, accounts=None, *args, **kwargs):
        if categories:
            self.base_fields['category'].choices = categories
        if partners:
            self.base_fields['partner_cd'].choices = partners
        if publishers:
            self.base_fields['publisher_cd'].choices = publishers
        if accounts:
            self.base_fields['account_cd'].choices = accounts
        super().__init__(*args, **kwargs)
    #     self.fields['fulltext'].widget.attrs['id'] = 'shiori_text'
        self.fields['corporate_number'].widget.attrs['readonly'] = 'readonly'

    # def clean_amount(self):
    #     amount = self.cleaned_data['amount']
    #     if 20 < len(str(amount)):
    #         raise forms.ValidationError('金額が正しくありません。')

    #     return amount
