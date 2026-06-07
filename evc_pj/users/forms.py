from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import EvcUser, SysOwner


class EvcUserChangeForm(UserChangeForm):
    class Meta:
        model = EvcUser
        fields = '__all__'

class EvcUserCreationForm(UserCreationForm):
    class Meta:
        model = EvcUser
        fields = ('user_id','user_name')

class OwnerForm(forms.ModelForm):
    class Meta:
        model = SysOwner
        fields = ('owner_id','owner_name','owner_ryaku_name','charge_name','charge_email','tel_no','root_folder','notes',
                'create_user','create_date','update_user','update_date',)

