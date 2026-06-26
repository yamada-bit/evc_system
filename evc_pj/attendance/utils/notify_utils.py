"""
勤怠システム メール通知ユーティリティ。

申請承認/却下・月報確定/差し戻し時に申請者へメールを送信する。
EvcUser.user_id はメールアドレスのため、そのまま宛先として使用する。

メール設定が未構成の場合は SMTPConnectionError 等が発生するが、
呼び出し元ですべて except して警告ログに留め、業務処理は継続させること。
"""
import logging

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

# メール通知の一時停止フラグ。True に戻すと送信が再開される。
NOTIFY_ENABLED = False

_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')


def _send(to: str, subject: str, body: str) -> None:
    if not NOTIFY_ENABLED:
        logger.info(f"【通知スキップ】NOTIFY_ENABLED=False のため送信しません。宛先: {to}, 件名: {subject}")
        return
    send_mail(subject, body, _FROM, [to], fail_silently=False)


def notify_application_result(
    applicant_id: str,
    apply_type_display: str,
    target_date,
    status: str,
    comment: str,
) -> None:
    """
    申請承認/却下時に申請者へ通知メールを送る。

    applicant_id: 申請者の user_id（= メールアドレス）
    apply_type_display: 申請種別の表示名（例: '残業申請'）
    target_date: 対象日（date オブジェクト）
    status: 'APPROVED' or 'REJECTED'
    comment: 承認者コメント
    """
    if status == 'APPROVED':
        subject = f"【承認】{apply_type_display}（{target_date}）"
        result_label = "承認されました"
    else:
        subject = f"【却下】{apply_type_display}（{target_date}）"
        result_label = "却下されました"

    comment_line = f"\nコメント: {comment}" if comment else ""
    body = (
        f"{apply_type_display}（対象日: {target_date}）が{result_label}。{comment_line}\n\n"
        "勤怠システムにログインして詳細をご確認ください。"
    )
    try:
        _send(applicant_id, subject, body)
        logger.info(f"【通知送信成功】宛先: {applicant_id}, 件名: {subject}")
    except Exception as e:
        logger.warning(f"【通知送信失敗】宛先: {applicant_id} - {e}")


def notify_monthly_report_result(
    applicant_id: str,
    target_month: str,
    status: str,
    comment: str,
) -> None:
    """
    月報確定/差し戻し時に提出者へ通知メールを送る。

    applicant_id: 提出者の user_id（= メールアドレス）
    target_month: 対象年月（例: '2026-06'）
    status: 'APPROVED' or 'REJECTED'
    comment: 上長コメント
    """
    if status == 'APPROVED':
        subject = f"【確定】{target_month}分 月報"
        result_label = "確定承認されました"
    else:
        subject = f"【差し戻し】{target_month}分 月報"
        result_label = "差し戻されました"

    comment_line = f"\nコメント: {comment}" if comment else ""
    body = (
        f"{target_month}分の月報が{result_label}。{comment_line}\n\n"
        "勤怠システムにログインして詳細をご確認ください。"
    )
    try:
        _send(applicant_id, subject, body)
        logger.info(f"【通知送信成功】宛先: {applicant_id}, 件名: {subject}")
    except Exception as e:
        logger.warning(f"【通知送信失敗】宛先: {applicant_id} - {e}")
