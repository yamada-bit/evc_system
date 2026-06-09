#from django_currentuser.db.models import CurrentUserField
from datetime import datetime as dt

from django.db import models

"""
update_date,INS_DATEフィールドを更新する抽象基底クラス
"""

class TimeStampBaseModel(models.Model):
    update_date = models.DateTimeField('更新日時', null=False, blank=False, auto_now=True)
    update_id = models.CharField('更新者ID', max_length=50, null=False, blank=False)
    ins_date = models.DateTimeField('登録日時', null=False, blank=False, default=dt.now)
    ins_id = models.CharField('登録者ID', max_length=50, null=False, blank=False )
    # update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    # update_id = models.CharField('更新者ID', max_length=50, null=False, blank=False)
    # ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    # ins_id = models.CharField('登録者ID', max_length=50, null=False, blank=False )
    del_flg = models.IntegerField('削除フラグ', null=False, blank=False, default=0)

    class Meta:
        abstract = True

    #created = models.DateTimeField(auto_now_add=True)
    #modified = models.DateTimeField(auto_now=True)
    #del_flg = models.BooleanField(verbose_name='削除フラグ', default=False)
    #ins_date = models.DateTimeField(verbose_name='登録日時', auto_now_add=True)
    #ins_id = CurrentUserField(verbose_name='登録者ID', related_name='create')
    #update_date = models.DateTimeField(verbose_name='更新日時', auto_now=True)
    #update_id = CurrentUserField(verbose_name='更新者ID', on_update=True, related_name='update')
"""
    def save(self, *args, **kwargs):
        dt_now = dt.now()
        #if self.ins_date == None:
        if self._state.adding:
            self.ins_date=dt_now.strftime('%Y/%m/%d %H:%M:%S')
            self.ins_id=self.update_id
        self.update_date=dt_now.strftime('%Y/%m/%d %H:%M:%S')
        self.del_flg=0

        super().save(*args, **kwargs)  # Call the "real" save() method.
"""
