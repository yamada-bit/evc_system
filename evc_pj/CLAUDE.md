# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

Django 5.2 製の EV 充電スタンド管理会社（EVC）向け社内 Web アプリケーション。
充電器点検記録（`Evc_App`, `Evc_Management`, `Evc_Owner`）、OCR フォーム処理（`Fms_Ocrform`）、
ファイル共有（`Fms_fileshare`）、**従業員勤怠管理（`attendance`）** の 4 系統を含む。
PostgreSQL 2 本構成。本番は Gunicorn + リバースプロキシで稼働。

---

## コマンドリファレンス

```bash
# 開発サーバー（Claude Code のバックグラウンドループでの起動は禁止）
python manage.py runserver

# マイグレーション
python manage.py makemigrations attendance
python manage.py migrate attendance --database=kmsdatabase   # attendance のみ kmsdatabase
python manage.py migrate                                      # それ以外は default DB

# テスト（.env 不要・SQLite インメモリ・高速）
python manage.py test --settings=config.settings_test attendance
python manage.py test --settings=config.settings_test attendance.tests.SomeTestCase

# ユーティリティ
python manage.py shell
python manage.py collectstatic --noinput
pip install -r requirements.txt
```

### マイグレーション確認コマンド（変更前に必ず実行）

```bash
# マイグレーション漏れチェック（"No changes detected" が正常）
python manage.py makemigrations attendance --settings=config.settings_test --check --dry-run

# システムチェック（"no issues" が正常）
python manage.py check --settings=config.settings_test
```

---

## 環境変数（`.env` または `$ENV_FILE` 指定ファイル）

| 変数 | 用途 |
|---|---|
| `SECRET_KEY` | Django シークレットキー |
| `DEBUG` | `'True'` / `'False'` |
| `ALLOWED_HOSTS` | カンマ区切り |
| `POSTGRES_DB` / `POSTGRES_DB_KMS` | DB 名 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_PORT` | 共通接続情報 |
| `USE_GOOGLE_CALENDAR` | `'True'` で Kms_Calendar 有効化 |
| `GOOGLE_CREDENTIALS_FILE` / `GOOGLE_REDIRECT_URI` | OAuth2（上記が True の場合のみ） |
| `GOOGLE_CLOUD_VISION_KEY` / `GOOGLE_OCR` | OCR 機能 |

---

## データベースアーキテクチャ

PostgreSQL 2 本構成。ルーター: `config/db_router.py → KmsDatabaseRouter`

| DB エイリアス | 収容アプリ |
|---|---|
| `default` | users, accounts, Evc_App, Evc_Management, Evc_Owner, Fms_Ocrform, Fms_fileshare |
| `kmsdatabase` | `attendance`, `Kms_Calendar` |

### ORM クエリの必須ルール

- `attendance/views/` 内の全 ORM クエリは **`.objects.using(using_db)`** を必ず付ける。
  `using_db` は `attendance/views/_base.py` で定義（`settings.ATTENDANCE_DB = 'kmsdatabase'`）。
  省略すると default DB にサイレントにヒットするため発見が困難なバグになる。
- クロス DB 外部キー（`users.EvcUser` ↔ attendance モデル）は `db_constraint=False`。
  **リスト画面で `.user.user_name` をトラバースしない**こと。
  `user_id` を集めて `User.objects.filter(user_id__in=...)` で一括取得 → Python 側でマージする
  （`attendance/utils/db_utils.py:build_user_map()` を使う）。

### ActiveManager（論理削除の自動フィルタ）

attendance の全モデル（`Attendance`, `DailyReport`, `WorkApplication`, `MonthlyReport`,
`LeaveBalance`）の `objects` マネージャは `ActiveManager` に差し替えられており、
**`delete_flg=0`（有効レコード）を自動適用** する。論理削除済みを含む全件が必要な場合は
`Model.all_objects.using(using_db).filter(...)` を使う。
新しいクエリを書く際に `delete_flg=0` を明示的に追加する必要はない（重複になる）。

---

## attendance アプリ構成（最も活発に開発中）

```
attendance/
  models.py            — Attendance, DailyReport, WorkApplication, MonthlyReport,
                         LeaveBalance, GaikinReport
  forms.py             — AttendanceLoginForm (EmailField認証), GaikinUploadForm,
                         GaikinListForm, GaikinEditForm
  urls.py              — app_name='attendance'
  tests.py             — テストスイート（74件）
  services/
    gaikin.py          — 外勤報告書ファイル I/O（PDF/画像管理）
    excel_export.py    — 勤務表 Excel 生成（BytesIO を返す）
  utils/
    db_utils.py        — build_user_map(): クロス DB ユーザー一括取得
    log_utils.py       — get_client_ip(), log_user_id(): IPとuser_idのSHA256ハッシュ化
    notify_utils.py    — notify_application_result(), notify_monthly_report_result(): メール通知
  views/
    _base.py           — AttendanceLoginMixin, AttendanceAccessMixin, MonthLockMixin,
                         using_db, LOCKED_STATUSES, is_month_locked(), get_fiscal_year(),
                         get_pending_leave_days(), format_duration(), csv_safe(), LEAVE_COST
    auth.py            — AttendanceLoginView（勤怠専用ログイン）
    dashboard.py       — DashboardView
    punch.py           — AttendancePunchView
    report.py          — DailyReportSubmitView, DailyReportDeleteView, MonthlyReportView
    application.py     — WorkApplicationView
    approval.py        — ApplicationApprovalView, ExportAttendanceCSVView
    management.py      — AdminReportListView, AdminReportCsvDownloadView,
                         LeaveBalanceManageView, SchedulePreviewView, ExportAttendanceExcelView
    gaikin.py          — GaikinListView, GaikinUploadView, GaikinEditView
    __init__.py        — 全ビュークラスを re-export（urls.py はここから import）
