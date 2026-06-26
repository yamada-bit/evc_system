"""
attendance アプリのテストスイート

【マルチDB構成について】
- ユーザーモデル（EvcUser）は `default` DB
- Attendance/DailyReport/WorkApplication/MonthlyReport/LeaveBalance は `kmsdatabase`
- `databases = ['default', 'kmsdatabase']` を指定し、両DBへのアクセスを許可している
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .models import Attendance, DailyReport, LeaveBalance, MonthlyReport, WorkApplication
from .views import format_duration, format_td_for_csv, get_fiscal_year

User = get_user_model()
DB = 'kmsdatabase'


# =============================================================================
# テスト共通ヘルパー
# =============================================================================
def create_user(email='user@example.com', name='テストユーザ', is_staff=False, password='pass1234'):
    return User.objects.create_user(user_id=email, user_name=name, password=password, is_staff=is_staff)


def create_attendance(user, work_date=None, **kwargs):
    if work_date is None:
        work_date = date.today()
    att = Attendance(user_id=user.user_id, work_date=work_date, **kwargs)
    att.save(using=DB)
    return att


def create_monthly_report(user, target_month, status='UNSUBMITTED', **kwargs):
    report = MonthlyReport(
        user_id=user.user_id,
        target_month=target_month,
        status=status,
        **kwargs,
    )
    report.save(using=DB)
    return report


# =============================================================================
# 1. ヘルパー関数テスト
# =============================================================================
class FormatDurationTest(TestCase):
    """format_duration のユニットテスト"""

    def test_normal_duration(self):
        self.assertEqual(format_duration(timedelta(hours=8, minutes=30)), '8:30')

    def test_zero_duration_returns_zero(self):
        # timedelta(0) は None ではないため '0:00' を返す
        self.assertEqual(format_duration(timedelta(0)), '0:00')

    def test_over_24_hours(self):
        self.assertEqual(format_duration(timedelta(hours=25, minutes=5)), '25:05')

    def test_none_returns_dash(self):
        self.assertEqual(format_duration(None), '-')

    def test_non_timedelta_returns_dash(self):
        self.assertEqual(format_duration('not a timedelta'), '-')


class FormatTdForCsvTest(TestCase):
    """format_td_for_csv のユニットテスト"""

    def test_normal_duration(self):
        self.assertEqual(format_td_for_csv(timedelta(hours=2, minutes=0)), '2:00')

    def test_none_returns_zero(self):
        self.assertEqual(format_td_for_csv(None), '0:00')


class GetFiscalYearTest(TestCase):
    """get_fiscal_year のユニットテスト（日本の年度: 4月始まり）"""

    def test_april_is_new_year(self):
        self.assertEqual(get_fiscal_year(date(2026, 4, 1)), 2026)

    def test_march_is_previous_year(self):
        self.assertEqual(get_fiscal_year(date(2026, 3, 31)), 2025)

    def test_january(self):
        self.assertEqual(get_fiscal_year(date(2026, 1, 1)), 2025)

    def test_december(self):
        self.assertEqual(get_fiscal_year(date(2025, 12, 1)), 2025)


# =============================================================================
# 2. Attendance モデルテスト
# =============================================================================
class AttendanceSaveTest(TestCase):
    """Attendance.save() の自動計算ロジックテスト"""

    databases = ['default', DB]

    def setUp(self):
        self.user = create_user()

    def _make(self, **kwargs):
        att = Attendance(user_id=self.user.user_id, work_date=date(2026, 6, 1), **kwargs)
        att.save(using=DB)
        return att

    def test_actual_work_hours_calculated(self):
        now = timezone.now()
        att = self._make(
            clock_in=now.replace(hour=9, minute=0, second=0, microsecond=0),
            clock_out=now.replace(hour=18, minute=0, second=0, microsecond=0),
        )
        self.assertEqual(att.actual_work_hours, timedelta(hours=9))

    def test_break_hours_deducted(self):
        base = timezone.now().replace(second=0, microsecond=0)
        att = self._make(
            clock_in=base.replace(hour=9, minute=0),
            clock_out=base.replace(hour=18, minute=0),
            break_start=base.replace(hour=12, minute=0),
            break_end=base.replace(hour=13, minute=0),
        )
        self.assertEqual(att.break_hours, timedelta(hours=1))
        self.assertEqual(att.actual_work_hours, timedelta(hours=8))

    def test_overtime_hours_over_8h(self):
        base = timezone.now().replace(second=0, microsecond=0)
        att = self._make(
            clock_in=base.replace(hour=9, minute=0),
            clock_out=base.replace(hour=19, minute=0),
        )
        self.assertEqual(att.overtime_hours, timedelta(hours=2))

    def test_no_overtime_exact_8h(self):
        base = timezone.now().replace(second=0, microsecond=0)
        att = self._make(
            clock_in=base.replace(hour=9, minute=0),
            clock_out=base.replace(hour=17, minute=0),
        )
        self.assertEqual(att.overtime_hours, timedelta(0))

    def test_no_clock_out_clears_work_hours(self):
        att = self._make(clock_in=timezone.now())
        self.assertIsNone(att.actual_work_hours)
        self.assertIsNone(att.overtime_hours)

    def test_skip_recalculate_flag_preserves_values(self):
        """skip_recalculate=True のとき既存の値が保護される"""
        base = timezone.now().replace(second=0, microsecond=0)
        att = self._make(
            clock_in=base.replace(hour=9, minute=0),
            clock_out=base.replace(hour=18, minute=0),
        )
        att.actual_work_hours = timedelta(hours=99)
        att.save(using=DB, skip_recalculate=True)
        att.refresh_from_db(using=DB)
        self.assertEqual(att.actual_work_hours, timedelta(hours=99))

    def test_update_fields_without_clock_skips_recalculate(self):
        """update_fields に打刻フィールドが含まれない場合、再計算はスキップされる"""
        base = timezone.now().replace(second=0, microsecond=0)
        att = self._make(
            clock_in=base.replace(hour=9, minute=0),
            clock_out=base.replace(hour=18, minute=0),
        )
        original_hours = att.actual_work_hours
        att.work_type = 'PAID_LEAVE'
        att.actual_work_hours = timedelta(hours=0)  # 手動で書き換え
        att.save(using=DB, update_fields=['work_type', 'update_date'])
        att.refresh_from_db(using=DB)
        # update_fields に clock フィールドが無いため再計算されず、元の値が保持される
        self.assertEqual(att.actual_work_hours, original_hours)


# =============================================================================
# 3. LeaveBalance モデルテスト
# =============================================================================
class LeaveBalanceTest(TestCase):
    databases = ['default', DB]

    def setUp(self):
        self.user = create_user()

    def test_remaining_days(self):
        lb = LeaveBalance(
            user_id=self.user.user_id,
            fiscal_year=2026,
            granted_days=Decimal('10.0'),
            used_days=Decimal('3.5'),
        )
        lb.save(using=DB)
        self.assertEqual(lb.remaining_days, Decimal('6.5'))


# =============================================================================
# 4. ビューテスト基底クラス
# =============================================================================
class AttendanceViewTestBase(TestCase):
    databases = ['default', DB]

    def setUp(self):
        self.user = create_user(email='employee@example.com', name='一般社員')
        self.staff = create_user(email='admin@example.com', name='管理者', is_staff=True)
        self.client = Client()

    def login(self, user=None):
        if user is None:
            user = self.user
        self.client.force_login(user)


# =============================================================================
# 5. AttendancePunchView テスト
# =============================================================================
class AttendancePunchViewTest(AttendanceViewTestBase):
    """打刻画面のテスト"""

    def setUp(self):
        super().setUp()
        self.url = reverse('attendance:attendance_punch')

    def test_get_requires_login(self):
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)

    def test_get_authenticated(self):
        self.login()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_clock_in(self):
        self.login()
        resp = self.client.post(self.url, {'punch_type': 'clock_in'})
        self.assertRedirects(resp, self.url)
        att = Attendance.objects.using(DB).get(user_id=self.user.user_id)
        self.assertIsNotNone(att.clock_in)

    def test_clock_in_twice_shows_warning(self):
        self.login()
        self.client.post(self.url, {'punch_type': 'clock_in'})
        self.client.post(self.url, {'punch_type': 'clock_in'})
        # 2回目の出勤打刻はレコードが1件のまま（重複登録されない）
        count = Attendance.objects.using(DB).filter(user_id=self.user.user_id).count()
        self.assertEqual(count, 1)

    def test_clock_out_without_clock_in_shows_warning(self):
        self.login()
        resp = self.client.post(self.url, {'punch_type': 'clock_out'})
        self.assertRedirects(resp, self.url)
        # clock_in なしでは Attendance レコード自体が存在しない
        self.assertFalse(Attendance.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_clock_out_after_clock_in(self):
        self.login()
        self.client.post(self.url, {'punch_type': 'clock_in'})
        resp = self.client.post(self.url, {'punch_type': 'clock_out'})
        self.assertRedirects(resp, self.url)
        att = Attendance.objects.using(DB).get(user_id=self.user.user_id)
        self.assertIsNotNone(att.clock_out)

    def test_invalid_punch_type_rejected(self):
        self.login()
        resp = self.client.post(self.url, {'punch_type': 'invalid_type'})
        self.assertRedirects(resp, self.url)
        self.assertFalse(Attendance.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_punch_blocked_when_monthly_report_submitted(self):
        """月報が提出済みの場合は打刻できない"""
        self.login()
        today = date.today()
        target_month = today.strftime('%Y-%m')
        create_monthly_report(self.user, target_month, status='SUBMITTED')
        resp = self.client.post(self.url, {'punch_type': 'clock_in'})
        self.assertRedirects(resp, self.url)
        self.assertFalse(Attendance.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_punch_not_blocked_by_deleted_monthly_report(self):
        """論理削除済みの月報がある場合は打刻をブロックしない（is_month_locked が delete_flg=0 のみ対象）"""
        self.login()
        today = date.today()
        target_month = today.strftime('%Y-%m')
        create_monthly_report(self.user, target_month, status='SUBMITTED', delete_flg=1)
        resp = self.client.post(self.url, {'punch_type': 'clock_in'})
        self.assertRedirects(resp, self.url)
        self.assertTrue(Attendance.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_break_start_without_clock_in_rejected(self):
        self.login()
        resp = self.client.post(self.url, {'punch_type': 'break_start'})
        self.assertRedirects(resp, self.url)

    def test_break_flow(self):
        self.login()
        self.client.post(self.url, {'punch_type': 'clock_in'})
        self.client.post(self.url, {'punch_type': 'break_start'})
        self.client.post(self.url, {'punch_type': 'break_end'})
        att = Attendance.objects.using(DB).get(user_id=self.user.user_id)
        self.assertIsNotNone(att.break_start)
        self.assertIsNotNone(att.break_end)


# =============================================================================
# 6. DailyReportSubmitView テスト
# =============================================================================
class DailyReportSubmitViewTest(AttendanceViewTestBase):
    url = None

    def setUp(self):
        super().setUp()
        self.url = reverse('attendance:daily_report_submit')

    def test_get_requires_login(self):
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)

    def test_get_authenticated(self):
        self.login()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_report(self):
        self.login()
        today_str = date.today().strftime('%Y-%m-%d')
        resp = self.client.post(self.url, {
            'target_date': today_str,
            'work_location': 'OFFICE',
            'task_summary': '本日の業務内容',
            'comment': '所感',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            DailyReport.objects.using(DB).filter(user_id=self.user.user_id).exists()
        )

    def test_post_updates_existing_report(self):
        self.login()
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        # 最初に作成
        self.client.post(self.url, {
            'target_date': today_str,
            'work_location': 'OFFICE',
            'task_summary': '初回内容',
            'comment': '',
        })
        # 更新
        self.client.post(self.url, {
            'target_date': today_str,
            'work_location': 'REMOTE',
            'task_summary': '更新後内容',
            'comment': '',
        })
        reports = DailyReport.objects.using(DB).filter(user_id=self.user.user_id, delete_flg=0)
        self.assertEqual(reports.count(), 1)
        self.assertEqual(reports.first().task_summary, '更新後内容')

    def test_post_blocked_by_monthly_report_submitted(self):
        self.login()
        today = date.today()
        target_month = today.strftime('%Y-%m')
        create_monthly_report(self.user, target_month, status='SUBMITTED')
        resp = self.client.post(self.url, {
            'target_date': today.strftime('%Y-%m-%d'),
            'work_location': 'OFFICE',
            'task_summary': 'テスト',
            'comment': '',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(DailyReport.objects.using(DB).filter(user_id=self.user.user_id).exists())


# =============================================================================
# 7. DailyReportDeleteView テスト
# =============================================================================
class DailyReportDeleteViewTest(AttendanceViewTestBase):

    def setUp(self):
        super().setUp()
        self.delete_url = reverse('attendance:daily_report_delete')

    def _create_report(self, user, report_date=None):
        if report_date is None:
            report_date = date.today()
        r = DailyReport(
            user_id=user.user_id,
            report_date=report_date,
            work_location='OFFICE',
            task_summary='テスト日報',
        )
        r.save(using=DB)
        return r

    def test_delete_own_report(self):
        self.login()
        report = self._create_report(self.user)
        resp = self.client.post(self.delete_url, {'report_id': report.id})
        self.assertEqual(resp.status_code, 302)
        report.refresh_from_db(using=DB)
        self.assertEqual(report.delete_flg, 1)

    def test_cannot_delete_other_users_report(self):
        other = create_user(email='other@example.com', name='他社員')
        report = self._create_report(other)
        self.login()
        self.client.post(self.delete_url, {'report_id': report.id})
        report.refresh_from_db(using=DB)
        self.assertEqual(report.delete_flg, 0)

    def test_delete_blocked_when_monthly_submitted(self):
        self.login()
        today = date.today()
        report = self._create_report(self.user, report_date=today)
        create_monthly_report(self.user, today.strftime('%Y-%m'), status='SUBMITTED')
        self.client.post(self.delete_url, {'report_id': report.id})
        report.refresh_from_db(using=DB)
        self.assertEqual(report.delete_flg, 0)

    def test_missing_report_id_redirects(self):
        self.login()
        resp = self.client.post(self.delete_url, {})
        self.assertEqual(resp.status_code, 302)


# =============================================================================
# 8. MonthlyReportView テスト
# =============================================================================
class MonthlyReportViewTest(AttendanceViewTestBase):

    def setUp(self):
        super().setUp()
        self.url = reverse('attendance:monthly_report')

    def test_get_requires_login(self):
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)

    def test_get_renders(self):
        self.login()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_submit_creates_monthly_report(self):
        self.login()
        today = date.today()
        month_str = today.strftime('%Y-%m')
        resp = self.client.post(
            f"{self.url}?month={month_str}",
            {'action_type': 'submit_monthly_report'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            MonthlyReport.objects.using(DB).filter(
                user_id=self.user.user_id, target_month=month_str, status='SUBMITTED'
            ).exists()
        )

    def test_submit_blocked_if_already_approved(self):
        self.login()
        today = date.today()
        month_str = today.strftime('%Y-%m')
        create_monthly_report(self.user, month_str, status='APPROVED')
        resp = self.client.post(
            f"{self.url}?month={month_str}",
            {'action_type': 'submit_monthly_report'},
        )
        self.assertEqual(resp.status_code, 302)
        # APPROVED のままで SUBMITTED に戻っていない
        report = MonthlyReport.objects.using(DB).get(user_id=self.user.user_id, target_month=month_str)
        self.assertEqual(report.status, 'APPROVED')

    def test_submit_creates_new_report_ignoring_deleted_record(self):
        """論理削除済みの月報がある場合、get_or_create が削除済みレコードを取得せず新規作成する"""
        self.login()
        today = date.today()
        month_str = today.strftime('%Y-%m')
        # 論理削除済みの REJECTED 月報を作成
        create_monthly_report(self.user, month_str, status='REJECTED', delete_flg=1)
        self.client.post(
            f"{self.url}?month={month_str}",
            {'action_type': 'submit_monthly_report'},
        )
        # delete_flg=0 の SUBMITTED レコードが新規に作成されること
        self.assertTrue(
            MonthlyReport.objects.using(DB).filter(
                user_id=self.user.user_id, target_month=month_str, status='SUBMITTED'
            ).exists()
        )
        # 削除済みレコードは delete_flg=1 のまま（更新されていない）
        deleted = MonthlyReport.all_objects.using(DB).get(
            user_id=self.user.user_id, target_month=month_str, delete_flg=1
        )
        self.assertEqual(deleted.status, 'REJECTED')

    def test_unknown_action_type_returns_redirect(self):
        self.login()
        today = date.today()
        month_str = today.strftime('%Y-%m')
        resp = self.client.post(
            f"{self.url}?month={month_str}",
            {'action_type': 'unknown_action'},
        )
        self.assertEqual(resp.status_code, 302)


# =============================================================================
# 9. WorkApplicationView テスト
# =============================================================================
class WorkApplicationViewTest(AttendanceViewTestBase):

    def setUp(self):
        super().setUp()
        self.url = reverse('attendance:work_application')

    def _post_application(self, apply_type, target_date=None, extra=None):
        if target_date is None:
            target_date = date.today().strftime('%Y-%m-%d')
        data = {
            'apply_type': apply_type,
            'target_date': target_date,
            'reason': 'テスト申請',
        }
        if extra:
            data.update(extra)
        return self.client.post(self.url, data)

    def test_get_requires_login(self):
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)

    def test_get_authenticated(self):
        self.login()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_overtime_application_requires_hours(self):
        self.login()
        resp = self._post_application('OVERTIME')
        self.assertRedirects(resp, self.url)
        self.assertFalse(WorkApplication.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_overtime_application_success(self):
        self.login()
        resp = self._post_application('OVERTIME', extra={'requested_overtime_hours': '02:00'})
        self.assertRedirects(resp, self.url)
        self.assertTrue(
            WorkApplication.objects.using(DB).filter(
                user_id=self.user.user_id, apply_type='OVERTIME'
            ).exists()
        )

    def test_paid_leave_requires_balance(self):
        """有給残日数が登録されていない場合は申請できない"""
        self.login()
        self._post_application('PAID_LEAVE')
        self.assertFalse(
            WorkApplication.objects.using(DB).filter(
                user_id=self.user.user_id, apply_type='PAID_LEAVE'
            ).exists()
        )

    def test_paid_leave_with_sufficient_balance(self):
        self.login()
        today = date.today()
        fy = get_fiscal_year(today)
        lb = LeaveBalance(user_id=self.user.user_id, fiscal_year=fy, granted_days=Decimal('10'))
        lb.save(using=DB)
        self._post_application('PAID_LEAVE', target_date=today.strftime('%Y-%m-%d'))
        self.assertTrue(
            WorkApplication.objects.using(DB).filter(
                user_id=self.user.user_id, apply_type='PAID_LEAVE'
            ).exists()
        )

    def test_duplicate_application_rejected(self):
        self.login()
        today = date.today()
        fy = get_fiscal_year(today)
        lb = LeaveBalance(user_id=self.user.user_id, fiscal_year=fy, granted_days=Decimal('10'))
        lb.save(using=DB)
        target = today.strftime('%Y-%m-%d')
        self._post_application('PAID_LEAVE', target_date=target)
        self._post_application('PAID_LEAVE', target_date=target)
        count = WorkApplication.objects.using(DB).filter(
            user_id=self.user.user_id, apply_type='PAID_LEAVE', target_date=today
        ).count()
        self.assertEqual(count, 1)

    def test_invalid_apply_type_rejected(self):
        self.login()
        resp = self._post_application('UNKNOWN_TYPE')
        self.assertRedirects(resp, self.url)
        self.assertFalse(WorkApplication.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_application_blocked_by_monthly_submitted(self):
        self.login()
        today = date.today()
        create_monthly_report(self.user, today.strftime('%Y-%m'), status='SUBMITTED')
        self._post_application('OVERTIME', extra={'requested_overtime_hours': '01:00'})
        self.assertFalse(WorkApplication.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_correction_invalid_time_format_rejected(self):
        self.login()
        resp = self._post_application('CORRECTION', extra={
            'corrected_clock_in': 'not_a_time',
            'corrected_clock_out': '18:00',
        })
        self.assertRedirects(resp, self.url)
        self.assertFalse(WorkApplication.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_correction_clock_in_after_out_rejected(self):
        self.login()
        resp = self._post_application('CORRECTION', extra={
            'corrected_clock_in': '18:00',
            'corrected_clock_out': '09:00',
        })
        self.assertRedirects(resp, self.url)
        self.assertFalse(WorkApplication.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_overtime_zero_hours_rejected(self):
        self.login()
        resp = self._post_application('OVERTIME', extra={'requested_overtime_hours': '00:00'})
        self.assertRedirects(resp, self.url)
        self.assertFalse(WorkApplication.objects.using(DB).filter(user_id=self.user.user_id).exists())

    def test_correction_missing_required_fields_rejected(self):
        """打刻修正申請で出退勤時刻が片方未入力の場合は申請できない"""
        self.login()
        resp = self._post_application('CORRECTION', extra={
            'corrected_clock_in': '',
            'corrected_clock_out': '18:00',
        })
        self.assertRedirects(resp, self.url)
        self.assertFalse(WorkApplication.objects.using(DB).filter(user_id=self.user.user_id).exists())


# =============================================================================
# 10. ApplicationApprovalView（管理者専用）テスト
# =============================================================================
class ApplicationApprovalViewTest(AttendanceViewTestBase):

    def setUp(self):
        super().setUp()
        self.url = reverse('attendance:application_approval')

    def test_non_staff_cannot_access(self):
        self.login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_access(self):
        self.login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def _create_application(self, apply_type='OVERTIME', status='PENDING', **kwargs):
        app = WorkApplication(
            user_id=self.user.user_id,
            apply_type=apply_type,
            target_date=date.today(),
            reason='テスト',
            status=status,
            requested_overtime_hours=timedelta(hours=2) if apply_type == 'OVERTIME' else None,
            **kwargs,
        )
        app.save(using=DB)
        return app

    def test_approve_overtime_application(self):
        self.login(self.staff)
        app = self._create_application('OVERTIME')
        # Attendance レコードが必要（承認時に overtime_hours を更新するため）
        create_attendance(self.user, work_date=app.target_date)
        self.client.post(self.url, {
            'action_type': 'approve',
            'application_id': app.id,
            'comment': '承認します',
        })
        app.refresh_from_db(using=DB)
        self.assertEqual(app.status, 'APPROVED')

    def test_reject_application(self):
        self.login(self.staff)
        app = self._create_application('OVERTIME')
        self.client.post(self.url, {
            'action_type': 'reject',
            'application_id': app.id,
            'comment': '却下します',
        })
        app.refresh_from_db(using=DB)
        self.assertEqual(app.status, 'REJECTED')

    def test_approve_overtime_creates_new_attendance_ignoring_deleted(self):
        """論理削除済みの打刻がある日付の申請を承認すると、削除済みレコードではなく新規 Attendance に反映される"""
        self.login(self.staff)
        today = date.today()
        # 論理削除済みの Attendance を作成
        deleted_att = Attendance(user_id=self.user.user_id, work_date=today, delete_flg=1)
        deleted_att.save(using=DB, skip_recalculate=True)
        # 残業申請を作成・承認
        app = self._create_application('OVERTIME')
        self.client.post(self.url, {
            'action_type': 'approve',
            'application_id': app.id,
            'comment': '承認します',
        })
        # delete_flg=0 の Attendance が作成され overtime_hours が反映されること
        active_att = Attendance.objects.using(DB).filter(
            user_id=self.user.user_id, work_date=today
        ).first()
        self.assertIsNotNone(active_att)
        self.assertEqual(active_att.overtime_hours, timedelta(hours=2))
        # 削除済みレコードは delete_flg=1 のまま（更新されていない）
        deleted_att.refresh_from_db(using=DB)
        self.assertEqual(deleted_att.delete_flg, 1)

    def test_approve_correction_application(self):
        """CORRECTION 申請を承認すると Attendance に修正打刻が反映される"""
        self.login(self.staff)
        today = date.today()
        app = self._create_application(
            'CORRECTION',
            corrected_clock_in=time(9, 0),
            corrected_clock_out=time(18, 0),
        )
        self.client.post(self.url, {
            'action_type': 'approve',
            'application_id': app.id,
            'comment': '承認します',
        })
        app.refresh_from_db(using=DB)
        self.assertEqual(app.status, 'APPROVED')
        att = Attendance.objects.using(DB).filter(
            user_id=self.user.user_id, work_date=today, delete_flg=0
        ).first()
        self.assertIsNotNone(att)
        local_in = timezone.localtime(att.clock_in)
        local_out = timezone.localtime(att.clock_out)
        self.assertEqual(local_in.hour, 9)
        self.assertEqual(local_out.hour, 18)
        self.assertEqual(att.work_type, 'NORMAL')

    def test_approve_paid_leave_application(self):
        """PAID_LEAVE 申請を承認すると Attendance が PAID_LEAVE に更新され残日数が消費される"""
        self.login(self.staff)
        today = date.today()
        fiscal_year = get_fiscal_year(today)
        lb = LeaveBalance(
            user_id=self.user.user_id,
            fiscal_year=fiscal_year,
            granted_days=Decimal('10'),
        )
        lb.save(using=DB)
        app = self._create_application('PAID_LEAVE')
        self.client.post(self.url, {
            'action_type': 'approve',
            'application_id': app.id,
            'comment': '承認します',
        })
        app.refresh_from_db(using=DB)
        self.assertEqual(app.status, 'APPROVED')
        att = Attendance.objects.using(DB).filter(
            user_id=self.user.user_id, work_date=today, delete_flg=0
        ).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.work_type, 'PAID_LEAVE')
        lb.refresh_from_db(using=DB)
        self.assertEqual(lb.used_days, Decimal('1.0'))

    def test_approve_month_sets_approved(self):
        """月報確定処理: status='APPROVED' になること"""
        self.login(self.staff)
        report = create_monthly_report(self.user, date.today().strftime('%Y-%m'), status='SUBMITTED')
        self.client.post(self.url, {
            'action_type': 'approve_month',
            'report_id': report.id,
            'comment': '確定します',
        })
        report.refresh_from_db(using=DB)
        self.assertEqual(report.status, 'APPROVED')

    def test_reject_month_sets_rejected(self):
        """月報差し戻し処理: status='REJECTED' になること"""
        self.login(self.staff)
        report = create_monthly_report(self.user, date.today().strftime('%Y-%m'), status='SUBMITTED')
        self.client.post(self.url, {
            'action_type': 'reject_month',
            'report_id': report.id,
            'comment': '差し戻します',
        })
        report.refresh_from_db(using=DB)
        self.assertEqual(report.status, 'REJECTED')


# =============================================================================
# 11. AdminReportListView（管理者専用）テスト
# =============================================================================
class AdminReportListViewTest(AttendanceViewTestBase):

    def setUp(self):
        super().setUp()
        self.url = reverse('attendance:admin_report_list')

    def test_non_staff_forbidden(self):
        self.login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_access(self):
        self.login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)


# =============================================================================
# 12. LeaveBalanceManageView（管理者専用）テスト
# =============================================================================
class LeaveBalanceManageViewTest(AttendanceViewTestBase):

    def setUp(self):
        super().setUp()
        self.url = reverse('attendance:leave_balance_manage')

    def test_non_staff_forbidden(self):
        self.login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_access(self):
        self.login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_leave_balance(self):
        """管理者が POST すると有給残日数レコードが新規作成される"""
        self.login(self.staff)
        fiscal_year = get_fiscal_year(date.today())
        self.client.post(self.url, {
            'user_id': self.user.user_id,
            'fiscal_year': str(fiscal_year),
            'granted_days': '10.0',
            'used_days': '0.0',
        })
        self.assertTrue(
            LeaveBalance.objects.using(DB).filter(
                user_id=self.user.user_id, fiscal_year=fiscal_year, delete_flg=0
            ).exists()
        )

    def test_post_updates_existing_leave_balance(self):
        """既存レコードがある場合は付与・取得済み日数が上書きされる"""
        self.login(self.staff)
        fiscal_year = get_fiscal_year(date.today())
        lb = LeaveBalance(user_id=self.user.user_id, fiscal_year=fiscal_year, granted_days=Decimal('5'))
        lb.save(using=DB)
        self.client.post(self.url, {
            'user_id': self.user.user_id,
            'fiscal_year': str(fiscal_year),
            'granted_days': '15.0',
            'used_days': '2.0',
        })
        lb.refresh_from_db(using=DB)
        self.assertEqual(lb.granted_days, Decimal('15.0'))
        self.assertEqual(lb.used_days, Decimal('2.0'))

    def test_post_ignores_deleted_record_and_creates_new(self):
        """論理削除済みの残日数レコードがある場合、削除済みレコードを更新せず新規作成する"""
        self.login(self.staff)
        fiscal_year = get_fiscal_year(date.today())
        deleted_lb = LeaveBalance(
            user_id=self.user.user_id,
            fiscal_year=fiscal_year,
            granted_days=Decimal('5'),
            delete_flg=1,
        )
        deleted_lb.save(using=DB)
        self.client.post(self.url, {
            'user_id': self.user.user_id,
            'fiscal_year': str(fiscal_year),
            'granted_days': '10.0',
            'used_days': '0.0',
        })
        # delete_flg=0 の新規レコードが作成されること
        self.assertTrue(
            LeaveBalance.objects.using(DB).filter(
                user_id=self.user.user_id, fiscal_year=fiscal_year
            ).exists()
        )
        # 削除済みレコードは変更されていないこと
        deleted_lb.refresh_from_db(using=DB)
        self.assertEqual(deleted_lb.delete_flg, 1)
        self.assertEqual(deleted_lb.granted_days, Decimal('5'))
