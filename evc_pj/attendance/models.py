"""
=====================================================================
勤怠管理システム（attendance アプリ） モデル層
=====================================================================

【マルチDB構成についての前提知識】
このアプリのモデル（Attendance/DailyReport/WorkApplication/
MonthlyReport）は、ユーザーマスタ（settings.AUTH_USER_MODEL、
社員情報を管理する別アプリ・別データベース）とは異なるデータベースに
配置される想定（views.py側で `using(using_db)` を使って
明示的にDBを指定しているのはこのため）。

そのため、各モデルの `user`（および`approver`）外部キーには
`db_constraint=False` を指定し、データベースレベルの外部キー制約を
意図的に外している。これは「Userと同じDBに無いと外部キー制約を
張れない」というRDBの制約を回避するためであり、バグではない。

【この設計の影響・注意点】
- `Attendance.objects.select_related('user')` のような結合は
  別DBをまたぐため使えない（Django ORMは別DBを跨いだJOINをサポート
  しない）。一覧画面でユーザー名を表示する際は、views.py側で
  user_idのリストを集めて`User.objects.filter(user_id__in=...)`を
  個別に発行し、Python側の辞書で引く実装に統一している。
- `on_delete=models.CASCADE` を指定しているフィールドがあるが、
  Userが別DBにある以上、Django ORM経由でのUser削除時のカスケード
  削除は正常に動作しない可能性がある（詳細はAttendanceクラスの
  docstringを参照）。退職者の論理削除（delete_flgを立てる運用）が
  前提と思われ、物理削除は基本的に行わない運用を推奨する。

【テーブル間の関係】
    User（別DB） 1 --- N Attendance（1人1日1レコード）
                  1 --- N DailyReport（1人1日1レコード）
                  1 --- N WorkApplication（1人1日1申請種別1レコード）
                  1 --- N MonthlyReport（1人1ヶ月1レコード）

    Attendance 1 --- 1 DailyReport（OneToOne、null許容）
    Attendance 1 --- N WorkApplication（任意の紐付け、null許容）

【各テーブルの delete_flg / 削除方針について】
全テーブルに `delete_flg`（論理削除フラグ）が用意されており、
views.py の全クエリに `.filter(delete_flg=0)` の絞り込みが適用済み。
論理削除済みレコード（delete_flg=1）は一切の画面表示・集計・CSV出力
から除外される。新たにクエリを追加する際は必ず `delete_flg=0` を
付与すること。物理削除は行わず、delete_flg=1 への更新で運用すること。
=====================================================================
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models

# ロガーの取得（勤怠システムのモデル層専用ログ）
logger = logging.getLogger(__name__)


# =====================================================================
# 1. 打刻・勤務実績管理テーブル
# =====================================================================
class Attendance(models.Model):
    """
    🏢 日々の出退勤時間および実稼働時間を記録・集計するコアテーブル。

    【マルチDBに関する注意点】
    Userモデルが別データベース（例: mt_user）に存在するため、
    db_constraint=False を指定してデータベースレベルの外部キー制約を無効化しています。

    【⚠️ クロスDB CASCADE削除に関する注意】
    on_delete=models.CASCADE を指定していますが、Userモデルが別データベースに存在するため、
    Django ORM経由でUserレコードを削除しようとすると、異なるDBエイリアスをまたいだ
    削除コレクタの処理でエラーになる可能性があります（db_constraint=Falseのため
    DB自体には外部キー制約は無く、物理的な削除自体は失敗しませんが、
    Django側のon_delete=CASCADEのロジックが正しく動作しない可能性があります）。
    退職者の物理削除処理を実装する際は、関連レコード（Attendance/DailyReport/
    WorkApplication/MonthlyReport）の削除を明示的に行うバッチ処理を別途用意してください。
    """

    WORK_TYPE_CHOICES = [
        ('NORMAL', '出勤'),
        ('PAID_LEAVE', '有休'),
        ('AM_LEAVE', '午前半休'),
        ('PM_LEAVE', '午後半休'),
        ('COMP_LEAVE', '代休'),
    ]

    # ユーザー連携（別DBカスタムユーザー対応）
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        db_constraint=False,
        verbose_name='ユーザーID'
    )
    work_date = models.DateField(verbose_name='勤務日')

    # 勤務区分
    work_type = models.CharField(
        verbose_name='勤務区分',
        max_length=20,
        choices=WORK_TYPE_CHOICES,
        default='NORMAL'
    )

    # 実際の打刻データ（時分秒まで記録するため DateTimeField を使用）
    clock_in = models.DateTimeField(verbose_name='出勤日時', null=True, blank=True)
    clock_out = models.DateTimeField(verbose_name='退勤日時', null=True, blank=True)
    break_start = models.DateTimeField(verbose_name='休憩開始日時', null=True, blank=True)
    break_end = models.DateTimeField(verbose_name='休憩終了日時', null=True, blank=True)

    # 集計用データ（DurationField により時間幅として保存。timedelta として操作可能）
    actual_work_hours = models.DurationField(verbose_name='実労働時間', null=True, blank=True)
    overtime_hours = models.DurationField(verbose_name='残業時間', null=True, blank=True)
    break_hours = models.DurationField(verbose_name='休憩時間', null=True, blank=True)

    # システム共通管理カラム
    delete_flg = models.IntegerField(verbose_name='削除フラグ', default=0)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', auto_now_add=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    class Meta:
        db_table = 'tr_attendance'
        unique_together = ('user', 'work_date')  # 1人1日1レコードを絶対保証
        verbose_name = '勤務実績'
        verbose_name_plural = '勤務実績一覧'

    # 自動再計算のトリガーとなる打刻フィールド群
    _CLOCK_FIELDS = frozenset({'clock_in', 'clock_out', 'break_start', 'break_end'})

    def save(self, *args, **kwargs):
        """
        💾 保存直前に割り込み、各種労働時間を自動で確定させるロジック。
        不整合な時間（マイナス値など）を検知した場合は安全に0クリアします。

        【自動再計算の実行条件（2段階の保護機構）】

        以下のいずれかに該当する場合、打刻データからの自動再計算をスキップし、
        モデルインスタンスに設定済みの値（または QuerySet.update() で確定した値）を保護します。

        保護条件1 — update_fields に打刻フィールドが含まれない場合:
            save(update_fields=['work_type', 'update_user']) のように、
            clock_in / clock_out / break_start / break_end を含まない
            update_fields が指定された場合は再計算をスキップします。
            打刻データを変更しない保存（勤務区分のみ変更など）で
            実労働時間が誤って再計算・クリアされるのを防ぎます。

        保護条件2 — skip_recalculate=True を明示した場合:
            attendance.save(skip_recalculate=True, using=db) のように
            明示的にフラグを立てると、無条件で再計算をスキップします。
            通常の打刻・日報フローでは使いません。承認フローなど、
            手動確定値を保護しつつ save() 経由で他フィールドも更新したい
            特殊なケースで使用してください。

        【推奨: 承認フローでの QuerySet.update() 利用について】
        「申請された残業時間で overtime_hours を確定したい」
        「有休承認で actual_work_hours を 0 に明示したい」など、
        打刻データに基づかない値を確定する場合は、
        save() ではなく QuerySet.update() を推奨します。
        QuerySet.update() は save() 自体を呼ばないため、
        このメソッドの再計算ロジックの影響を完全に受けません
        （ApplicationApprovalView の OVERTIME / PAID_LEAVE / COMP_LEAVE
        承認処理がこのパターンを採用しています）。
        """
        # --- 保護条件2: skip_recalculate フラグ（Django標準kwargではないのでpopで除去）---
        skip_recalculate = kwargs.pop('skip_recalculate', False)

        # --- 保護条件1: update_fields に打刻フィールドが含まれるかチェック ---
        update_fields = kwargs.get('update_fields')
        clock_fields_updated = (
            update_fields is None  # update_fields未指定 = フルsave → 常に再計算
            or bool(self._CLOCK_FIELDS & set(update_fields))  # 打刻フィールドあり → 再計算
        )

        should_recalculate = not skip_recalculate and clock_fields_updated

        if should_recalculate:
            try:
                # --- 1. 休憩時間の自動計算 ---
                if self.break_start and self.break_end:
                    calculated_break = self.break_end - self.break_start
                    self.break_hours = max(calculated_break, timedelta(0))  # マイナス休憩の防止
                else:
                    self.break_hours = self.break_hours or timedelta(0)

                # --- 2. 実労働時間 & 残業時間の自動計算 ---
                if self.clock_in and self.clock_out:
                    total_duration = self.clock_out - self.clock_in
                    calculated_work = total_duration - self.break_hours
                    # 実労働時間がマイナス（打刻ミス等）の場合は0に丸める
                    self.actual_work_hours = max(calculated_work, timedelta(0))

                    # --- 3. 残業時間の計算（法定労働時間：1日8時間を超過した分）---
                    eight_hours = timedelta(hours=8)
                    self.overtime_hours = (
                        self.actual_work_hours - eight_hours
                        if self.actual_work_hours > eight_hours
                        else timedelta(0)
                    )
                    # 💡 安全対策: ログ出力時はリレーションを経由せず、生値の self.user_id を使うことで、
                    # ユーザーモデルが存在しない場合の ObjectDoesNotExist による保存失敗を完全に防ぐ
                    logger.info(
                        f"【勤務時間自動集計成功】ユーザー: {self.user_id}, 日付: {self.work_date}, "
                        f"実労働: {self.actual_work_hours}, 残業: {self.overtime_hours}, 休憩: {self.break_hours}"
                    )
                else:
                    # 出退勤が揃わない場合は必ずクリア
                    self.actual_work_hours = None
                    self.overtime_hours = None

            except Exception as e:
                # 万が一の計算エラー時もシステムを停止させず、エラーログを記録して通常の保存処理へ流す
                logger.error(
                    f"【勤務時間自動集計エラー】ユーザー: {self.user_id}, 日付: {self.work_date} - 原因: {str(e)}",
                    exc_info=True
                )

        super().save(*args, **kwargs)

    def __str__(self):
        # 外部DBリレーション起因の例外対策
        try:
            return f"{self.user.user_name or self.user_id} - {self.work_date}"
        except Exception:
            return f"{self.user_id} - {self.work_date}"


# =====================================================================
# 2. 日報管理テーブル
# =====================================================================
class DailyReport(models.Model):
    """
    📝 日々の業務内容、進捗、勤務場所を記録するテーブル。
    1つの勤務実績(Attendance)に対して原則1つの日報が紐づく1対1の構造です。

    【attendanceフィールドがnull許容な理由】
    打刻システムを使わない勤務形態（直行直帰など）でも日報単体での
    提出を可能にするため、Attendanceとの紐付けは必須にしていない。
    日報一覧画面等でAttendanceの情報（出退勤時刻等）と突き合わせて
    表示したい場合は、`attendance`がNoneのケースを必ず考慮すること。
    """

    LOCATION_CHOICES = [
        ('OFFICE', '出社（オフィス）'),
        ('REMOTE', 'リモート（在宅勤務）'),
        ('OUTSIDE', '直行・直帰（客先など）'),
    ]

    # 勤務実績への1対1リンク（打刻が消えたら日報も消える連動設定）
    attendance = models.OneToOneField(
        Attendance,
        on_delete=models.CASCADE,
        related_name='daily_report',
        verbose_name='勤務実績レコード',
        null=True,
        blank=True
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        db_constraint=False,
        verbose_name='ユーザーID'
    )
    report_date = models.DateField(verbose_name='日報対象日')

    # 勤務場所（初期値: 出社）
    work_location = models.CharField(
        verbose_name='勤務場所',
        max_length=20,
        choices=LOCATION_CHOICES,
        default='OFFICE'
    )

    # 業務内容・テキストエントリ
    task_summary = models.TextField(verbose_name='業務内容・進捗')
    comment = models.TextField(verbose_name='所感・連絡事項', null=True, blank=True)

    # システム共通管理カラム
    delete_flg = models.IntegerField(verbose_name='削除フラグ', default=0)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', auto_now_add=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    class Meta:
        db_table = 'tr_daily_report'
        unique_together = ('user', 'report_date')  # 1人1日1日報を絶対保証
        verbose_name = '日報'
        verbose_name_plural = '日報一覧'

    def __str__(self):
        return f"{self.report_date} 日報 ({self.user_id})"


# =====================================================================
# 3. 申請・承認管理テーブル
# =====================================================================
class WorkApplication(models.Model):
    """
    📨 各種就業申請（残業、有給、打刻修正など）と、上長による承認フローを管理するテーブル。

    【APPLY_TYPE_CHOICESごとに「どのフィールドが使われるか」の対応表】
      OVERTIME    : requested_overtime_hours が必須。承認時にこの値で
                    Attendance.overtime_hours を上書き確定する。
      CORRECTION  : corrected_clock_in / corrected_clock_out が必須、
                    corrected_break_hours は任意。承認時にこれらの値で
                    Attendanceの打刻データ自体を書き換える
                    （実労働時間・残業時間はAttendance.save()内で
                    打刻ベースに再計算される）。
      PAID_LEAVE / AM_LEAVE / PM_LEAVE / COMP_LEAVE:
                    時刻系フィールドは未使用（reasonのみ必須）。
                    承認時にAttendance.work_typeが変更される。
                    PAID_LEAVE/COMP_LEAVE（全休扱い）の場合のみ
                    出退勤・実労働/残業時間も明示的に0クリアされる。

    【承認時のAttendance更新方式に関する重要な注意】
    申請が承認(APPROVED)されたタイミングでAttendanceへ反映する処理は
    views.py の ApplicationApprovalView.post() に実装されている。
    このモデル自体にはAttendanceを自動更新するシグナルやメソッドは
    無いため、「承認したのにAttendanceが更新されない」というバグが
    疑われる場合は、まずApplicationApprovalView側の分岐漏れを疑うこと
    （実際に過去、OVERTIME種別の承認処理が分岐から漏れていたバグが
    あった）。
    """

    APPLY_TYPE_CHOICES = [
        ('OVERTIME', '残業申請'),
        ('PAID_LEAVE', '有給休暇申請（全休）'),
        ('AM_LEAVE', '午前半休申請'),
        ('PM_LEAVE', '午後半休申請'),
        ('COMP_LEAVE', '代休申請'),
        ('CORRECTION', '打刻修正申請'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '未承認（保留中）'),
        ('APPROVED', '承認済み'),
        ('REJECTED', '却下'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        db_constraint=False,
        related_name='applications',
        verbose_name='申請ユーザーID'
    )

    # 打刻修正申請の際に、対象となる実績とスムーズに連携するための非制約リレーション
    # ※ OVERTIME/CORRECTION申請の場合、views.py側で対象日の既存Attendanceがあれば自動セットされる
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.SET_NULL,
        db_constraint=False,
        null=True,
        blank=True,
        related_name='applications',
        verbose_name='対象勤務実績'
    )

    apply_type = models.CharField(verbose_name='申請種別', max_length=20, choices=APPLY_TYPE_CHOICES)
    target_date = models.DateField(verbose_name='対象日')

    # 打刻修正申請用の専用フィールド（TimeField で時刻のみ管理、休憩は時間幅）
    corrected_clock_in = models.TimeField(verbose_name='修正後出勤時刻', null=True, blank=True)
    corrected_clock_out = models.TimeField(verbose_name='修正後退勤時刻', null=True, blank=True)
    corrected_break_hours = models.DurationField(verbose_name='修正後休憩時間', null=True, blank=True)

    # ➕ 追加: 残業申請(OVERTIME)用の申請残業時間。
    # 承認時にこの値でAttendance.overtime_hoursを上書きする（打刻からの自動計算値は使わない）。
    requested_overtime_hours = models.DurationField(verbose_name='申請残業時間', null=True, blank=True)

    reason = models.TextField(verbose_name='申請理由')

    # ワークフローステータス
    status = models.CharField(verbose_name='承認ステータス', max_length=15, choices=STATUS_CHOICES, default='PENDING')
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column='approver_id',
        db_constraint=False,
        related_name='approved_applications',
        null=True,
        blank=True,
        verbose_name='承認者ユーザーID'
    )
    approval_comment = models.CharField(verbose_name='承認・却下理由/コメント', max_length=100, null=True, blank=True)
    approval_date = models.DateTimeField(verbose_name='承認・却下日時', null=True, blank=True)

    # システム共通管理カラム
    delete_flg = models.IntegerField(verbose_name='削除フラグ', default=0)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', auto_now_add=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    class Meta:
        db_table = 'tr_application'
        # 同一日・同一申請種別の重複申請スパムをデータベースレベルで防止
        unique_together = ('user', 'target_date', 'apply_type')
        verbose_name = '各種申請'
        verbose_name_plural = '各種申請一覧'

    def __str__(self):
        return f"[{self.get_apply_type_display()}] {self.user_id} - {self.target_date} ({self.get_status_display()})"


# =====================================================================
# 4. 月報（月次締め）管理テーブル
# =====================================================================
class MonthlyReport(models.Model):
    """
    📊 月ごとの勤務実績データを集計し、給与計算等のために月次データを固定・ロックするテーブル。

    【ステータス遷移】
    UNSUBMITTED（未提出）
        → SUBMITTED（社員が月報提出。views.py MonthlyReportView.post()）
        → APPROVED（上長が確定承認。views.py ApplicationApprovalView.post()、
                     action_type='approve_month'）
        → REJECTED（上長が差し戻し。同上、action_type='reject_month'）
          → 差し戻し後、社員が再度月報提出するとSUBMITTEDに戻る
            （MonthlyReportView.post()は既存レコードがあればget_or_create
            の `created=False` 分岐で再度SUBMITTEDに更新する実装のため、
            REJECTED → SUBMITTED の遷移に専用の特別処理は無い）

    【他テーブルへのロック作用】
    status が SUBMITTED または APPROVED の間、対象月の
    Attendance（打刻）/ DailyReport（日報）/ WorkApplication（新規申請）
    への操作がviews.py側の各ビューで一律ブロックされる
    （本モデル自体にはロックを強制する仕組みは無く、views.py側の
    各ビューが個別に `MonthlyReport...exists()` をチェックする実装に
    なっている点に注意。ロック条件を変える場合は影響範囲が広い）。

    【is_closed / closed_date フィールドについて】
    確定承認（approve_month）時に is_closed=1 / closed_date=現在日時が
    セットされ、差し戻し（reject_month）時に is_closed=0 に戻る。

    ただし、打刻・日報・申請のロック判定はすべて `status` フィールドで
    行っており（status__in=['SUBMITTED', 'APPROVED']）、is_closed を
    参照している箇所は現状ない。

    is_closed は「APPROVED 確定後はたとえ管理者でも差し戻しできない」
    といった、status だけでは表現しにくい厳格な締め処理が必要になった
    場合の拡張ポイントとして意図的に残しているフィールドである。
    現時点では参照ロジックを持たないため、追加する場合は
    ApplicationApprovalView の reject_month 分岐に
    `if report.is_closed: return error` のガードを実装すること。
    """

    STATUS_CHOICES = [
        ('UNSUBMITTED', '未提出'),
        ('SUBMITTED', '提出済（承認待ち）'),
        ('APPROVED', '確定（承認済み）'),
        ('REJECTED', '差し戻し'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        db_constraint=False,
        verbose_name='ユーザーID'
    )
    target_month = models.CharField(verbose_name='対象年月', max_length=7) # フォーマット例: '2026-06'

    # 月間累計サマリーデータ
    total_work_days = models.IntegerField(verbose_name='総出勤日数', default=0)
    total_work_hours = models.DurationField(verbose_name='総実労働時間', null=True, blank=True)
    total_overtime_hours = models.DurationField(verbose_name='総残業時間', null=True, blank=True)

    # 締め状態管理（is_closed=1 の場合、対象月の打刻・日報への新規登録・変更をビューでロックします）
    is_closed = models.IntegerField(verbose_name='月次締めフラグ', default=0)
    closed_date = models.DateTimeField(verbose_name='締め処理日時', null=True, blank=True)

    # ワークフロー状態
    status = models.CharField(verbose_name='確定ステータス', max_length=20, choices=STATUS_CHOICES, default='UNSUBMITTED')
    approval_comment = models.CharField(verbose_name='上長コメント/差し戻し理由', max_length=100, null=True, blank=True)

    # システム共通管理カラム
    delete_flg = models.IntegerField(verbose_name='削除フラグ', default=0)
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', auto_now_add=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    class Meta:
        db_table = 'tr_monthly_report'
        unique_together = ('user', 'target_month') # 1人1ヶ月1レコード
        verbose_name = '月報'
        verbose_name_plural = '月報一覧'

    def __str__(self):
        try:
            return f"{self.user.user_name or self.user_id} - {self.target_month} ({self.get_status_display()})"
        except Exception:
            return f"{self.user_id} - {self.target_month} ({self.get_status_display()})"


# =====================================================================
# 5. 有給残日数管理テーブル
# =====================================================================
class LeaveBalance(models.Model):
    """
    有給残日数を年度単位で管理するマスタ。
    1人1年度1レコード。管理者が付与日数を設定し、申請承認時に取得日数が自動加算される。

    【日数の単位】
    全休（PAID_LEAVE）= 1.0 日、午前/午後半休（AM_LEAVE/PM_LEAVE）= 0.5 日。
    DecimalField（小数点1桁）で0.5刻みの管理に対応。

    【年度の定義】
    日本の会計年度（4月始まり）。4月〜翌3月が同一 fiscal_year。
    例: 2026年4月〜2027年3月 → fiscal_year=2026
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        db_constraint=False,
        verbose_name='ユーザーID'
    )
    fiscal_year = models.IntegerField(verbose_name='年度')

    granted_days = models.DecimalField(
        verbose_name='付与日数', max_digits=5, decimal_places=1, default=Decimal('0')
    )
    used_days = models.DecimalField(
        verbose_name='取得済み日数', max_digits=5, decimal_places=1, default=Decimal('0')
    )

    # システム共通管理カラム
    create_user = models.CharField(verbose_name='作成者', max_length=30, null=True, blank=True)
    create_date = models.DateTimeField(verbose_name='作成日時', auto_now_add=True)
    update_user = models.CharField(verbose_name='更新者', max_length=30, null=True, blank=True)
    update_date = models.DateTimeField(verbose_name='更新日時', auto_now=True)

    class Meta:
        db_table = 'mt_leave_balance'
        unique_together = ('user', 'fiscal_year')
        verbose_name = '有給残日数'
        verbose_name_plural = '有給残日数一覧'

    @property
    def remaining_days(self):
        return self.granted_days - self.used_days

    def __str__(self):
        return f"{self.user_id} - {self.fiscal_year}年度 (残: {self.remaining_days}日)"