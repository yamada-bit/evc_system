# Create your models here.
from django.contrib import auth
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    # venv\Lib\site-packages\django\contrib\auth\models.py

    use_in_migrations = True

    def _create_user(self, user_id, user_name, password, **extra_fields):
        """
        Creates and saves a User with the given usename, email, and password.
        """
        if not user_id:
            raise ValueError('user_idを入力して下さい')
        user_id = self.normalize_email(user_id)
        user_name = self.model.normalize_username(user_name)
        user = self.model(user_id=user_id, **extra_fields)
        user.set_password(password)
        user.save(using=self.db)
        return user
    def create_user(self, user_id, user_name, password=None, **extra_fields):
        extra_fields.setdefault('delete_flg', 0)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(user_id, user_name, password, **extra_fields)

    def create_superuser(self, user_id, user_name, password, **extra_fields):
        extra_fields.setdefault('delete_flg', 0)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('is_staff=Trueである必要があります。')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('is_superuser=Trueである必要があります。')
        return self._create_user(user_id, user_name, password, **extra_fields)
    def with_perm(self, perm, is_active=True, include_superusers=True, backend=None, obj=None):
        if backend is None:
            backends = auth._get_backends(return_tuples=True)
            if len(backends) == 1:
                backend, _ = backends[0]
            else:
                raise ValueError(
                    "You have multiple authentication backends configured and "
                    "therefore must provide the `backend` argument."
                )
        elif not isinstance(backend, str):
            raise TypeError(
                f"backend must be a dotted import path string (got {backend!r})."
            )
        else:
            backend = auth.load_backend(backend)
        if hasattr(backend, "with_perm"):
            return backend.with_perm(
                perm,
                is_active=is_active,
                include_superusers=include_superusers,
                obj=obj,
            )
        return self.none()

# ユーザ管理マスタ
# カスタムユーザーモデル
class EvcUser(AbstractBaseUser, PermissionsMixin):
    """
    An abstract base class implementing a fully featured User model with
    admin-compliant permissions.
    Username and password are required. Other fields are optional.
    AbstractBaseUserは、パーミッション関連の機能を持っていないので、PermissionsMixinを同時に継承
    AbstractBaseUser で定義されているカラムが定義される
      password = models.CharField(_("password"), max_length=128)
      last_login = models.DateTimeField(_("last login"), blank=True, null=True)
    PermissionsMixin  で定義されているカラムが定義される
      is_superuser = models.BooleanField(default=False)
    """
    user_id = models.EmailField(verbose_name='メールアドレス', max_length=50,  primary_key=True)
    user_name = models.CharField(verbose_name='ユーザ名', max_length=50, null=True, blank=True)
    #AbstractBaseUser で定義のpassword をカラム名を指定する定義
    password = models.CharField(_("password"), max_length=128, db_column='user_pwd')
    # user_pwd = models.CharField(verbose_name='パスワード', max_length=50, null=True, blank=True)
    # email_address = models.EmailField(verbose_name='メールアドレス', max_length=50, null=True, blank=True)
    user_authority = models.CharField(verbose_name='権限', max_length=10, null=True, blank=True)
    owner_id = models.CharField(verbose_name='契約会社ID', max_length=10, null=True, blank=True)
    delete_flg = models.IntegerField(verbose_name='削除フラグ', null=False, blank=False,default=0)
    notes = models.CharField(verbose_name='備考', max_length=100, null=True, blank=True)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)

    #AbstractBaseUser で定義
    last_login = models.DateTimeField(_("last login"), blank=True, null=True)
    #PermissionsMixin  で定義
    is_superuser = models.BooleanField(default=False)
    #
    is_staff = models.BooleanField(_("staff status"), default=False)
    is_active = models.BooleanField(_("active"), default=True)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.user_name

    USERNAME_FIELD = 'user_id'
    EMAIL_FIELD = "user_id"
    REQUIRED_FIELDS = ['user_name']

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        db_table = 'mt_user'

    def clean(self):
        super().clean()
        self.user_id = self.__class__.objects.normalize_email(self.user_id)
        # self.email_address = self.__class__.objects.normalize_email(self.email_address)

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.user_id], **kwargs)

#契約会社マスタ
class SysOwner(models.Model):
    owner_id = models.CharField(verbose_name='契約会社ID', max_length=10,  primary_key=True)
    owner_name = models.CharField(verbose_name='会社名', max_length=50, null=True, blank=True)
    owner_ryaku_name = models.CharField(verbose_name='会社名（略称）', max_length=20, null=True, blank=True)
    charge_name = models.CharField(verbose_name='担当者名', max_length=50, null=True, blank=True)
    charge_email = models.EmailField(verbose_name='担当者メールアドレス', max_length=50, null=True, blank=True)
    tel_no = models.CharField(verbose_name='電話番号', max_length=20, null=True, blank=True)
    root_folder = models.CharField(verbose_name='ルートフォルダ', max_length=100, null=True, blank=True)
    notes = models.CharField(verbose_name='備考', max_length=100, null=True, blank=True)
    users_number = models.IntegerField(verbose_name='利用者数', null=False, blank=False, default=1, validators=[MinValueValidator(1)])
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)


    class Meta:
        managed = True # migrationsの管理対象とする
        verbose_name = _('契約会社')
        verbose_name_plural = _('契約会社')
        db_table = 'sys_owner'
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.owner_name

