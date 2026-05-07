from django.core.management.base import BaseCommand
from Fms_Ocrform.svt_tnw import sv_save_trasa_file

#  c:\EVCProject\Evc_Pj>c:\EVCProject\venv\Scripts\python.exe manage.py tnwcommand c:\test.jpg --user test1
#  c:\EVCProject\Evc_Pj>tnwocr.bat C:\Evc_root\くるめ生産履歴票１.pdf test1

class Command(BaseCommand):
    help = "生産履歴票OCRコマンド"

    def add_arguments(self, parser):
        parser.add_argument("user", help="ユーザID", type=str)    # 位置引数（必須引数）
        parser.add_argument("path", help="ファイル名", type=str)    # 位置引数（必須引数）
        # parser.add_argument('--user', nargs="?", help='ユーザID')         # オプション引数
        # python manage.py tnwcommand C:\\Evc_root\\くるめ生産履歴票１.pdf --user test1
    def handle(self, *args, **options):
        path = options.get("path", None)
        user_id = options.get("user", None)
        print('Start batch!')
        if not user_id:
            print('Please specify the userid.')
            user_id = 'test1'
            # return -1
        if not path:
            print('Please specify the path.')
            path = "/data_root/evc_root/くるめ生産履歴票６.pdf"
            # return -2
        print(path)
        print(user_id)

        # ファイルから情報をOCR抽出し連携ファイルに保存
        jsonfile = sv_save_trasa_file(path, user_id)

        print(jsonfile)
        return 0
