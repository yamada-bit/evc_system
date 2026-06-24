from django import forms
from django.contrib.auth.forms import AuthenticationForm


class AttendanceLoginForm(AuthenticationForm):
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