#部署マスタ
class MtDept(models.Model):
    dept_id = models.CharField(verbose_name='部署ID', max_length=10,  primary_key=True)
    dept_name = models.CharField(verbose_name='部署名', max_length=50, null=True, blank=True)
    acntlink_cd = models.CharField(verbose_name='会計連携CD', max_length=20, null=True, blank=True)
    delete_flg = models.IntegerField(verbose_name='削除フラグ', null=False, blank=False, default=0)
    notes = models.CharField(verbose_name='備考', max_length=100, null=True, blank=True)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)


    class Meta:
        managed = True
        verbose_name = _('部署')
        verbose_name_plural = _('部署')
        db_table = 'mt_dept'
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.dept_name
#フォルダ管理マスタ
class MtFolder(models.Model):
    folder_id = models.CharField(primary_key=True, max_length=20)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    category_name = models.CharField(max_length=20, blank=True, null=True)
    folder_name = models.CharField(max_length=50, blank=True, null=True)
    folder_path = models.CharField(max_length=100, blank=True, null=True)
    use_flg = models.DecimalField(max_digits=1, decimal_places=0)
    notes = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.DecimalField(max_digits=4, decimal_places=0)
    use_count = models.BigIntegerField(default=0)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('フォルダ管理')
        verbose_name_plural = _('フォルダ管理')
        db_table = 'mt_folder'
    def __str__(self):
        return (self.owner_id or 'None') + ':' + (self.category_name or 'None')

