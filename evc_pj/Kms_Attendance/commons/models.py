from django.db import models
#from django_currentuser.db.models import CurrentUserField
from datetime import datetime as dt
"""
UPDATE_DATE,INS_DATEフィールドを更新する抽象基底クラス
"""
 
class TimeStampBaseModel(models.Model):
    UPDATE_DATE = models.DateTimeField('更新日時', null=False, blank=False, auto_now=True)
    UPDATE_ID = models.CharField('更新者ID', max_length=50, null=False, blank=False)
    INS_DATE = models.DateTimeField('登録日時', null=False, blank=False, default=dt.now)
    INS_ID = models.CharField('登録者ID', max_length=50, null=False, blank=False )
    # UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    # UPDATE_ID = models.CharField('更新者ID', max_length=50, null=False, blank=False)
    # INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    # INS_ID = models.CharField('登録者ID', max_length=50, null=False, blank=False )
    DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False, default=0)
    
    class Meta:
        abstract = True

    #created = models.DateTimeField(auto_now_add=True)
    #modified = models.DateTimeField(auto_now=True)
    #DEL_FLG = models.BooleanField(verbose_name='削除フラグ', default=False)
    #INS_DATE = models.DateTimeField(verbose_name='登録日時', auto_now_add=True)
    #INS_ID = CurrentUserField(verbose_name='登録者ID', related_name='create')
    #UPDATE_DATE = models.DateTimeField(verbose_name='更新日時', auto_now=True)
    #UPDATE_ID = CurrentUserField(verbose_name='更新者ID', on_update=True, related_name='update')
"""
    def save(self, *args, **kwargs):
        dt_now = dt.now()
        #if self.INS_DATE == None:
        if self._state.adding:
            self.INS_DATE=dt_now.strftime('%Y/%m/%d %H:%M:%S')
            self.INS_ID=self.UPDATE_ID
        self.UPDATE_DATE=dt_now.strftime('%Y/%m/%d %H:%M:%S')
        self.DEL_FLG=0

        super().save(*args, **kwargs)  # Call the "real" save() method.
"""