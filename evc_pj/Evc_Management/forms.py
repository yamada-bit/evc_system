import os
import datetime
from django import forms
from django.contrib.auth.forms import AuthenticationForm,UserCreationForm
from users.models import EvcUser,SysOwner,MtPartner,MtFolder

# from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
# from django.utils.translation import gettext as _
VALID_CSV_EXTENSIONS = ['.csv']

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

# 実績サマリー画面
class EviSummaryForm(forms.Form):
    # trade_month = forms.CharField(
    #     required=False,
    #     max_length=7,
    #     widget=forms.TextInput(attrs={
    #         'placeholder': 'yyyy/mm',
    #         'type': 'text',
    #         'size': 7,
    #     })
    # )
    trade_month = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )

    category = forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select
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

    def clean_trade_month(self):
        trade_month = self.cleaned_data['trade_month']
        if trade_month:
            trade_month = check_ym(trade_month)
            if not trade_month:
                raise forms.ValidationError('取引年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if trade_month < '200001':
                raise forms.ValidationError('取引年月は2000年1月以降を入力してください')
        return trade_month

# 実績照会画面
class EviInquiryForm(forms.Form):
    # trade_month = forms.CharField(
    #     required=False,
    #     max_length=7,
    #     widget=forms.TextInput(attrs={
    #         'placeholder': 'yyyy/mm',
    #         'type': 'text',
    #         'size': 7,
    #     })
    # )
    trade_month = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )

    category = forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select
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

    def clean_trade_month(self):
        trade_month = self.cleaned_data['trade_month']
        if trade_month:
            trade_month = check_ym(trade_month)
            if not trade_month:
                raise forms.ValidationError('取引年月を正しく入力してください')
                # raise forms.ValidationError('処理年月は yyyy/mm で入力してください')
            if trade_month < '200001':
                raise forms.ValidationError('取引年月は2000年1月以降を入力してください')
        return trade_month

# ユーザ登録(/変更/削除)画面
class EvcUserForm(forms.ModelForm):
    CHOICE_AUTHORITY = [
        ('管理者','管理者'),
        ('一般','一般')]
    user_authority = forms.ChoiceField(label='権限', widget=forms.RadioSelect, choices=CHOICE_AUTHORITY, initial='一般')

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'パスワードを入力',
        })
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'パスワードを再入力（確認）',
        })
    )
    # owner_cd = forms.ModelChoiceField(queryset=SysOwner.objects.all().order_by('owner_id'))
    # notes = forms.CharField(max_length=100, widget=forms.Textarea())
    CHOICE = [
        ('新規','新規'),
        ('変更','変更'),
        ('削除','削除')]
    kubun = forms.ChoiceField(label='登録区分', widget=forms.RadioSelect, choices=CHOICE, initial='新規')
    # delete_flg = forms.IntegerField(widget=forms.HiddenInput,initial=0)
 
    class Meta:
        model = EvcUser
        # fields = ('user_id')
        fields = ['user_authority','user_id','user_name','password1','password2',
            'kubun','notes']
        widgets = {
            'notes': forms.Textarea(attrs={'placeholder':'100文字まで'}),
            'user_id'   : forms.TextInput(attrs={'placeholder': '例）suzuki@gmail.com'}),
            'user_name' : forms.TextInput(attrs={'placeholder': '例）鈴木一郎'}),
            # 'tel_no'        : forms.Textarea (attrs={'placeholder' : '例）123-4567-8910'}),
        }
    def __init__(self, *args, update=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if field.label != '権限' and field.label != '登録区分' and field.label != '備考':
                field.widget.attrs['class'] = 'form-input'
            if field.label != '備考':
               field.required = True
            #    field.widget.attrs['required'] = 'required'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'
        self.fields['notes'].widget.attrs['class'] = 'form-textarea'
        # self.fields['email_address'].required = True
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        if update:
            self.fields['user_id'].widget.attrs['readonly'] = 'readonly'

    def validate_unique(self):
        """
        Call the instance's validate_unique() method and update the form's
        validation errors if any were raised.
        """
        exclude = self._get_validation_exclusions()
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            # self._update_errors(e)
            kubun = self.cleaned_data.get('kubun')
            if kubun == '新規':
                self._update_errors(e)
            else:
                pass

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        kubun = self.cleaned_data.get('kubun')
        if kubun != '新規' and not password1 and not password2:
            return password2

        validate_password(password2)
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('確認用パスワードが一致しません。')
        return password2

    #パスワード変更を判定のためview.pyで処理
    # def save(self, commit=True):
    #     # Save the provided password in hashed format
    #     user = super().save(commit=False)
    #     user.set_password(self.cleaned_data['password1'])
    #     if commit:
    #         user.save()
    #     return user
# ユーザ一覧表示画面
class EvcUserListForm(forms.Form):
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
# エビデンス変更履歴一覧表示画面
class EvcEviHistoryListForm(forms.Form):
    kubun = forms.ChoiceField(
        label='履歴区分', 
        required=False,
        widget=forms.RadioSelect,
        choices=(
            ('none', '指定なし'),
            ('change', 'キー修正'),
            ('ocr', 'OCR修正'),
            ('delete', '削除'),
        ),
        initial='none'
    )
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

    category = forms.fields.ChoiceField(
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
            'size': 10,
        })
    )
    process_date2 = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'size': 10,
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
# エビデンス詳細画面
class EvcSConShowForm(forms.Form):
    # evidence_id = forms.CharField(widget=forms.HiddenInput)
    fulltext = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'id': 'shiori_text',
            'disabled': 'disabled',
        })
    )
    category =forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select(attrs={
            'disabled': 'disabled',
        }),
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
            'readonly': 'readonly', 
        })
    )
    publisher_cd = forms.ChoiceField(
        widget=forms.widgets.Select,
        required=False
    )
    process_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'size': 10,
            'readonly': 'readonly', 
        })
    )
    payment_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'size': 10,
            'readonly': 'readonly', 
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
            'readonly': 'readonly', 
        })
    )
    slip_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            # 'placeholder': '伝票番号を入力*',
            'type': 'search',
            'readonly': 'readonly', 
        })
    )
    duplicate_check = forms.BooleanField(
        label='重複許可',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'duplicate-checkbox',
            'disabled': 'disabled', 
        }),
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

    # def clean_amount(self):
    #     amount = self.cleaned_data['amount']
    #     if 20 < len(str(amount)):
    #         raise forms.ValidationError('金額が正しくありません。')

    #     return amount