#取引先マスタ
class MtPartner(models.Model):
    partner_id = models.CharField(primary_key=True, max_length=10)
    partner_name = models.CharField(max_length=50, blank=True, null=True)
    partner_ryaku_name = models.CharField(max_length=20, blank=True, null=True)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    corporate_number = models.CharField(max_length=13, blank=True, null=True)
    partner_type = models.DecimalField(max_digits=1, decimal_places=0)
    charge_dept = models.CharField(max_length=30, blank=True, null=True)
    charge_name = models.CharField(max_length=30, blank=True, null=True)
    charge_email = models.CharField(max_length=50, blank=True, null=True)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    address1 = models.CharField(max_length=100, blank=True, null=True)
    address2 = models.CharField(max_length=100, blank=True, null=True)
    tel_no = models.CharField(max_length=20, blank=True, null=True)
    fax_no = models.CharField(max_length=20, blank=True, null=True)
    delete_flg = models.DecimalField(max_digits=1, decimal_places=0)
    notes = models.CharField(max_length=100, blank=True, null=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('取引先')
        verbose_name_plural = _('取引先')
        db_table = 'mt_partner'
    def __str__(self):
        return self.partner_name

#エビデンス情報
class TtEvidence(models.Model):
    evidence_id = models.CharField(primary_key=True, max_length=20)
    evidence_name = models.CharField(max_length=50, blank=True, null=True)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    pdf_name = models.CharField(max_length=50, blank=True, null=True)
    processed_ym = models.CharField(max_length=6, blank=True, null=True)
    category_name = models.CharField(max_length=20, blank=True, null=True)
    processed_date = models.DateField(blank=True, null=True)
    partner_id = models.CharField(max_length=10, blank=True, null=True)
    publisher_id = models.CharField(max_length=10, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    pdf_handbook = models.TextField(blank=True, null=True)
    tran_detail = models.JSONField(blank=True, null=True)
    evidence_data = models.BinaryField(blank=True, null=True)
    google_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    account_id = models.CharField(max_length=20, blank=True, null=True)
    account_desc = models.CharField(max_length=100, null=True, blank=True)
    slip_number = models.CharField(max_length=20, blank=True, null=True)
    payment_date = models.DateField(blank=True, null=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('エビデンス情報')
        verbose_name_plural = _('エビデンス情報')
        db_table = 'tt_evidence'
    def __str__(self):
        return self.evidence_name

    # def save(self, *args, **kwargs):
        # if not self.create_date:
        #     # self.create_date = timezone.now()   # 新規作成時の時刻を保存
        #     self.create_date = datetime.datetime.now()   # 新規作成時の時刻を保存
        # # self.update_date = timezone.now()
        # self.update_date = datetime.datetime.now()
        # return super(TtEvidence, self).save(*args, **kwargs)
#エビデンス履歴情報
class HtEvidence(models.Model):
    r_evidence_id = models.CharField(primary_key=True, max_length=20)
    rireki_kbn = models.CharField(max_length=1, blank=True, null=True)
    evidence_id = models.CharField(max_length=20, blank=True, null=True)
    evidence_name = models.CharField(max_length=50, blank=True, null=True)
    owner_id = models.CharField(max_length=10, blank=True, null=True)
    pdf_name = models.CharField(max_length=50, blank=True, null=True)
    processed_ym = models.CharField(max_length=6, blank=True, null=True)
    category_name = models.CharField(max_length=20, blank=True, null=True)
    processed_date = models.DateField(blank=True, null=True)
    partner_id = models.CharField(max_length=10, blank=True, null=True)
    publisher_id = models.CharField(max_length=10, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    pdf_handbook = models.TextField(blank=True, null=True)
    tran_detail = models.JSONField(blank=True, null=True)
    evidence_data = models.BinaryField(blank=True, null=True)
    google_amount = models.DecimalField(max_digits=21, decimal_places=8, blank=True, null=True)
    account_id = models.CharField(max_length=20, blank=True, null=True)
    account_desc = models.CharField(max_length=100, null=True, blank=True)
    slip_number = models.CharField(max_length=20, blank=True, null=True)
    payment_date = models.DateField(blank=True, null=True)
    create_user = models.CharField(max_length=30, blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    update_user = models.CharField(max_length=30, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        verbose_name = _('エビデンス履歴情報')
        verbose_name_plural = _('エビデンス履歴情報')
        db_table = 'ht_evidence'
    def __str__(self):
        return self.evidence_name

#科目マスタ
class MtAccount(models.Model):
    account_id = models.CharField(verbose_name='科目ID', max_length=20,  primary_key=True)
    account_name = models.CharField(verbose_name='科目名', max_length=50, null=True, blank=True)
    account_code = models.CharField(verbose_name='科目コード', max_length=20, blank=True, null=True)
    company_code = models.CharField(verbose_name='会社コード', max_length=20, null=True, blank=True)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)


    class Meta:
        managed = True
        verbose_name = _('科目')
        verbose_name_plural = _('科目')
        db_table = 'mt_account'
    #管理画面に表示されるモデル内のデータを判別するための文字列を定義
    def __str__(self):
        return self.account_name

#カテゴリフレーズマスタ
class MtPhrase(models.Model):
    phrase_id = models.CharField(verbose_name='フレーズID', max_length=20,  primary_key=True)
    owner_id = models.CharField(verbose_name='契約会社ID', max_length=10, blank=True, null=True)
    phrase = models.CharField(verbose_name='フレーズ', max_length=100, null=True, blank=True)
    category_name = models.CharField(verbose_name='カテゴリ名', max_length=20, blank=True, null=True)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)

    class Meta:
        managed = True
        verbose_name = _('カテゴリフレーズ')
        verbose_name_plural = _('カテゴリフレーズ')
        db_table = 'mt_phrase'
    def __str__(self):
        return (self.phrase or 'None') + ':' + (self.category_name or 'None')

#検出情報
class TtDetect(models.Model):
    evidence_id = models.CharField(verbose_name='エビデンスID', max_length=20, primary_key=True)
    category_name = models.CharField(verbose_name='カテゴリ名', max_length=20, blank=True, null=True)
    processed_date = models.DateField(verbose_name='取引日',blank=True, null=True)
    partner_name = models.CharField(verbose_name='取引先名', max_length=50, blank=True, null=True)
    publisher_name = models.CharField(verbose_name='発行元名', max_length=50, blank=True, null=True)
    total_amount = models.DecimalField(verbose_name='取引合計金額', max_digits=21, decimal_places=8, blank=True, null=True)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)

    class Meta:
        managed = True
        verbose_name = _('検出情報')
        verbose_name_plural = _('検出情報')
        db_table = 'tt_detect'

    def __str__(self):
        return (self.evidence_id or 'None') + ':' + (self.category_name or 'None')

# #契約会社対応ユーザマスタ
# class MtOwnerUser(models.Model):
#     id = models.UUIDField('id', default=uuid.uuid4, primary_key=True)

#     owner_id = models.CharField(verbose_name='契約会社ID', max_length=10,  null=False, blank=False)
#     user_id = models.CharField(verbose_name='対応ユーザID', max_length=50,  null=False, blank=False)
#     notes = models.CharField(verbose_name='備考', max_length=100, null=True, blank=True)
#     create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
#     create_date = models.DateTimeField(verbose_name='作成日時', null=True, blank=True)
#     update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
#     update_date = models.DateTimeField(verbose_name='更新日時', null=True, blank=True)

#     #管理画面に表示されるモデル内のデータを判別するための文字列を定義
#     def __str__(self):
#         return self.owner_id + ' : ' + self.user_id

#     class Meta:
#         managed = True # migrationsの管理対象とする
#         verbose_name = _('契約会社対応ユーザ')
#         verbose_name_plural = _('契約会社対応ユーザ')
#         db_table = 'mt_owner_user'
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['owner_id','user_id'],
#                 name='owner_user_unique'
#             ),
#         ]

