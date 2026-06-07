from django.db import models
from django.utils.translation import gettext_lazy as _


# Create your models here.
#OCRフォーム情報
class TtOcrform(models.Model):
    ocrform_id = models.CharField(verbose_name='フォームID', max_length=20,  primary_key=True)
    ocrform_name = models.CharField(verbose_name='フォーム名', max_length=50, null=True, blank=True)
    owner_id = models.CharField(verbose_name='契約会社ID', max_length=10, blank=True, null=True)
    ocrform_path = models.CharField(verbose_name='ファイルパス', max_length=256, null=True, blank=True)
    ocrform_area = models.TextField(verbose_name='フォームエリア', null=True, blank=True)
    ocrform_text = models.TextField(verbose_name='フォームテキスト', null=True, blank=True)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)

    class Meta:
        managed = True
        verbose_name = _('フォーム情報')
        verbose_name_plural = _('フォーム情報')
        db_table = 'tt_ocrform'
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.ocrform_name

#入力情報
class TtEntry(models.Model):
    entry_id = models.CharField(primary_key=True, max_length=20)
    entry_name = models.CharField(max_length=50, blank=True, null=True)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    ocrform_id = models.CharField(max_length=20, blank=True, null=True)
    pdf_name = models.CharField(max_length=50, blank=True, null=True)
    file_path = models.CharField(max_length=100, blank=True, null=True)
    processed_ym = models.CharField(max_length=6, blank=True, null=True)
    entry_area = models.TextField(blank=True, null=True)
    entry_detail = models.TextField(blank=True, null=True)
    google_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('入力情報')
        verbose_name_plural = _('入力情報')
        db_table = 'tt_entry'
    def __str__(self):
        return self.entry_name

#勤務表情報
class TtTimesheet(models.Model):
    timesheet_id = models.CharField(primary_key=True, max_length=20)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    pdf_name = models.CharField(max_length=50, blank=True, null=True)
    file_path = models.CharField(max_length=100, blank=True, null=True)
    processed_ym = models.CharField(max_length=6, blank=True, null=True)
    pdf_handbook = models.TextField(blank=True, null=True)
    ocrform_id = models.CharField(max_length=20, blank=True, null=True)
    form_area = models.TextField(blank=True, null=True)
    form_detail = models.TextField(blank=True, null=True)
    target_date = models.DateField(blank=True, null=True)
    emp_name = models.CharField(max_length=20, blank=True, null=True)
    emp_id = models.CharField(max_length=20, blank=True, null=True)
    office_name = models.CharField(max_length=50, blank=True, null=True)
    google_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('勤務表情報')
        verbose_name_plural = _('勤務表情報')
        db_table = 'tt_timesheet'
    def __str__(self):
        return self.timesheet_id

#Ocr文書情報
class TtOcrData(models.Model):
    ocrdata_id = models.CharField(primary_key=True, max_length=20)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    pdf_name = models.CharField(max_length=50, blank=True, null=True)
    file_path = models.CharField(max_length=100, blank=True, null=True)
    processed_ym = models.CharField(max_length=6, blank=True, null=True)
    pdf_handbook = models.TextField(blank=True, null=True)
    ocrform_id = models.CharField(max_length=20, blank=True, null=True)
    form_area = models.TextField(blank=True, null=True)
    form_detail = models.TextField(blank=True, null=True)
    search_text = models.TextField(blank=True, null=True)
    google_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('Ocr文書情報')
        verbose_name_plural = _('Ocr文書情報')
        db_table = 'tt_ocrdata'
    def __str__(self):
        return self.ocrdata_id

#JAふくおか八女 文書情報
class TtJafyame(models.Model):
    jafyame_id = models.CharField(primary_key=True, max_length=20)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    pdf_name = models.CharField(max_length=50, blank=True, null=True)
    file_path = models.CharField(max_length=100, blank=True, null=True)
    processed_ym = models.CharField(max_length=6, blank=True, null=True)
    pdf_handbook = models.TextField(blank=True, null=True)
    ocrform_id = models.CharField(max_length=20, blank=True, null=True)
    form_detail = models.TextField(blank=True, null=True)
    processed_date = models.DateField(blank=True, null=True)
    dept = models.CharField(max_length=50, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    spine = models.CharField(max_length=50, blank=True, null=True)
    username = models.CharField(max_length=50, blank=True, null=True)
    google_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('JAふくおか八女文書')
        verbose_name_plural = _('JAふくおか八女文書')
        db_table = 'tt_jafyame'
    def __str__(self):
        return self.jafyame_id

#アクセスログ
class TtAccessLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    access_user = models.CharField(max_length=50, null=False, blank=False)
    document_id = models.CharField(max_length=20, null=False, blank=False)
    accessed_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=[('view', 'View'), ('download', 'Download')])
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('アクセスログ')
        verbose_name_plural = _('アクセスログ')
        db_table = 'tt_accesslog'
    def __str__(self):
        return f'{self.access_user} accessed {self.document_id} at {self.accessed_at}'
