import uuid

from django.db import models

# Create your models here.
from Kms_Attendance.commons.models import TimeStampBaseModel


#社員マスタ
class M_emp(TimeStampBaseModel):
#class M_emp(models.Model):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)
    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    emp_name = models.CharField('社員名', max_length=40, null=False, blank=False)
    kbn = models.IntegerField('区分', null=False, blank=False)
    emp_kana = models.CharField('フリガナ', max_length=80, null=False, blank=False)
    # EvcUserとリンクするため追加、ユニークで必須に
    user_id = models.EmailField('EvcユーザID', max_length=50, null=False, blank=False, unique=True)
    tofuken_cd = models.IntegerField('都道府県', null=False, blank=False)
    add_1 = models.CharField('住所１', max_length=100, null=True, blank=True)
    work_pat_cd = models.CharField('勤務パターンCD', max_length=4, null=False, blank=False, default='0')
    tel_no = models.CharField('電話番号', max_length=11, null=True, blank=True)
    mobile_no = models.CharField('携帯番号', max_length=11, null=True, blank=True)
    mail_add = models.CharField('メールアドレス', max_length=50, null=True, blank=True)
    sex = models.IntegerField('性別', null=False, blank=False)
    birthday = models.IntegerField('生年月日', null=True, blank=True)
    joined_date = models.IntegerField('入社日', null=True, blank=True)
    memo = models.CharField('備考', max_length=120, null=True, blank=True)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_emp'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id'],
                name='emp_unique'
            ),
        ]
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id
#所属マスタ
class M_ltd(TimeStampBaseModel):
    #id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)

    ltd_cd = models.CharField('所属CD', max_length=4, primary_key=True)
    ltd_name = models.CharField('所属名', max_length=40,  null=False, blank=False)
    ltd_kana = models.CharField('フリガナ', max_length=80, null=False, blank=False)
    ltd_tdfuken_cd = models.IntegerField('本社所在', null=False, blank=False)
    ltd_add = models.CharField('住所', max_length=100, null=True, blank=True)
    daihyo_name = models.CharField('代表者名', max_length=40, null=False, blank=False)
    daihyo_mail = models.CharField('代表メールアドレス', max_length=50, null=True, blank=True)
    tanto_name = models.CharField('担当者名', max_length=40, null=True, blank=True)
    tanto_mail = models.CharField('担当者メールアドレス', max_length=50, null=True, blank=True)
    tel_no = models.CharField('電話番号', max_length=11, null=True, blank=True)
    fax_no = models.CharField('FAX番号', max_length=11, null=True, blank=True)
    memo = models.CharField('備考', max_length=120, null=True, blank=True)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_ltd'
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.ltd_cd + ' : ' + self.ltd_name
#祝日マスタ
class M_holiday(TimeStampBaseModel):
    holiday_ymd = models.IntegerField('年月日', primary_key=True)
    holiday_name = models.CharField('祝祭日名称', max_length=40, null=False, blank=False)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_holiday'

    def __str__(self):
        return str(self.holiday_ymd) + ' : ' + self.holiday_name
#都道府県マスタ
class M_tdfuken(TimeStampBaseModel):
    tofuken_cd = models.IntegerField('都道府県コード', primary_key=True)
    tdfuken_name = models.CharField('都道府県名', max_length=8, null=False, blank=False)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_tdfuken'

    def __str__(self):
        return str(self.tofuken_cd) + ' : ' + self.tdfuken_name

#所定勤務マスタ
class M_work_pat(TimeStampBaseModel):
    work_pat_cd = models.CharField('勤務パターンCD', max_length=4, primary_key=True)
    work_pat_name = models.CharField('勤務パターン名', max_length=16, null=False, blank=False)
    start_time = models.CharField('開始時刻', max_length=5, null=False, blank=False)
    end_time = models.CharField('終了時刻', max_length=5, null=False, blank=False)
    work_time = models.CharField('稼働時間', max_length=5, null=False, blank=False)
    rest1_start_time = models.CharField('休憩１開始時刻', max_length=5, null=False, blank=False)
    rest1_end_time = models.CharField('休憩１終了時刻', max_length=5, null=False, blank=False)
    rest1_time = models.CharField('休憩時間１', max_length=5, null=False, blank=False)
    rest2_start_time = models.CharField('休憩2開始時刻', max_length=5, null=False, blank=False)
    rest2_end_time = models.CharField('休憩2終了時刻', max_length=5, null=False, blank=False)
    rest2_time = models.CharField('休憩時間2', max_length=5, null=False, blank=False)
    night_start_time = models.CharField('深夜勤務開始時刻', max_length=5, null=False, blank=False)
    night_end_time = models.CharField('深夜勤務終了時刻', max_length=5, null=False, blank=False)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_work_pat'

    def __str__(self):
        return str(self.work_pat_cd) + ' : ' + self.work_pat_name

