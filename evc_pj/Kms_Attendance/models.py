import uuid

from django.db import models

# Create your models here.
from Kms_Attendance.commons.models import TimeStampBaseModel


#社員マスタ
class M_emp(TimeStampBaseModel):
#class M_emp(models.Model):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)
    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    EMP_NAME = models.CharField('社員名', max_length=40, null=False, blank=False)
    KBN = models.IntegerField('区分', null=False, blank=False)
    EMP_KANA = models.CharField('フリガナ', max_length=80, null=False, blank=False)
    # EvcUserとリンクするため追加、ユニークで必須に
    user_id = models.EmailField('EvcユーザID', max_length=50, null=False, blank=False, unique=True)
    TDFUKEN_CD = models.IntegerField('都道府県', null=False, blank=False)
    ADD_1 = models.CharField('住所１', max_length=100, null=True, blank=True)
    WORK_PAT_CD = models.CharField('勤務パターンCD', max_length=4, null=False, blank=False, default='0')
    TEL_NO = models.CharField('電話番号', max_length=11, null=True, blank=True)
    MOBILE_NO = models.CharField('携帯番号', max_length=11, null=True, blank=True)
    MAIL_ADD = models.CharField('メールアドレス', max_length=50, null=True, blank=True)
    SEX = models.IntegerField('性別', null=False, blank=False)
    BIRTHDAY = models.IntegerField('生年月日', null=True, blank=True)
    JOINED_DATE = models.IntegerField('入社日', null=True, blank=True)
    MEMO = models.CharField('備考', max_length=120, null=True, blank=True)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_EMP'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID'],
                name='emp_unique'
            ),
        ]
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID
#所属マスタ
class M_ltd(TimeStampBaseModel):
    #id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)

    LTD_CD = models.CharField('所属CD', max_length=4, primary_key=True)
    LTD_NAME = models.CharField('所属名', max_length=40,  null=False, blank=False)
    LTD_KANA = models.CharField('フリガナ', max_length=80, null=False, blank=False)
    LTD_TDFUKEN_CD = models.IntegerField('本社所在', null=False, blank=False)
    LTD_ADD = models.CharField('住所', max_length=100, null=True, blank=True)
    DAIHYO_NAME = models.CharField('代表者名', max_length=40, null=False, blank=False)
    DAIHYO_MAIL = models.CharField('代表メールアドレス', max_length=50, null=True, blank=True)
    TANTO_NAME = models.CharField('担当者名', max_length=40, null=True, blank=True)
    TANTO_MAIL = models.CharField('担当者メールアドレス', max_length=50, null=True, blank=True)
    TEL_NO = models.CharField('電話番号', max_length=11, null=True, blank=True)
    FAX_NO = models.CharField('FAX番号', max_length=11, null=True, blank=True)
    MEMO = models.CharField('備考', max_length=120, null=True, blank=True)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_LTD'
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.LTD_CD + ' : ' + self.LTD_NAME
#祝日マスタ
class M_holiday(TimeStampBaseModel):
    HOLIDAY_YMD = models.IntegerField('年月日', primary_key=True)
    HOLIDAY_NAME = models.CharField('祝祭日名称', max_length=40, null=False, blank=False)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_HOLIDAY'

    def __str__(self):
        return str(self.HOLIDAY_YMD) + ' : ' + self.HOLIDAY_NAME
#都道府県マスタ
class M_tdfuken(TimeStampBaseModel):
    TDFUKEN_CD = models.IntegerField('都道府県コード', primary_key=True)
    TDFUKEN_NAME = models.CharField('都道府県名', max_length=8, null=False, blank=False)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_TDFUKEN'

    def __str__(self):
        return str(self.TDFUKEN_CD) + ' : ' + self.TDFUKEN_NAME

