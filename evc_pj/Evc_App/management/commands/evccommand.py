from django.core.management.base import BaseCommand
import os
import shutil

from users.models import HtEvidence
from Evc_App.sv_file import sv_get_processed_ym_path

#  c:\EVCProject\Evc_Pj>c:\EVCProject\venv\Scripts\python.exe manage.py evccommand test1 c:\test.jpg

class Command(BaseCommand):
    help = 'EVCコマンド'

    def add_arguments(self, parser):
        parser.add_argument('user', help='ユーザID', type=str)    # 位置引数（必須引数）
        parser.add_argument('path', help='ファイル名', type=str)    # 位置引数（必須引数）
        # parser.add_argument('--user', nargs='?', help='ユーザID')         # オプション引数
        # python manage.py evccommand C:\\Evc_root\\terst.pdf --user test1
        # python manage.py evccommand terst1 C:\\Evc_root\\SO24040001_root
    def handle(self, *args, **options):
        path = options.get('path', None)
        user_id = options.get('user', None)
        print('Start batch!')
        if not user_id:
            print('Please specify the userid.')
            user_id = 'test1'
            # return -1
        if not path:
            print('Please specify the path.')
            path = '/data_root/evc_root'
            # return -2
        print(path)
        print(user_id)

        ret = self.move_image(path)

        print(str(ret))
        return 0

    def move_image(self, rootfolder):
        copy = True
        cnt = 0
        objs = HtEvidence.objects.filter(rireki_kbn='D').order_by('create_date')
        for obj in objs:
            if obj.evidence_id:
                try:
                    ym_dir = sv_get_processed_ym_path(rootfolder, obj.processed_ym)
                    src = os.path.join(ym_dir, 'img', obj.evidence_id + '.jpg').replace(os.sep,'/')
                    if os.path.exists(src):
                        dest_dir = os.path.join(ym_dir, 'del').replace(os.sep,'/')
                        if not os.path.isdir(dest_dir):
                            os.makedirs(dest_dir)
                        dst = os.path.join(dest_dir, obj.evidence_id + '.jpg').replace(os.sep,'/')
                        # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
                        if copy:
                            shutil.copy(src, dst)
                        else:
                            shutil.move(src, dst)
                            cnt += 1
                except Exception as e:
                    print(e)
        return cnt
        # for root, dirs, files in os.walk(top=rootfolder):
        #     for dir in dirs:
        #         dirPath = os.path.join(root, dir)
        #         print(f'dirPath = {dirPath}')
        # for p in os.listdir(src_dir):
        #     try:
        #         shutil.move(os.path.join(src_dir, p), dst_dir)
        #         # shutil.moveの第二引数に、ファイルのパスを指定した場合は、移動先に同名ファイルがあると上書き
        #         if copy:
        #             shutil.copy(os.path.join(src_dir, p), dst_dir)
        #         else:
        #             shutil.move(os.path.join(src_dir, p), dst_dir)
        #     except Exception as e:
        #         print(e)