#年度切替マスタ
class M_nendo(TimeStampBaseModel):
    ltd_cd = models.CharField('所属CD', max_length=4, primary_key=True)
    nendo_start_md = models.IntegerField('月日', null=False, blank=False)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_nendo'

    def __str__(self):
        return self.ltd_cd + ' : ' + str(self.nendo_start_md)

#勤務区分マスタ
class M_kbn(TimeStampBaseModel):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)

    zokusei_cd = models.IntegerField('属性値', null=False, blank=False)
    zokusei_name = models.CharField('属性名', max_length=16, null=False, blank=False)
    kbn = models.IntegerField('区分値', null=False, blank=False)
    kbn_name = models.CharField('区分名', max_length=16, null=False, blank=False)
    kbn_order = models.IntegerField('表示順', null=False, blank=False)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_kbn'
        constraints = [
            models.UniqueConstraint(
                fields=['zokusei_cd','kbn'],
                name='kbn_unique'
            ),
        ]

    def __str__(self):
        return self.kbn_name

#有給付与管理テーブル
class M_yukyu(TimeStampBaseModel):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)

    ltd_cd = models.CharField('所属CD', max_length=4, null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20, null=False, blank=False)
    nendo = models.IntegerField('年度', null=False, blank=False)
    new_count = models.IntegerField('当年度付与数', null=True, blank=True)
    carry_over = models.IntegerField('前年繰越日数', null=True, blank=True)
    all_count = models.IntegerField('当年度総数', null=True, blank=True)
    used_count = models.IntegerField('当年度取得数', null=True, blank=True)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 'm_yukyu'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','nendo'],
                name='yukyu_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.nendo)

#休暇管理テーブル
class T_leave(TimeStampBaseModel):
    id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)
    #id = models.IntegerField('id', primary_key=True)

    ltd_cd = models.CharField('所属CD', max_length=4, null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20, null=False, blank=False)
    nendo = models.IntegerField('年度', null=False, blank=False)
    kbn =  models.IntegerField('出退勤区分', null=False, blank=False)
    modify_date =  models.IntegerField('休暇修正日', null=True, blank=True)
    new_count =  models.CharField('当年度付与数', max_length=6, null=True, blank=True)
    carry_over =  models.CharField('前年繰越日数', max_length=6, null=True, blank=True)
    all_count =  models.CharField('当年度総数', max_length=6, null=True, blank=True)
    used_count =  models.CharField('当年度取得数', max_length=6, null=True, blank=True)
    remaining_count =  models.CharField('残数調整', max_length=6, null=True, blank=True)
    expiration_date =  models.IntegerField('有効期限', null=True, blank=True)
    reason = models.CharField('理由', max_length=120, null=True, blank=True)
    #update_date = models.CharField('更新日時', max_length=20, null=False, blank=False)
    #update_id = models.CharField('更新者ID', max_length=20, null=False, blank=False)
    #ins_date = models.CharField('登録日時', max_length=20, null=False, blank=False)
    #ins_id = models.CharField('登録者ID', max_length=20, null=False, blank=False )
    #del_flg = models.IntegerField('削除フラグ', null=False, blank=False)

    class Meta:
        managed = True
        db_table = 't_leave'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','nendo','kbn'],
                name='leave_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.nendo)