```

### 認証・権限

- `EvcUser.user_id` は `EmailField`（Primary Key）。ログインフォームは email アドレス入力。
- `is_staff=True` または `is_superuser=True` のユーザーが管理者扱い（`test_func()` で判定）。
- 権限不足は `AttendanceAccessMixin.handle_no_permission()` → `attendance/403.html` を返す。
- ログアウトは **POST** のみ受け付ける（Django 5.x のセキュリティ変更）。テンプレートの
  フォームが `method="post"` になっていることを確認すること。

### 月次ロック

`MonthlyReport.status` が `SUBMITTED` または `APPROVED` の月は打刻・日報・申請の
全操作がブロックされる。ガードロジックは `_base.py` にある:

- `LOCKED_STATUSES` — ロック対象ステータスのセット
- `is_month_locked(user_id, month_str, *, request=None)` — DB チェック（request 渡しでキャッシュ）
- `MonthLockMixin.month_lock_response()` — POST 先頭で呼び出す

ロック箇所はコード内の `🔒【月次ロック` コメントで検索できる（4 箇所）。

### モデルの choice 値（ハードコードしない）

**WorkApplication.apply_type:**
`OVERTIME` / `PAID_LEAVE` / `AM_LEAVE` / `PM_LEAVE` / `COMP_LEAVE` / `CORRECTION`

**WorkApplication.status:**
`PENDING` / `APPROVED` / `REJECTED`

**MonthlyReport.status:**
`UNSUBMITTED` / `SUBMITTED` / `APPROVED` / `REJECTED`

有給消費日数マップ（`_base.py:LEAVE_COST`）と `APPLY_TYPE_CHOICES` は必ずセットで更新すること。

### 承認時の Attendance 更新パターン（重要）

- `CORRECTION`（打刻修正）→ `attendance.save()` 経由で実労働・残業を自動再計算させる
- `OVERTIME` / `PAID_LEAVE` / `COMP_LEAVE` → **`QuerySet.update()` で `save()` をバイパス**
  （`save()` の自動計算で承認値が上書きされるのを防ぐため）

### Excel エクスポートフロー

`ExportAttendanceExcelView` → `services/excel_export.py:export_attendance_excel()`
→ `Attendance` + `DailyReport`（`location_detail` → 列 E、`task_summary` → 列 G）を読み込み
→ `settings.ATTENDANCE_EXCEL_TEMPLATE_DIR/勤務表テンプレート_{year}.xlsx` を埋める。
テンプレート年は `month < 4`（4月年度始まり）のとき `year - 1`。

### GaikinReport

テーブル `tr_gaikin_report`（`managed=True`）— Kms_Calendar の `tt_gaikin_report` とは**完全別物**。
物理削除パターン（`delete_flg` なし）。ファイルは `settings.ATTENDANCE_GAIKIN_ROOT` 以下。

### DailyReport の主要フィールド

- `location_detail` — `work_location == 'OUTSIDE'` 時に JS で表示; Excel 列 E / SchedulePreview に流れる
- `task_summary` — Excel 列 G に流れる

---

## テスト設定（`config/settings_test.py`）

両 PostgreSQL DB を SQLite インメモリで代替、Kms_Calendar を無効化、
`MD5PasswordHasher` で高速化、ロギング抑制。**`.env` 不要**。
テストスイートは常に `--settings=config.settings_test` を付けて実行すること。

### テスト用ユーザー作成の注意

`EvcUser.user_id` は `EmailField` のため、テストで直接インスタンスを作る場合は
メールアドレス形式を使う:

```python
user = EvcUser(user_id='emp@example.com', user_name='山田太郎', is_active=True,
               user_authority='0', delete_flg=0)