# 取引先一覧表示画面
class PartnerListForm(forms.Form):
    # partner_cd = forms.ModelChoiceField(queryset=MtPartner.objects.all().order_by('partner_id'))        
    partner = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '取引先名を入力',
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
    # class Meta:
    #     model = TtEvidence
    #     fields = ['partner_name', 'partner_ryaku_name',
    #     'create_date']
    #     # fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['page_size'].initial = 10
        # for field in self.fields.values():
        #     field.widget.attrs['class'] = 'form-control'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'

# 取引先登録画面
class EvcPartnerForm(forms.ModelForm):
    # partner_id_hidden = forms.CharField(widget=forms.HiddenInput)
    CHOICE = [
        ('new','新規'),
        ('change','変更'),
        ('delete','削除')]
    kubuns = forms.ChoiceField(label='登録区分', widget=forms.RadioSelect, choices=CHOICE, initial='new')
    CHOICE_TYPE = [
        ('none','区分無し'),
        ('customer','顧客'),
        ('supplier','仕入先')]
    partner_types = forms.ChoiceField(label='取引先区分', widget=forms.RadioSelect, choices=CHOICE_TYPE, initial='none')

    partner_name = forms.CharField(
        label='取引先名',
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': '例）株式会社鈴木商事',
        })
    )
    partner_ryaku_name = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '例）鈴木商事',
        })
    )
    corporate_number = forms.CharField(
        max_length=13,
        widget=forms.TextInput(attrs={
            'placeholder': '例）2010001168333',
        })
    )
    charge_dept = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': '例）業務管理部',
        })
    )
    charge_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': '例）鈴木一郎',
        })
    )
    charge_email = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': '例）suzuki@gmail.com',
        })
    )
    zip3 = forms.CharField(
        label='郵便番号3',
        max_length=3,
        widget=forms.TextInput(attrs={
            'placeholder': '100',
        })
    )
    zip4 = forms.CharField(
        label='郵便番号4',
        max_length=4,
        widget=forms.TextInput(attrs={
            'placeholder': '0000',
            'onkeyup':"AjaxZip3.zip2addr('zip3','zip4','address1','address1');"
        })
    )

    address1 = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': '例）東京都千代田区１丁目１－１',
            'onkeyup':"AjaxZip3.zip2addr('zip3','zip4','address1','address1');"
        })
    )

    address2 = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': '例）鈴木ビル１階１０１号室',
        })
    )
    tel_no = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '例）03-4567-8910',
        })
    )
    fax_no = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '例）03-4567-8911',
        })
    )

    class Meta:
        model = MtPartner
        fields = [
            'kubuns', 'partner_name', 'partner_types','partner_ryaku_name','corporate_number',
            'charge_dept','charge_name','charge_email','zip3','zip4','address1','address2',
            'tel_no','fax_no','notes',
        ]
        # fields = '__all__'
        widgets = {
            'notes': forms.Textarea(attrs={'placeholder':'100文字まで'}),
        }    
               
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    #     self.fields['fulltext'].widget.attrs['id'] = 'shiori_text'
        for field in self.fields.values():
            if field.label != '登録区分' and field.label != '取引先区分':
                field.widget.attrs['class'] = 'form-input'
            if field.label == '登録区分' or field.label == '取引先名' or field.label == '取引先区分':
               field.required = True
            else:
               field.required = False
            #    field.widget.attrs['required'] = "required'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'
        self.fields['notes'].widget.attrs['class'] = 'form-textarea'
        self.fields['zip3'].widget.attrs['class'] = 'form-zip1'
        self.fields['zip4'].widget.attrs['class'] = 'form-zip2'