#所定勤務マスタ
class M_work_pat(TimeStampBaseModel):
    WORK_PAT_CD = models.CharField('勤務パターンCD', max_length=4, primary_key=True)
    WORK_PAT_NAME = models.CharField('勤務パターン名', max_length=16, null=False, blank=False)
    START_TIME = models.CharField('開始時刻', max_length=5, null=False, blank=False)
    END_TIME = models.CharField('終了時刻', max_length=5, null=False, blank=False)
    WORK_TIME = models.CharField('稼働時間', max_length=5, null=False, blank=False)
    REST1_START_TIME = models.CharField('休憩１開始時刻', max_length=5, null=False, blank=False)
    REST1_END_TIME = models.CharField('休憩１終了時刻', max_length=5, null=False, blank=False)
    REST1_TIME = models.CharField('休憩時間１', max_length=5, null=False, blank=False)
    REST2_START_TIME = models.CharField('休憩2開始時刻', max_length=5, null=False, blank=False)
    REST2_END_TIME = models.CharField('休憩2終了時刻', max_length=5, null=False, blank=False)
    REST2_TIME = models.CharField('休憩時間2', max_length=5, null=False, blank=False)
    NIGHT_START_TIME = models.CharField('深夜勤務開始時刻', max_length=5, null=False, blank=False)
    NIGHT_END_TIME = models.CharField('深夜勤務終了時刻', max_length=5, null=False, blank=False)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_WORK_PAT'

    def __str__(self):
        return str(self.WORK_PAT_CD) + ' : ' + self.WORK_PAT_NAME

#年度切替マスタ
class M_nendo(TimeStampBaseModel):
    LTD_CD = models.CharField('所属CD', max_length=4, primary_key=True)
    NENDO_START_MD = models.IntegerField('月日', null=False, blank=False)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_NENDO'

    def __str__(self):
        return self.LTD_CD + ' : ' + str(self.NENDO_START_MD)

#勤務区分マスタ
class M_kbn(TimeStampBaseModel):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)

    ZOKUSEI_CD = models.IntegerField('属性値', null=False, blank=False)
    ZOKUSEI_NAME = models.CharField('属性名', max_length=16, null=False, blank=False)
    KBN = models.IntegerField('区分値', null=False, blank=False)
    KBN_NAME = models.CharField('区分名', max_length=16, null=False, blank=False)
    KBN_ORDER = models.IntegerField('表示順', null=False, blank=False)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_KBN'
        constraints = [
            models.UniqueConstraint(
                fields=['ZOKUSEI_CD','KBN'],
                name='kbn_unique'
            ),
        ]

    def __str__(self):
        return self.KBN_NAME

#有給付与管理テーブル
class M_yukyu(TimeStampBaseModel):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)

    LTD_CD = models.CharField('所属CD', max_length=4, null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20, null=False, blank=False)
    NENDO = models.IntegerField('年度', null=False, blank=False)
    NEW_COUNT = models.IntegerField('当年度付与数', null=True, blank=True)
    CARRY_OVER = models.IntegerField('前年繰越日数', null=True, blank=True)
    ALL_COUNT = models.IntegerField('当年度総数', null=True, blank=True)
    USED_COUNT = models.IntegerField('当年度取得数', null=True, blank=True)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'M_YUKYU'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','NENDO'],
                name='yukyu_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.NENDO)

#休暇管理テーブル
class T_leave(TimeStampBaseModel):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)

    LTD_CD = models.CharField('所属CD', max_length=4, null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20, null=False, blank=False)
    NENDO = models.IntegerField('年度', null=False, blank=False)
    KBN =  models.IntegerField('出退勤区分', null=False, blank=False)
    MODIFY_DATE =  models.IntegerField('休暇修正日', null=True, blank=True)
    NEW_COUNT =  models.CharField('当年度付与数', max_length=6, null=True, blank=True)
    CARRY_OVER =  models.CharField('前年繰越日数', max_length=6, null=True, blank=True)
    ALL_COUNT =  models.CharField('当年度総数', max_length=6, null=True, blank=True)
    USED_COUNT =  models.CharField('当年度取得数', max_length=6, null=True, blank=True)
    REMAINING_COUNT =  models.CharField('残数調整', max_length=6, null=True, blank=True)
    EXPIRATION_DATE =  models.IntegerField('有効期限', null=True, blank=True)
    REASON = models.CharField('理由', max_length=120, null=True, blank=True)
    #UPDATE_DATE = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #UPDATE_ID = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #INS_DATE = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #INS_ID = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #DEL_FLG = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'T_LEAVE'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','NENDO','KBN'],
                name='leave_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.NENDO)

