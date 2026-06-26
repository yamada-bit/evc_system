"""
認証ビュー（ログイン）。

勤怠システム専用のログイン画面を定義する。
ログアウトは Django 標準の LogoutView を urls.py で直接使用しているため、ここには含まない。
"""
import logging

from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

from ..forms import AttendanceLoginForm
from ..utils.log_utils import get_client_ip, log_user_id

logger = logging.getLogger(__name__)


class AttendanceLoginView(LoginView):
    """
    勤怠システム専用ログイン画面。

    【認証成功後の遷移先】
    打刻画面（attendance:attendance_punch）へリダイレクトする。
    Django デフォルトの settings.LOGIN_REDIRECT_URL は使わない。

    【セキュリティ上の注意】
    - ログイン成功時に session.cycle_key() でセッションIDを再生成し、
      セッション固定攻撃（Session Fixation Attack）を防止している。
      この処理を削除するとセキュリティ上の脆弱性になるため、絶対に消さないこと。
    - ユーザーIDはSHA256ハッシュ化してログに記録する（生のメールアドレスをログファイルに残さない）。
    - ログイン失敗時は原因（フォームエラー内容）をWARNINGで記録する。
      ブルートフォース攻撃の監視に活用できる。
    """
    template_name = "attendance/attendance_login.html"
    form_class = AttendanceLoginForm

    def get_success_url(self):
        return reverse_lazy('attendance:attendance_punch')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_name'] = 'alogin'
        return context

    def form_valid(self, form):
        # セッション固定攻撃対策：ログイン成功時にセッションキーを必ず再生成する
        self.request.session.cycle_key()

        user_id = form.cleaned_data.get('username')
        logger.info(
            f"[AUTH][LOGIN_SUCCESS] IP: {get_client_ip(self.request)} "
            f"ユーザー(HASH): {log_user_id(user_id)}"
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        err = form.errors.as_text()
        logger.warning(
            f"[AUTH][LOGIN_FAILED] IP: {get_client_ip(self.request)} "
            f"原因: {err.strip()}"
        )
        return super().form_invalid(form)