class EvcPartnerSaveForm(forms.Form):
    partnercsv = forms.FileField(
        label='アップロードファイル',
    )
    def clean_partnercsv(self):
        file = self.cleaned_data['partnercsv']
        extension = os.path.splitext(file.name)[1] # 拡張子を取得
        if not extension.lower() in VALID_CSV_EXTENSIONS:
            raise forms.ValidationError('csvファイルを選択してください！')

class EvcAccountSaveForm(forms.Form):
    accountcsv = forms.FileField(
        label='アップロードファイル',
    )
    def clean_accountcsv(self):
        file = self.cleaned_data['accountcsv']
        extension = os.path.splitext(file.name)[1] # 拡張子を取得
        if not extension.lower() in VALID_CSV_EXTENSIONS:
            raise forms.ValidationError('csvファイルを選択してください！')
# Google利用履歴画面
class EvcUseGoogleForm(forms.Form):
    # owner = forms.ModelChoiceField(queryset=SysOwner.objects.all().order_by('owner_id'))
    owner = forms.fields.ChoiceField(
        required=False,
        widget=forms.widgets.Select
    )

    kubun = forms.ChoiceField(
        label='集計区分', 
        required=False,
        widget=forms.RadioSelect,
        choices=(
            ('none', '指定なし'),
            ('summ', '集計'),
        ),
        initial='none'
    )
    shori_date1 = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )
    shori_date2 = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'month',
            'min': '2000-01'
        })
    )
    # shori_date1 = forms.CharField(
    #     required=False,
    #     max_length=7,
    #     # initial= ut_get_localtoday().strftime('%Y/%m'),
    #     widget=forms.TextInput(attrs={
    #         'placeholder': 'yyyy/mm',
    #         'type': 'text',
    #         'size': 7,
    #     })
    # )    
    # shori_date2 = forms.CharField(
    #     required=False,
    #     max_length=7,
    #     # initial= ut_get_localtoday().strftime('%Y/%m'),
    #     widget=forms.TextInput(attrs={
    #         'placeholder': 'yyyy/mm',
    #         'type': 'text',
    #         'size': 7,
    #     })
    # )    
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
    def clean_shori_date1(self):
        shori_date = self.cleaned_data['shori_date1']
        if shori_date:
            shori_date = check_ym(shori_date)
            if not shori_date:
                raise forms.ValidationError('処理年月(開始)を正しく入力してください')
                # raise forms.ValidationError('処理年月(開始)は yyyy/mm で入力してください')
            if shori_date < '200001':
                raise forms.ValidationError('処理年月(開始)は2000年1月以降を入力してください')
        return shori_date
    def clean_shori_date2(self):
        shori_date = self.cleaned_data['shori_date2']
        if shori_date:
            shori_date = check_ym(shori_date)
            if not shori_date:
                raise forms.ValidationError('処理年月(終了)を正しく入力してください')
                # raise forms.ValidationError('処理年月(終了)は yyyy/mm で入力してください')
            if shori_date < '200001':
                raise forms.ValidationError('処理年月(終了)は2000年1月以降を入力してください')
        return shori_date

# カテゴリ一覧表示画面
class EvcCategoryListForm(forms.Form):
    # partner_cd = forms.ModelChoiceField(queryset=MtPartner.objects.all().order_by('partner_id'))        
    partner = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '取引先名を入力',
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
    # class Meta:
    #     model = TtEvidence
    #     fields = ['partner_name', 'partner_ryaku_name',
    #     'create_date']
    #     # fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['page_size'].initial = 10
        # for field in self.fields.values():
        #     field.widget.attrs['class'] = 'form-control'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'

# カテゴリ登録画面
class EvcCategoryForm(forms.ModelForm):
    # partner_id_hidden = forms.CharField(widget=forms.HiddenInput)
    CHOICE = [
        ('new','新規'),
        ('change','変更'),
        ('delete','削除')]
    kubuns = forms.ChoiceField(label='登録区分', widget=forms.RadioSelect, choices=CHOICE, initial='new')

    category_name = forms.CharField(
        label='カテゴリ名',
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '例）領収書',
        })
    )
    display_order = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'placeholder': '表示順',
            'size':4,
        })
        # widget=forms.TextInput(attrs={
        #     'pattern': '^[0-9]+$',
        #     'type': 'search',
        #     'max': '9999',
        #     'size': 4,
        # })
    )

    class Meta:
        model = MtFolder
        fields = [
            'kubuns', 'category_name','notes','display_order'
        ]
        # fields = '__all__'
        widgets = {
            'notes': forms.Textarea(attrs={'placeholder':'100文字まで'}),
        }    
               
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    #     self.fields['fulltext'].widget.attrs['id'] = 'shiori_text'
        for field in self.fields.values():
            if field.label != '登録区分' and field.label != 'カテゴリ区分':
                field.widget.attrs['class'] = 'form-input'
            if field.label == '登録区分' or field.label == 'カテゴリ名' or field.label == 'カテゴリ区分':
               field.required = True
            else:
               field.required = False
        
            #    field.widget.attrs['required'] = 'required'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'
        self.fields['notes'].widget.attrs['class'] = 'form-textarea'
        self.fields['display_order'].widget.attrs['min'] = 0
