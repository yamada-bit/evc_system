from django.db import models

# Create your models here.
from django.utils.translation import gettext_lazy as _

# 外勤報告書情報
class TtGaikinReport(models.Model):
    report_id = models.CharField(primary_key=True, max_length=20)
    report_name = models.CharField(max_length=50, blank=True, null=True)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    pdf_name = models.CharField(max_length=50, blank=True, null=True)
    file_path = models.CharField(max_length=100, blank=True, null=True)
    processed_ym = models.CharField(max_length=6, blank=True, null=True)
    page_count = models.IntegerField(null=False, blank=False,default=0)
    # google_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    delete_flg = models.IntegerField(null=False, blank=False,default=0)
    notes = models.CharField(max_length=100, null=True, blank=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.report_name
    class Meta:
        managed = True
        verbose_name = _('外勤報告書情報')
        verbose_name_plural = _('外勤報告書情報')
        db_table = 'tt_gaikin_report'
