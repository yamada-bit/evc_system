from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import EvcUserChangeForm, EvcUserCreationForm, OwnerForm
from .models import (EvcUser,SysOwner,MtDept,MtFolder,MtPartner,TtEvidence,HtEvidence,
                     MtAccount,MtPhrase)
from Fms_Ocrform.models import TtOcrform,TtEntry,TtOcrData,TtTimesheet

class EvcUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('user_id', 'user_name', 'password')}),
        (_('Personal info'), {'fields': ('user_authority','owner_id','delete_flg','notes','create_user','create_date','update_user','update_date')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('user_id', 'user_name', 'password1', 'password2'),
        }),
    )
    form = EvcUserChangeForm
    add_form = EvcUserCreationForm
    list_display = ('user_id', 'user_name', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('user_id', 'user_name')
    ordering = ('user_id',)
#ユーザー定義のモデルを管理画面に組み込む
#admin.site.register(EvcUser)
#Django管理サイト、一覧表示をカスタマイズするには第二引数にクラス指定
admin.site.register(EvcUser, EvcUserAdmin)

class OwnerAdmin(admin.ModelAdmin):
    form = OwnerForm
    # list_display=('owner_id','owner_name','charge_name','charge_email','tel_no','notes',
    # 'create_user','create_date','update_user','update_date')
    # ordering = ('owner_id',)
admin.site.register(SysOwner, OwnerAdmin)

admin.site.unregister(Group)    # ジャンゴ(django)の提供してるGroupは使えないように

admin.site.register(MtDept)
admin.site.register(MtFolder)
admin.site.register(MtPartner)
admin.site.register(TtEvidence)
admin.site.register(HtEvidence)
admin.site.register(TtOcrform)
admin.site.register(MtAccount)
admin.site.register(TtEntry)
admin.site.register(MtPhrase)
