"""
テスト専用設定ファイル。
PostgreSQL の代わりに SQLite（インメモリ）を使い、外部サービスへの依存を排除する。

使い方:
    python manage.py test --settings=config.settings_test attendance
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'test-secret-key-only-for-testing'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'users.apps.UsersConfig',
    'accounts.apps.AccountsConfig',
    'Evc_App.apps.EvcAppConfig',
    'Evc_Management.apps.EvcManagementConfig',
    'Evc_Owner.apps.EvcOwnerConfig',
    'Fms_Ocrform.apps.EvcOcrformConfig',
    'Fms_fileshare.apps.FmsFileshareConfig',
    'attendance.apps.AttendanceConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'sequences.apps.SequencesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATE_DIR = BASE_DIR / 'Template'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATE_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# テスト用 SQLite（インメモリ）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
    'kmsdatabase': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}

# テスト中はパスワードハッシュを軽量化してテスト速度を改善
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

AUTH_USER_MODEL = 'users.EvcUser'

ATTENDANCE_DB = 'kmsdatabase'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Evc_App 等で参照される設定（テスト時はダミー値で十分）
GOOGLE_OCR = False
GOOGLE_CLOUD_VISION_KEY = 'dummy.json'
KOKUZEI_WEBAPI = ''
USE_GOOGLE_CALENDAR = False
EVC_URL = '/EvcData/'
EVC_HELP_URL = '/help/'
EVC_ROOT = '/tmp/evc_root/'
EVC_HELP_DIR = '/tmp/evc_help/'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

# メール送信を抑制
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# ログ出力を抑制（テスト時のノイズ削減）
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {
        'handlers': ['null'],
    },
}
