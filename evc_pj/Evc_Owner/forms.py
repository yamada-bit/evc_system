from django import forms
from users.models import SysOwner,MtPhrase

from django.core.exceptions import ValidationError


# 契約会社登録画面
class EvcOwnerForm(forms.ModelForm):
    # CHOICE = [
    #     ('新規','新規'),
    #     ('変更','変更')]
    # kubun = forms.ChoiceField(label='登録区分', widget=forms.RadioSelect, choices=CHOICE, initial='新規')
    # delete_flg = forms.CharField(widget=forms.HiddenInput,initial=0)
    categorys = forms.CharField(label='カテゴリ', widget=forms.Textarea)
    # selectable_users = forms.CharField(label='選択可能ユーザ', widget=forms.Textarea)
    class Meta:
        model = SysOwner
        fields = ['owner_name','owner_ryaku_name','charge_name','charge_email','tel_no',
            'root_folder','notes','users_number','categorys']
            # 'root_folder','notes','users_number','categorys','selectable_users']
        widgets = {
            'notes': forms.Textarea(attrs={'placeholder':'100文字まで'}),
        }

        # widgets = {
        #     'user_id'   : forms.TextInput(attrs={'placeholder': '例）suzuki@gmail.com'}),
        #     'user_name' : forms.TextInput(attrs={'placeholder': '例）鈴木一郎'}),
        #     # 'tel_no'        : forms.Textarea (attrs={'placeholder' : '例）123-4567-8910'}),
        # }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if field.label != '登録区分':
                field.widget.attrs['class'] = 'form-input'
            if field.label == '契約会社ID':
               field.required = True
            if field.label == '会社名' or field.label == '会社名（略称）':
               field.required = True
            if field.label == '担当者名' or field.label == '担当者メールアドレス':
               field.required = True

            #    field.widget.attrs['required'] = 'required'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'
        # self.fields['root_folder'].widget.attrs['required'] = 'required'
        self.fields['notes'].widget.attrs['class'] = 'form-textarea'
        self.fields['categorys'].widget.attrs['class'] = 'form-textarea'
        # self.fields['selectable_users'].widget.attrs['class'] = 'form-textarea'
        # self.fields['categorys'].initial = '契約書\n注文書\n注文請書\n請求書\n領収書\n納品書\n見積書\n見積依頼書\n検収書\n発注書\nその他'
        self.fields['categorys'].initial = \
                    '契約書\n領収書\n預かり証\n借用書\n預金通帳\n小切手\n約束手形\n'\
                    '有価証券受渡計算書\n社債申込書\n契約の申込書\n請求書\n納品書\n送り状\n'\
                    '輸出証明書\n検収書\n入庫報告書\n貨物受領書\n'\
                    '見積書\n見積依頼書\n注文書\n注文請書\n契約申込書\n発注書\nその他'

        # self.fields['email_address'].required = True
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
# 契約会社変更画面
class EvcUpdateOwnerForm(forms.ModelForm):
    # CHOICE = [
    #     ('新規','新規'),
    #     ('変更','変更')]
    # kubun = forms.ChoiceField(label='登録区分', widget=forms.RadioSelect, choices=CHOICE, initial='新規')
    # delete_flg = forms.CharField(widget=forms.HiddenInput,initial=0)
    # selectable_users = forms.CharField(label='選択可能ユーザ', widget=forms.Textarea)
    class Meta:
        model = SysOwner
        fields = ['owner_name','owner_ryaku_name','charge_name','charge_email','tel_no',
                  'notes','users_number']
                #   'selectable_users','notes','users_number']
        widgets = {
            'notes': forms.Textarea(attrs={'placeholder':'100文字まで'}),
        }

        # widgets = {
        #     'user_id'   : forms.TextInput(attrs={'placeholder': '例）suzuki@gmail.com'}),
        #     'user_name' : forms.TextInput(attrs={'placeholder': '例）鈴木一郎'}),
        #     # 'tel_no'        : forms.Textarea (attrs={'placeholder' : '例）123-4567-8910'}),
        # }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if field.label != '登録区分':
                field.widget.attrs['class'] = 'form-input'
            if field.label == '会社名' or field.label == '会社名（略称）':
               field.required = True
            if field.label == '担当者名' or field.label == '担当者メールアドレス':
               field.required = True

            #    field.widget.attrs['required'] = 'required'
        # self.fields['user_id'].widget.attrs['readonly'] = 'readonly'
        # self.fields['root_folder'].widget.attrs['required'] = 'required'
        # self.fields['selectable_users'].widget.attrs['class'] = 'form-textarea'
        self.fields['notes'].widget.attrs['class'] = 'form-textarea'
        # self.fields['email_address'].required = True

# 契約会社一覧表示画面
class OwnerListForm(forms.Form):
    # partner_cd = forms.ModelChoiceField(queryset=MtPartner.objects.all().order_by('partner_id'))        
    owner = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '会社名を入力',
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

class PhraseForm(forms.ModelForm):
    """
    Phrase モデルの作成、更新に使われる Django フォーム。
    ModelForm を継承して作れば、HTMLで表示したいフィールドを
    指定するだけで HTML フォームを作ってくれる。
    """
    class Meta:
        model = MtPhrase
        fields = ['phrase_id', 'phrase', 'category_name']
"""
# 契約会社選択ユーザ一覧表示画面
class SelectableUserListForm(forms.Form):
    owner = forms.fields.ChoiceField(
        choices = (
            ('1', 'Owner1'),
            ('2', 'Owner2')
        ),
        required=True,
        widget=forms.widgets.Select
    )
    # owner_id = forms.CharField(
    #     max_length=30,
    #     required=False,
    #     widget=forms.TextInput(attrs={
    #         'placeholder': '契約会社IDを入力',
    #         'type': 'text',
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
"""