#打刻テーブル
class T_time_stamp(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    #uuid = models.UUIDField(default=uuid.uuid4,
    #                        primary_key=True, editable=False)

    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    TARGET_DATE =  models.IntegerField('年月日', null=False, blank=False)
    KBN =  models.IntegerField('出退勤区分', null=False, blank=False)
    START_TIME = models.CharField('出社時刻（打刻）', max_length=20,  null=True, blank=True)
    CORRET_START_TIME = models.CharField('出社時刻（訂正）', max_length=20,  null=True, blank=True)
    END_TIME = models.CharField('退社時刻（打刻）', max_length=20,  null=True, blank=True)
    CORRET_END_TIME = models.CharField('退社時刻（訂正）', max_length=20,  null=True, blank=True)
    OUT_START_TIME = models.CharField('外出開始時刻', max_length=20,  null=True, blank=True)
    OUT_END_TIME = models.CharField('外出開始時刻', max_length=20,  null=True, blank=True)
    I_DO = models.CharField('緯度', max_length=20,  null=True, blank=True)
    KE_ID = models.CharField('経度', max_length=20,  null=True, blank=True)
    WORK_STAT =  models.IntegerField('申請状態', null=True, blank=True)
    WORK_DEL_FLG =  models.IntegerField('勤務削除', null=True, blank=True)

    # # M_emp モデルへのリレーション
    # emp = models.ForeignKey(M_emp, on_delete=models.CASCADE,
    #                         related_name='time_stamps',
    #                         to_field='id')  # M_emp の id を使ってリレーション

    class Meta:
        managed = True
        db_table = 'T_TIME_STAMP'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','TARGET_DATE'],
                name='time_stamp_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.TARGET_DATE)
#申請テーブル
class T_request(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    #uuid = models.UUIDField(default=uuid.uuid4,
    #                        primary_key=True, editable=False)

    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    TARGET_DATE =  models.IntegerField('年月日', null=False, blank=False)
    KBN =  models.IntegerField('出退勤区分', null=False, blank=False)
    START_TIME = models.CharField('出社時刻（打刻）', max_length=20,  null=True, blank=True)
    CORRET_START_TIME = models.CharField('出社時刻（訂正）', max_length=20,  null=True, blank=True)
    END_TIME = models.CharField('退社時刻（打刻）', max_length=20,  null=True, blank=True)
    CORRET_END_TIME = models.CharField('退社時刻（訂正）', max_length=20,  null=True, blank=True)
    END_NEXT_FLG =  models.IntegerField('退社翌日フラグ', null=False, blank=False)
    EXPENSES =  models.IntegerField('経費', null=True, blank=True)
    MEMO = models.CharField('備考', max_length=120, null=True, blank=True)
    AGREE_COMMENT = models.CharField('所属長コメント', max_length=120, null=True, blank=True)
    REQUEST_DATE =  models.IntegerField('申請年月日', null=False, blank=False)
    AGREE_DATE =  models.IntegerField('承認年月日', null=True, blank=True)
    AGREE_LTD_CD = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    AGREE_EMP_ID = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)
    WORK_STAT =  models.IntegerField('申請状態', null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'T_REQUEST'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','TARGET_DATE'],
                name='request_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.TARGET_DATE)

#申請休憩テーブル
class T_request_rest(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    #uuid = models.UUIDField(default=uuid.uuid4,
    #                        primary_key=True, editable=False)

    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    TARGET_DATE =  models.IntegerField('年月日', null=False, blank=False)
    REST_NO =  models.IntegerField('No', null=False, blank=False)
    REST_START_TIME = models.CharField('休憩開始時刻', max_length=20,  null=True, blank=True)
    REST_START_NEXT_FLG =  models.IntegerField('休憩開始翌日フラグ', null=False, blank=False)
    REST_END_TIME = models.CharField('休憩終了時刻', max_length=20,  null=True, blank=True)
    REST_END_NEXT_FLG =  models.IntegerField('休憩終了フラグ', null=False, blank=False)

    #request = models.ForeignKey(
    #    T_request,
    #    on_delete=models.CASCADE)
    class Meta:
        managed = True
        db_table = 'T_REQUEST_REST'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','TARGET_DATE','REST_NO'],
                name='request_rest_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.TARGET_DATE)  + ' : ' + str(self.REST_NO)

#休暇申請テーブル
class T_request_holiday(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    KBN =  models.IntegerField('出退勤区分', null=False, blank=False)
    TARGET_DATE =  models.IntegerField('年月日', null=False, blank=False)
    TRANSFER_DATE =  models.IntegerField('振替年月日', null=True, blank=True)
    REQUEST_DATE =  models.IntegerField('申請年月日', null=False, blank=False)
    AGREE_DATE =  models.IntegerField('承認年月日', null=True, blank=True)
    AGREE_LTD_CD = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    AGREE_EMP_ID = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)
    MEMO = models.CharField('備考', max_length=120, null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'T_REQUEST_HOLIDAY'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','TARGET_DATE'],
                name='request_holiday_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.TARGET_DATE)
"""
#月次勤怠レポートテーブル
class T_getuji_kintai(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    TARGET_DATE =  models.IntegerField('年月日', null=False, blank=False)

    SHOTEI_COUNT =  models.CharField('月間所定労働日数', max_length=6, null=False, blank=False)
    WORK_COUNT =  models.CharField('月間出勤日数', max_length=6, null=False, blank=False)
    HOTEIGAI_WORK_COUNT =  models.CharField('法定外休日出勤日数', max_length=6, null=False, blank=False)
    KEKKIN_COUNT =  models.CharField('欠勤日数', max_length=6, null=False, blank=False)
    LATE_COUNT =  models.CharField('遅刻日数', max_length=6, null=False, blank=False)
    EARLY_COUNT =  models.CharField('早退日数', max_length=6, null=False, blank=False)
    ALL_WORK_TIME =  models.CharField('総労働時間', max_length=6, null=False, blank=False)
    JITU_WORK_TIME =  models.CharField('実働時間', max_length=6, null=False, blank=False)
    OVERTIME_TIME =  models.CharField('残業時間', max_length=6, null=False, blank=False)
    HOTEIKYU_TIME =  models.CharField('法定休日労働時間', max_length=6, null=False, blank=False)
    MIDNIGHT_TIME =  models.CharField('深夜労働時間', max_length=6, null=False, blank=False)
    LATE_TIME =  models.CharField('遅刻時間', max_length=6, null=False, blank=False)
    EARLY_TIME =  models.CharField('早退時間', max_length=6, null=False, blank=False)
    SHOTEI_LESS_TIME =  models.CharField('所定不足時間', max_length=6, null=False, blank=False)
    HOLIDAY_COUNT =  models.CharField('公休日数', max_length=6, null=False, blank=False)
    YUKYU_COUNT =  models.CharField('有給休暇日数', max_length=6, null=False, blank=False)
    YUKYU_ZAN_COUNT =  models.CharField('有給休暇残数', max_length=6, null=False, blank=False)
    KAKIKYU_COUNT =  models.CharField('夏季休暇日数', max_length=6, null=False, blank=False)
    KAKIKYU_ZAN_COUNT =  models.CharField('夏季休暇残数', max_length=6, null=False, blank=False)
    FURIKYU_COUNT =  models.CharField('振替休日日数', max_length=6, null=False, blank=False)
    FURIKYU_ZAN_COUNT =  models.CharField('振替休日残数', max_length=6, null=False, blank=False)
    DAIKYU_COUNT =  models.CharField('代休日数', max_length=6, null=False, blank=False)
    DAIKYU_ZAN_COUNT =  models.CharField('代休残数', max_length=6, null=False, blank=False)
    KYUSHOKU_COUNT =  models.CharField('休職日数', max_length=6, null=False, blank=False)
    MONTH_YUKYU_COUNT =  models.CharField('有休（当月取得）', max_length=6, null=False, blank=False)
    MONTH_KAKIKYU_COUNT =  models.CharField('夏休（当月取得）', max_length=6, null=False, blank=False)
    AGREE_FLG =  models.IntegerField('月次承認フラグ', null=False, blank=False)
    AGREE_DATE =  models.IntegerField('承認年月日', null=True, blank=True)
    AGREE_LTD_CD = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    AGREE_EMP_ID = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'T_GETUJI_KINTAI'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','TARGET_DATE'],
                name='getuji_kintai_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.TARGET_DATE)
"""
#月次レポートテーブル
class T_getuji_report(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    TARGET_MONTH =  models.IntegerField('年月', null=False, blank=False)
    SHOTEI_TIME =  models.CharField('所定時間', max_length=6, null=False, blank=False)
    SHOTEINAI_WORK_TIME =  models.CharField('所定内労働時間', max_length=6, null=False, blank=False)
    HOTEINAI_OVER_TIME =  models.CharField('法定内時間外労働時間', max_length=6, null=False, blank=False)
    HOTEI_OVER_TIME =  models.CharField('法定時間外労働時間', max_length=6, null=False, blank=False)
    HOTEIGAIKYU_TIME =  models.CharField('法定外休日労働時間', max_length=6, null=False, blank=False)
    HOTEIKYU_TIME =  models.CharField('法定休日労働時間', max_length=6, null=False, blank=False)
    MIDNIGHT_TIME =  models.CharField('深夜労働時間', max_length=6, null=False, blank=False)
    ALL_WORK_TIME =  models.CharField('総労働時間', max_length=6, null=False, blank=False)
    JITU_WORK_TIME =  models.CharField('実働時間', max_length=6, null=False, blank=False)
    LATE_TIME =  models.CharField('遅刻時間', max_length=6, null=False, blank=False)
    EARLY_TIME =  models.CharField('早退時間', max_length=6, null=False, blank=False)
    SHOTEI_LESS_TIME =  models.CharField('所定不足時間', max_length=6, null=False, blank=False)
    OVERTIME_TIME =  models.CharField('残業時間', max_length=6, null=False, blank=False)
    SHOTEI_COUNT =  models.CharField('月間所定労働日数', max_length=6, null=False, blank=False)
    WORK_COUNT =  models.CharField('月間出勤日数', max_length=6, null=False, blank=False)
    HOTEIGAI_WORK_COUNT =  models.CharField('法定外休日出勤日数', max_length=6, null=False, blank=False)
    HOTEI_WORK_COUNT =  models.CharField('法定休日出勤日数', max_length=6, null=False, blank=False)
    KEKKIN_COUNT =  models.CharField('欠勤日数', max_length=6, null=False, blank=False)
    LATE_COUNT =  models.CharField('遅刻日数', max_length=6, null=False, blank=False)
    EARLY_COUNT =  models.CharField('早退日数', max_length=6, null=False, blank=False)
    HOLIDAY_COUNT =  models.CharField('公休日数', max_length=6, null=False, blank=False)
    YUKYU_COUNT =  models.CharField('有給休暇日数', max_length=6, null=False, blank=False)
    YUKYU_ZAN_COUNT =  models.CharField('有給休暇残数', max_length=6, null=False, blank=False)
    KAKIKYU_COUNT =  models.CharField('夏季休暇日数', max_length=6, null=False, blank=False)
    KAKIKYU_ZAN_COUNT =  models.CharField('夏季休暇残数', max_length=6, null=False, blank=False)
    FURIKYU_COUNT =  models.CharField('振替休日日数', max_length=6, null=False, blank=False)
    FURIKYU_ZAN_COUNT =  models.CharField('振替休日残数', max_length=6, null=False, blank=False)
    DAIKYU_COUNT =  models.CharField('代休日数', max_length=6, null=False, blank=False)
    DAIKYU_ZAN_COUNT =  models.CharField('代休残数', max_length=6, null=False, blank=False)
    TOKUKYU_COUNT =  models.CharField('特別休暇日数', max_length=6, null=False, blank=False)
    KYUSHOKU_COUNT =  models.CharField('休職日数', max_length=6, null=False, blank=False)
    MONTH_YUKYU_COUNT =  models.CharField('有休（当月取得）', max_length=6, null=False, blank=False)
    MONTH_KAKIKYU_COUNT =  models.CharField('夏休（当月取得）', max_length=6, null=False, blank=False)
    AM_YUKYU_COUNT =  models.CharField('午前有給休暇', max_length=6, null=False, blank=False)
    PM_YUKYU_COUNT =  models.CharField('午後有給休暇', max_length=6, null=False, blank=False)
    AGREE_FLG =  models.IntegerField('月次承認フラグ', null=False, blank=False)
    AGREE_DATE =  models.IntegerField('承認年月日', null=True, blank=True)
    AGREE_LTD_CD = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    AGREE_EMP_ID = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'T_GETUJI_REPORT'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','TARGET_MONTH'],
                name='getuji_report_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.TARGET_MONTH)

#日報テーブルT_DAILY_REPORT
class T_daily_report(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    LTD_CD = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    EMP_ID = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    TARGET_DATE =  models.IntegerField('年月日', null=False, blank=False)
    #TORIHIKISAKI =  models.CharField('取引先', max_length=8, null=True, blank=True)
    #PROJECT =  models.CharField('プロジェクト', max_length=8, null=True, blank=True)
    #GYOMU =  models.CharField('業務分類', max_length=8, null=True, blank=True)
    REPORT = models.CharField('日報', max_length=520,  null=True, blank=True)
    #GYOMU_YOTEI_TIME =  models.CharField('業務時間(予定)', max_length=6, null=True, blank=True)
    #GYOMU_JISEKI_TIME =  models.CharField('業務時間(実績)', max_length=6, null=True, blank=True)
    COM_LTD_CD = models.CharField('コメント所属CD', max_length=4,  null=True, blank=True)
    COM_EMP_ID = models.CharField('コメント社員番号', max_length=20,  null=True, blank=True)
    COMMENT = models.CharField('コメント', max_length=520,  null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'T_DAILY_REPORT'
        constraints = [
            models.UniqueConstraint(
                fields=['LTD_CD','EMP_ID','TARGET_DATE'],
                name='daily_report_unique'
            ),
        ]

    def __str__(self):
        return self.LTD_CD + ' : ' + self.EMP_ID + ' : ' + str(self.TARGET_DATE)

#会社情報を格納するテーブル
class Company(models.Model):
    name      = models.CharField(max_length=256)
    industory = models.CharField(max_length=256)
    location  = models.CharField(max_length=256)

    class Meta:
        managed = True
    def __str__(self):
        return self.name

#会社に紐づく従業員情報を格納するテーブル
class Employee(models.Model):
    name    = models.CharField(max_length=256)
    age     = models.PositiveIntegerField()
    company = models.ForeignKey(Company,related_name='Employees',on_delete=models.CASCADE,null=True)

    class Meta:
        managed = True
    def __str__(self):
        return self.name

'''
# Create your models here.
class SubmitAttendance(models.Model):

    class Meta:
        db_table = 'attendance'

    PLACES = (
        (1, 'Bar Foo'),
        (2, 'Bar Baz'),
        (3, 'Bar Qux'),
        (4, 'Bar Quux'),
        (5, 'Bar Corge'),
        (6, 'Bar Grault'),
    )
    IN_OUT = (
        (1, 'IN'),
        (0, 'OUT'),
    )

    staff = models.ForeignKey(get_user_model(), verbose_name='スタッフ', on_delete=models.CASCADE, default=None)
    place = models.IntegerField(verbose_name='出勤場所名', choices=PLACES, default=None)
    in_out = models.IntegerField(verbose_name='IN/OUT', choices=IN_OUT, default=None)
    time = models.TimeField(verbose_name='打刻時間')
    date = models.DateField(verbose_name='打刻日')

    #辞書化
    place_dict = dict(PLACES)
    in_out_dict = dict(IN_OUT)

    def __str__(self):
        return  str(User.objects.get(id=self.staff_id)) + ' : ' + str(self.place_dict[self.place]) + ' ' + str(self.in_out_dict[self.in_out])

class Fee(SubmitAttendance):

    class Meta:
        db_table = 'fee'

    today = models.DateField(verbose_name='出勤日')
    staff = SubmitAttendance.staff()
    start = SubmitAttendance.objects.get(in_out=1, staff_id=staff, date=today).time
    end = SubmitAttendance.objects.get(in_out=0, staff_id=staff, date=today).time
    howlong_hours = ((end - start).seconds) / 3600
    fee = howlong_hours * 900
'''


