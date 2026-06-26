"""
=====================================================================
勤怠管理システム（attendance アプリ） ビュー層
=====================================================================

【このパッケージの構成】
このパッケージは元々 1 ファイル（views.py）だったものを機能ごとに分割したもの。
urls.py は `from .views import XxxView` の形式をそのまま使えるよう、
このファイル（__init__.py）で全ビュークラスを re-export している。

  _base.py        共通ミックスイン・定数・ユーティリティ関数
  auth.py         AttendanceLoginView（ログイン画面）
  dashboard.py    DashboardView（ダッシュボード）
  punch.py        AttendancePunchView（打刻）
  report.py       DailyReportSubmitView / DailyReportDeleteView / MonthlyReportView（日報・月報）
  application.py  WorkApplicationView（各種就業申請）
  approval.py     ApplicationApprovalView / ExportAttendanceCSVView（承認・勤怠CSV出力）
  admin.py        AdminReportListView / AdminReportCsvDownloadView / LeaveBalanceManageView（管理者機能）

【関連テーブルとその役割（models.py 参照）】
- Attendance（tr_attendance）
    1人1日1レコード。出退勤・休憩の打刻実績と、そこから自動計算される
    実労働時間 / 残業時間 / 休憩時間を保持する「実績の正」のテーブル。
    保存時（save()）に打刻データから各種時間を自動計算するロジックが
    組み込まれている点に注意（詳細は models.py 側の docstring を参照）。

- DailyReport（tr_daily_report）
    1人1日1レコード。その日の業務内容・勤務場所・所感を記録する日報。
    Attendance とは1対1（OneToOne）で緩く紐づくが、Attendance が
    なくても日報単体での登録が可能（attendance=Null を許容）。

- WorkApplication（tr_application）
    残業・有休（全休 / 午前半休 / 午後半休）・代休・打刻修正の5種類の
    申請を扱う。1人・1日・1申請種別につき1レコードまで（DB 制約あり）。
    承認されると Attendance の該当レコードが更新される「申請→反映」の
    ワークフローを構成する。

- MonthlyReport（tr_monthly_report）
    1人1ヶ月1レコード。月報提出（status='SUBMITTED'）すると、
    対象月の Attendance / DailyReport / WorkApplication への新規登録・編集・
    削除がビュー側で一律ロックされる「月次締め」を担う。
    上長が承認（status='APPROVED'）すると確定。差し戻し時は
    'REJECTED' に戻り、再度ロック解除される。

【全体のデータフロー（社員側）】
    1. AttendancePunchView で日々打刻（出勤 / 退勤 / 休憩開始 / 休憩終了）
       → Attendance.save() が実労働時間・残業時間を自動計算
    2. DailyReportSubmitView で日報を都度登録・編集
    3. 打刻ミスや有休取得の必要があれば WorkApplicationView から申請
       → 申請時点では Attendance は更新されず、ステータス PENDING のまま
    4. 月末、MonthlyReportView から月報を提出（status='SUBMITTED'）
       → 以降、対象月の打刻・日報・新規申請は一切ブロックされる

【全体のデータフロー（管理者 / 承認者側）】
    1. ApplicationApprovalView で申請一覧・月報提出一覧を確認
    2. 申請を承認 / 却下 → 承認時に Attendance へ自動反映
    3. 月報を確定（承認）/ 差し戻し
    4. AdminReportListView / AdminReportCsvDownloadView /
       ExportAttendanceCSVView で日報・勤怠データを閲覧 / CSV 出力

【⚠️ 引き継ぎ時に特に注意すべきポイント】

1. ロックの仕組み（月報提出済みなら操作不可）は _base.py に集約されている。
     - ロック対象ステータス: LOCKED_STATUSES（frozenset）
     - ロック判定関数:       is_month_locked(user_id, target_month_str)
     - ロック強制 Mixin:     MonthLockMixin.month_lock_response(request, month_str)
   ロック判定ロジックを変更する場合は _base.py のみ修正すればよい。
   ただし MonthLockMixin を使っているビュー（4箇所）は 🔒【月次ロック N/4】の
   コメントで明示しているため、Mixin の使い方を変える際は4箇所を確認すること。
     - punch.py       → AttendancePunchView.post()
     - report.py      → DailyReportSubmitView.post()
     - report.py      → DailyReportDeleteView.post()
     - application.py → WorkApplicationView.post()

2. 申請承認時の Attendance 更新は、申請種別によって「通常の save() 経由」と
   「QuerySet.update() 経由（save() をバイパス）」を使い分けている。
   詳細は approval.py のモジュール docstring を参照すること。

3. DB は複数 DB 構成（マルチ DB）。`using_db` 変数（_base.py で定義）を、
   ORM クエリには必ず `.objects.using(using_db)` の形で明示的に付与する必要がある。
   付け忘れると default DB に対してクエリが飛び、データが見つからない
   / 書き込まれないという気づきにくいバグになるため要注意。

4. ユーザーモデル（User）は Attendance 等とは別 DB にあり、
   外部キーは `db_constraint=False` で DB レベルの制約を外している。
   `att.user.user_name` のようにリレーション経由でアクセスすると
   別 DB への追加クエリが都度発生する（N+1 問題）。
   一覧画面では原則、user_id のリストを集めて
   `User.objects.filter(user_id__in=...)` で一括取得し、
   Python 側の辞書（user_map）で引く方式に統一している。

5. 「未知の action_type / punch_type / apply_type を必ずハンドリングして
   redirect を返す」設計を徹底している。Django のビューはレスポンスを
   返さない分岐があると 500 エラーになるため、新しい申請種別や打刻種別を
   追加する際は、対応するハンドリング漏れがないか必ず確認すること。
=====================================================================
"""
from .management import AdminReportCsvDownloadView, AdminReportListView, ExportAttendanceExcelView, LeaveBalanceManageView, SchedulePreviewView
from .application import WorkApplicationView
from .approval import ApplicationApprovalView, ExportAttendanceCSVView
from .auth import AttendanceLoginView
from ._base import csv_safe, format_duration, format_td_for_csv, get_fiscal_year
from .dashboard import DashboardView
from .punch import AttendancePunchView
from .report import DailyReportDeleteView, DailyReportSubmitView, MonthlyReportView

__all__ = [
    'AttendanceLoginView',
    'DashboardView',
    'AttendancePunchView',
    'DailyReportSubmitView',
    'DailyReportDeleteView',
    'MonthlyReportView',
    'WorkApplicationView',
    'ApplicationApprovalView',
    'ExportAttendanceCSVView',
    'ExportAttendanceExcelView',
    'AdminReportListView',
    'AdminReportCsvDownloadView',
    'LeaveBalanceManageView',
    'SchedulePreviewView',
    'csv_safe',
    'format_duration',
    'format_td_for_csv',
    'get_fiscal_year',
]
