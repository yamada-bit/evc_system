# import os
import csv
import logging
from io import TextIOWrapper

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import FormView

from commons.utils import ut_get_client_ip

# from Evc_App.sv_json import sv_load_jsonfile,sv_get_textlines
from Evc_App.sv_file import sv_get_owner_ryaku_name, sv_save_account
from Evc_App.views import OwnerTestMixin
from Evc_Management.forms import EvcAccountSaveForm
from users.models import MtAccount

logger = logging.getLogger(__name__)

# 科目登録（一括）
class EvcAccountSaveView(LoginRequiredMixin, OwnerTestMixin, FormView):
    template_name = 'Evc_Management/FE_AccountSave.html'
    form_class = EvcAccountSaveForm
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_form()
        owner_id = self.request.session.get('owner_id')
        owner_ryaku_name = sv_get_owner_ryaku_name(owner_id)
        # path_lists = [sv_helpurl(), 'AccountSave_help.html']
        # help_url = os.path.join(*path_lists).replace(os.sep,'/')
        context = {
            'form': form,
            'process_title': '科目登録（一括）',
            'owner_ryaku_name': owner_ryaku_name
            # 'help_url': help_url
        }
        return context

    def form_valid(self, form):
        try:
            file = self.request.FILES['accountcsv']
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcAccountSaveView import csv {file.name}')
            rtn = self.save_account_csv(file)
        except Exception:
            logger.exception(f'{ut_get_client_ip(self.request)} '
                            'EvcAccountSaveView exception')
            rtn = False

        if rtn:
            messages.success(self.request, f'{rtn} 件 科目登録に成功しました。')
            logger.info(f'{ut_get_client_ip(self.request)} '
                        f'EvcAccountSaveView {rtn} 件 科目登録に成功しました。')
        else:
            messages.error(self.request, '科目登録に失敗しました。')
            logger.error(f'{ut_get_client_ip(self.request)} '
                        'EvcAccountSaveView 科目登録に失敗しました。')
        return self.render_to_response(self.get_context_data(form=form))
    def form_invalid(self, form):
        messages.error(self.request, 'アップロードに失敗しました。')
        err = form.errors.as_text()
        logger.error(f'{ut_get_client_ip(self.request)} '
                     f'EvcAccountSaveView アップロードに失敗しました {err}')
        return super().form_invalid(form)
    def save_account_csv(self, file):
        user_id = self.request.user.user_id
        # owner_id = get_owner_id(user_id)
        owner_id = self.request.session.get('owner_id')

        csv_data = TextIOWrapper(file, encoding='CP932')
        reader = csv.reader(csv_data)
        # ラベルデータをスキップする
        header = next(reader)
        cnt = 0
        for line in reader:
            if len(line) < 2:
                continue
            account_id = line[0]
            if 20 < len(account_id):
                continue
            account_name = line[1]
            if 50 < len(account_name):
                continue
            try:
                account_obj = MtAccount.objects.get(account_id=account_id)
                kubun = 'change'
            except MtAccount.DoesNotExist:
                account_id = '0'
                kubun = 'new'
            check = check_account_name(owner_id, account_id, account_name)
            if not check:
                logger.error(f'EvcAccountSaveView Same account exists {account_id=}')
                continue

            # type = line[4]
            # if type == '顧客':
            #     account_type = 1
            # elif type == '仕入先':
            #     account_type = 2
            # else:
            #     account_type = 0
            # delete_flg = line[13]
            # if delete_flg == 'true':
            #     delete_flg = 1
            # else:
            #     delete_flg = 0

            data = {
                'account_id': account_id,
                'account_name': account_name,
                # 'owner_id': owner_id,
                # 'corporate_number': line[3] if len(line[3]) < 14 else '',
            }
            rtn = sv_save_account(data, user_id, kubun)
            if not rtn:
                return cnt
            else:
                cnt += 1
        return cnt
# 同一科目名のチェック
def check_account_name(owner_id, account_id, account_name):
    accountobjs = MtAccount.objects.filter(account_name=account_name)
    for data in accountobjs:
        if account_id != data.account_id:
            logger.debug(f'MtAccount 同一科目名レコードあり {data.account_id} : {account_name}')
            return False
    return True
