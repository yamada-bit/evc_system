from django import forms
from django.contrib.auth.forms import AuthenticationForm
# from users.models import EvcUser,SysOwner

# from django.core.validators import validate_email
# from django.core.exceptions import ValidationError

# def check_email(value):
#     try:
#         if value:
#             validate_email(value)
#             return True
#     except ValidationError:
#         pass
#         # raise ValidationError('Email error.')
#     return False

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
    # def clean_email(self):
    #     email = self.cleaned_data['email']
    #     if email:
    #         if check_email(email):
    #             pass
    #         else:
    #             raise ValidationError(_("メールアドレスが正しくありません"),
    #                 code="invalid email"
    #             )
    #     return email

# class UserForm(forms.ModelForm):
#     """ユーザー情報更新フォーム"""
#     class Meta:
#         model = EvcUser
#         fields = ['user_id', 'user_name',
#         'owner_id','delete_flg','notes',
#         'create_user','create_date','update_user','update_date']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         for field in self.fields.values():
#             field.widget.attrs['class'] = 'form-control'
#         self.fields['user_id'].widget.attrs['readonly'] = 'readonly'