#打刻テーブル
class T_time_stamp(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    #uuid = models.UUIDField(default=uuid.uuid4,
    #                        primary_key=True, editable=False)

    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    target_date =  models.IntegerField('年月日', null=False, blank=False)
    kbn =  models.IntegerField('出退勤区分', null=False, blank=False)
    start_time = models.CharField('出社時刻（打刻）', max_length=20,  null=True, blank=True)
    corret_start_time = models.CharField('出社時刻（訂正）', max_length=20,  null=True, blank=True)
    end_time = models.CharField('退社時刻（打刻）', max_length=20,  null=True, blank=True)
    corret_end_time = models.CharField('退社時刻（訂正）', max_length=20,  null=True, blank=True)
    out_start_time = models.CharField('外出開始時刻', max_length=20,  null=True, blank=True)
    out_end_time = models.CharField('外出開始時刻', max_length=20,  null=True, blank=True)
    i_do = models.CharField('緯度', max_length=20,  null=True, blank=True)
    ke_id = models.CharField('経度', max_length=20,  null=True, blank=True)
    work_stat =  models.IntegerField('申請状態', null=True, blank=True)
    work_del_flg =  models.IntegerField('勤務削除', null=True, blank=True)

    # # M_emp モデルへのリレーション
    # emp = models.ForeignKey(M_emp, on_delete=models.CASCADE,
    #                         related_name='time_stamps',
    #                         to_field='id')  # M_emp の id を使ってリレーション

    class Meta:
        managed = True
        db_table = 't_time_stamp'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','target_date'],
                name='time_stamp_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.target_date)
#申請テーブル
class T_request(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    #uuid = models.UUIDField(default=uuid.uuid4,
    #                        primary_key=True, editable=False)

    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    target_date =  models.IntegerField('年月日', null=False, blank=False)
    kbn =  models.IntegerField('出退勤区分', null=False, blank=False)
    start_time = models.CharField('出社時刻（打刻）', max_length=20,  null=True, blank=True)
    corret_start_time = models.CharField('出社時刻（訂正）', max_length=20,  null=True, blank=True)
    end_time = models.CharField('退社時刻（打刻）', max_length=20,  null=True, blank=True)
    corret_end_time = models.CharField('退社時刻（訂正）', max_length=20,  null=True, blank=True)
    end_next_flg =  models.IntegerField('退社翌日フラグ', null=False, blank=False)
    expenses =  models.IntegerField('経費', null=True, blank=True)
    memo = models.CharField('備考', max_length=120, null=True, blank=True)
    agree_comment = models.CharField('所属長コメント', max_length=120, null=True, blank=True)
    request_date =  models.IntegerField('申請年月日', null=False, blank=False)
    agree_date =  models.IntegerField('承認年月日', null=True, blank=True)
    agree_ltd_cd = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    agree_emp_id = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)
    work_stat =  models.IntegerField('申請状態', null=True, blank=True)

    class Meta:
        managed = True
        db_table = 't_request'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','target_date'],
                name='request_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.target_date)

#申請休憩テーブル
class T_request_rest(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    #uuid = models.UUIDField(default=uuid.uuid4,
    #                        primary_key=True, editable=False)

    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    target_date =  models.IntegerField('年月日', null=False, blank=False)
    rest_no =  models.IntegerField('No', null=False, blank=False)
    rest_start_time = models.CharField('休憩開始時刻', max_length=20,  null=True, blank=True)
    rest_start_next_flg =  models.IntegerField('休憩開始翌日フラグ', null=False, blank=False)
    rest_end_time = models.CharField('休憩終了時刻', max_length=20,  null=True, blank=True)
    rest_end_next_flg =  models.IntegerField('休憩終了フラグ', null=False, blank=False)

    #request = models.ForeignKey(
    #    T_request,
    #    on_delete=models.CASCADE)
    class Meta:
        managed = True
        db_table = 't_request_rest'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','target_date','rest_no'],
                name='request_rest_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.target_date)  + ' : ' + str(self.rest_no)

#休暇申請テーブル
class T_request_holiday(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    kbn =  models.IntegerField('出退勤区分', null=False, blank=False)
    target_date =  models.IntegerField('年月日', null=False, blank=False)
    transfer_date =  models.IntegerField('振替年月日', null=True, blank=True)
    request_date =  models.IntegerField('申請年月日', null=False, blank=False)
    agree_date =  models.IntegerField('承認年月日', null=True, blank=True)
    agree_ltd_cd = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    agree_emp_id = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)
    memo = models.CharField('備考', max_length=120, null=True, blank=True)

    class Meta:
        managed = True
        db_table = 't_request_holiday'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','target_date'],
                name='request_holiday_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.target_date)
"""
#月次勤怠レポートテーブル
class T_getuji_kintai(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    target_date =  models.IntegerField('年月日', null=False, blank=False)

    shotei_count =  models.CharField('月間所定労働日数', max_length=6, null=False, blank=False)
    work_count =  models.CharField('月間出勤日数', max_length=6, null=False, blank=False)
    hoteigai_work_count =  models.CharField('法定外休日出勤日数', max_length=6, null=False, blank=False)
    kekkin_count =  models.CharField('欠勤日数', max_length=6, null=False, blank=False)
    late_count =  models.CharField('遅刻日数', max_length=6, null=False, blank=False)
    early_count =  models.CharField('早退日数', max_length=6, null=False, blank=False)
    all_work_time =  models.CharField('総労働時間', max_length=6, null=False, blank=False)
    jitu_work_time =  models.CharField('実働時間', max_length=6, null=False, blank=False)
    overtime_time =  models.CharField('残業時間', max_length=6, null=False, blank=False)
    hoteikyu_time =  models.CharField('法定休日労働時間', max_length=6, null=False, blank=False)
    midnight_time =  models.CharField('深夜労働時間', max_length=6, null=False, blank=False)
    late_time =  models.CharField('遅刻時間', max_length=6, null=False, blank=False)
    early_time =  models.CharField('早退時間', max_length=6, null=False, blank=False)
    shotei_less_time =  models.CharField('所定不足時間', max_length=6, null=False, blank=False)
    holiday_count =  models.CharField('公休日数', max_length=6, null=False, blank=False)
    yukyu_count =  models.CharField('有給休暇日数', max_length=6, null=False, blank=False)
    yukyu_zan_count =  models.CharField('有給休暇残数', max_length=6, null=False, blank=False)
    kakikyu_count =  models.CharField('夏季休暇日数', max_length=6, null=False, blank=False)
    kakikyu_zan_count =  models.CharField('夏季休暇残数', max_length=6, null=False, blank=False)
    furikyu_count =  models.CharField('振替休日日数', max_length=6, null=False, blank=False)
    furikyu_zan_count =  models.CharField('振替休日残数', max_length=6, null=False, blank=False)
    daikyu_count =  models.CharField('代休日数', max_length=6, null=False, blank=False)
    daikyu_zan_count =  models.CharField('代休残数', max_length=6, null=False, blank=False)
    kyushoku_count =  models.CharField('休職日数', max_length=6, null=False, blank=False)
    month_yukyu_count =  models.CharField('有休（当月取得）', max_length=6, null=False, blank=False)
    month_kakikyu_count =  models.CharField('夏休（当月取得）', max_length=6, null=False, blank=False)
    agree_flg =  models.IntegerField('月次承認フラグ', null=False, blank=False)
    agree_date =  models.IntegerField('承認年月日', null=True, blank=True)
    agree_ltd_cd = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    agree_emp_id = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'T_GETUJI_KINTAI'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','target_date'],
                name='getuji_kintai_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.target_date)
"""
#月次レポートテーブル
class T_getuji_report(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    target_month =  models.IntegerField('年月', null=False, blank=False)
    shotei_time =  models.CharField('所定時間', max_length=6, null=False, blank=False)
    shoteinai_work_time =  models.CharField('所定内労働時間', max_length=6, null=False, blank=False)
    hoteinai_over_time =  models.CharField('法定内時間外労働時間', max_length=6, null=False, blank=False)
    hotei_over_time =  models.CharField('法定時間外労働時間', max_length=6, null=False, blank=False)
    hoteigaikyu_time =  models.CharField('法定外休日労働時間', max_length=6, null=False, blank=False)
    hoteikyu_time =  models.CharField('法定休日労働時間', max_length=6, null=False, blank=False)
    midnight_time =  models.CharField('深夜労働時間', max_length=6, null=False, blank=False)
    all_work_time =  models.CharField('総労働時間', max_length=6, null=False, blank=False)
    jitu_work_time =  models.CharField('実働時間', max_length=6, null=False, blank=False)
    late_time =  models.CharField('遅刻時間', max_length=6, null=False, blank=False)
    early_time =  models.CharField('早退時間', max_length=6, null=False, blank=False)
    shotei_less_time =  models.CharField('所定不足時間', max_length=6, null=False, blank=False)
    overtime_time =  models.CharField('残業時間', max_length=6, null=False, blank=False)
    shotei_count =  models.CharField('月間所定労働日数', max_length=6, null=False, blank=False)
    work_count =  models.CharField('月間出勤日数', max_length=6, null=False, blank=False)
    hoteigai_work_count =  models.CharField('法定外休日出勤日数', max_length=6, null=False, blank=False)
    hotei_work_count =  models.CharField('法定休日出勤日数', max_length=6, null=False, blank=False)
    kekkin_count =  models.CharField('欠勤日数', max_length=6, null=False, blank=False)
    late_count =  models.CharField('遅刻日数', max_length=6, null=False, blank=False)
    early_count =  models.CharField('早退日数', max_length=6, null=False, blank=False)
    holiday_count =  models.CharField('公休日数', max_length=6, null=False, blank=False)
    yukyu_count =  models.CharField('有給休暇日数', max_length=6, null=False, blank=False)
    yukyu_zan_count =  models.CharField('有給休暇残数', max_length=6, null=False, blank=False)
    kakikyu_count =  models.CharField('夏季休暇日数', max_length=6, null=False, blank=False)
    kakikyu_zan_count =  models.CharField('夏季休暇残数', max_length=6, null=False, blank=False)
    furikyu_count =  models.CharField('振替休日日数', max_length=6, null=False, blank=False)
    furikyu_zan_count =  models.CharField('振替休日残数', max_length=6, null=False, blank=False)
    daikyu_count =  models.CharField('代休日数', max_length=6, null=False, blank=False)
    daikyu_zan_count =  models.CharField('代休残数', max_length=6, null=False, blank=False)
    tokukyu_count =  models.CharField('特別休暇日数', max_length=6, null=False, blank=False)
    kyushoku_count =  models.CharField('休職日数', max_length=6, null=False, blank=False)
    month_yukyu_count =  models.CharField('有休（当月取得）', max_length=6, null=False, blank=False)
    month_kakikyu_count =  models.CharField('夏休（当月取得）', max_length=6, null=False, blank=False)
    am_yukyu_count =  models.CharField('午前有給休暇', max_length=6, null=False, blank=False)
    pm_yukyu_count =  models.CharField('午後有給休暇', max_length=6, null=False, blank=False)
    agree_flg =  models.IntegerField('月次承認フラグ', null=False, blank=False)
    agree_date =  models.IntegerField('承認年月日', null=True, blank=True)
    agree_ltd_cd = models.CharField('承認者所属CD', max_length=4,  null=True, blank=True)
    agree_emp_id = models.CharField('承認者社員番号', max_length=20,  null=True, blank=True)

    class Meta:
        managed = True
        db_table = 't_getuji_report'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','target_month'],
                name='getuji_report_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.target_month)

#日報テーブルT_DAILY_REPORT
class T_daily_report(TimeStampBaseModel):
    #id = models.AutoField(primary_key=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)

    ltd_cd = models.CharField('所属CD', max_length=4,  null=False, blank=False)
    emp_id = models.CharField('社員番号', max_length=20,  null=False, blank=False)
    target_date =  models.IntegerField('年月日', null=False, blank=False)
    #TORIHIKISAKI =  models.CharField('取引先', max_length=8, null=True, blank=True)
    #PROJECT =  models.CharField('プロジェクト', max_length=8, null=True, blank=True)
    #GYOMU =  models.CharField('業務分類', max_length=8, null=True, blank=True)
    report = models.CharField('日報', max_length=520,  null=True, blank=True)
    #GYOMU_YOTEI_TIME =  models.CharField('業務時間(予定)', max_length=6, null=True, blank=True)
    #GYOMU_JISEKI_TIME =  models.CharField('業務時間(実績)', max_length=6, null=True, blank=True)
    com_ltd_cd = models.CharField('コメント所属CD', max_length=4,  null=True, blank=True)
    com_emp_id = models.CharField('コメント社員番号', max_length=20,  null=True, blank=True)
    comment = models.CharField('コメント', max_length=520,  null=True, blank=True)

    class Meta:
        managed = True
        db_table = 't_daily_report'
        constraints = [
            models.UniqueConstraint(
                fields=['ltd_cd','emp_id','target_date'],
                name='daily_report_unique'
            ),
        ]

    def __str__(self):
        return self.ltd_cd + ' : ' + self.emp_id + ' : ' + str(self.target_date)
"""
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
"""
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


