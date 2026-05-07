import os
import datetime
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from django.conf import settings

logger = logging.getLogger(__name__)

"""
GoogleのOAuth 2.0プロトコルでは、セキュリティのためにHTTPSを使用することが必須となっています。
開発環境ではhttp://localhostが許可されていますが、設定やコードに問題がある場合でもこのエラーが発生する可能性があります。
OAuth 2.0の仕様では、通常HTTPSが必須ですが、開発環境ではhttp://localhostで動作するように特別に許可されています。
このエラーが出る場合、GoogleのクライアントライブラリがHTTPを拒否している可能性があります。
開発環境でHTTPを許可： 下のコードを追加し、HTTPを許可します。
"""
if settings.DEBUG:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def credentials_to_dict(credentials):
    """Google OAuth 2.0 トークンを辞書形式に変換"""
    return {
        'token': credentials.token, # アクセストークンを取得
        'refresh_token': credentials.refresh_token, # リフレッシュトークンを取得
        # 'id_token': credentials.id_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        # 'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None,
    }

def dict_to_credentials(credentials_dict):
    """辞書形式から credentials オブジェクトを復元"""
    """expiryをstrからdatetimeにする"""
    if credentials_dict['expiry']:
        expiry_date=datetime.datetime.fromisoformat(credentials_dict['expiry'])
    else:
        expiry_date = None
    return Credentials(
        token=credentials_dict['token'],
        refresh_token=credentials_dict['refresh_token'],
        token_uri=credentials_dict['token_uri'],
        client_id=credentials_dict['client_id'],
        client_secret=credentials_dict['client_secret'],
        # expiryをdatetimeに復元
        expiry=expiry_date,
    )
# Google Calendar APIクライアントの作成 
def get_calendar_service(credentials_dict):
    # credentials = Credentials(**credentials_dict)
    credentials = dict_to_credentials(credentials_dict)
    service = build('calendar', 'v3', credentials=credentials)
    return service

# def get_google_calendar_service():
#     creds = None
#     logger.debug('start')
#     # トークンファイルが存在する場合はロード
#     if os.path.exists(settings.GOOGLE_TOKEN_FILE):
#         creds = Credentials.from_authorized_user_file(settings.GOOGLE_TOKEN_FILE, settings.GOOGLE_SCOPES)
#     # トークンがない場合は新たに認証
#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             logger.debug('process1')
#             creds.refresh(Request())
#         else:
#             logger.debug('process2')
#             flow = InstalledAppFlow.from_client_secrets_file(settings.GOOGLE_CREDENTIALS_FILE, settings.GOOGLE_SCOPES)
#             logger.debug('process3')
#             creds = flow.run_local_server(port=0)
#         logger.debug('process4')
#         # トークンを保存
#         with open(settings.GOOGLE_TOKEN_FILE, 'w') as token:
#             token.write(creds.to_json())
#     logger.debug('end')
#     return build('calendar', 'v3', credentials=creds)