user.set_password('password')
user.save()
```

`EvcUser.objects.create_user()` の `user_name` 引数は内部で `normalize_username` を
呼ぶだけでモデルに渡らない既知の挙動がある。`user_name` は上記のように直接フィールドに代入すること。

---

## テンプレート

全テンプレートは `Template/`（アプリ内ではなく）に配置される。

- `Template/base.html` — メインサイト基底
- `Template/attendance/base.html` — 勤怠アプリ基底（独自サイドバーナビ）
- `Template/attendance/` — 勤怠アプリの全テンプレート（403.html を含む）

### Django テンプレートの制約

`{% with %}` は Python 演算子（`or`, `and`, `not`）をサポートしない。
ブール値の組み合わせはビュー側で計算してコンテキスト変数として渡す。
例: `is_red = is_holiday or is_sunday` → テンプレートで `day.is_red`

---

## 主要設定値（`config/settings.py`）

```python
ATTENDANCE_DB = 'kmsdatabase'
ATTENDANCE_GAIKIN_ROOT = '/data_root/evc_root/Gaikin'
ATTENDANCE_EXCEL_TEMPLATE_DIR = '/data_root/data/excel_template'
EVC_ROOT = '/data_root/evc_root/'
```

---

## Kms_Calendar（レガシー）

`settings.USE_GOOGLE_CALENDAR`（本番では現在 `True`）で制御。
`True` のとき `/calendar/` にマウント。
勤怠との統合は段階的に廃止中 — Excel エクスポートと外勤報告書は `attendance` に移行済み。
目標状態: `USE_GOOGLE_CALENDAR = False`、Kms_Calendar を `INSTALLED_APPS` から除去・削除。

---

## コードスタイル・アーキテクチャ

- **ビュー**: 標準 CRUD は CBV（Class-Based Views）。単純な一発処理のみ FBV 可。
- **命名**: モデル → PascalCase; ビュー/フォーム → PascalCase + サフィックス（`PostListView`, `PostForm`）; URL → ハイフン区切り小文字。
- **新規アプリ**: `python manage.py startapp <name>` で作成し、即座に `INSTALLED_APPS` へ追加。
- **モデルファースト**: `views.py` / `forms.py` を編集する前に必ず `models.py` を読んでフィールド名を確認する。
- **CSV インジェクション対策**: ユーザー入力由来の全 CSV セルに `_base.py:csv_safe()` を適用すること。
- **ログ**: `user_id`（メールアドレス）をログに残す場合は必ず `log_utils.py:log_user_id()` で SHA256 ハッシュ化する。

---

## 行動規範（Anti-Loop）

- **Think Before Coding:** 実装や修正を始める前に、「対象ファイル」「修正方針」「終了条件」を1文で提示し、ユーザーの確認を待つか、明確なゴールがある場合のみ実行すること。
- **Surgical Changes Only:** 指示されたバグやエラーの修正だけをピンポイントで行うこと。周辺コードの「ついで修正」・リファクタリング・フォーマット変更は禁止。
- **Verification over Assumption:** 「チェック」を求められたら、必ず `makemigrations --check` や `test` などの具体的コマンドを実行し、その出力を証拠として示すこと。雰囲気で判断しない。
