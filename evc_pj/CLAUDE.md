# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

Django 5.2 製の EV 充電スタンド管理会社（EVC）向け社内 Web アプリケーション。
PostgreSQL 2 本構成。本番は Gunicorn + リバースプロキシで稼働。

### インストール済みアプリ一覧

| アプリ | マウント先 URL | 用途 |
|---|---|---|
| `users` | — | カスタムユーザーモデル（`EvcUser`）。`AUTH_USER_MODEL = 'users.EvcUser'` |
| `accounts` | `/accounts/` | サイト共通ログイン・ログアウト |
| `Evc_App` | `/Evc_App/` | 充電器点検記録（本体） |
| `Evc_Management` | `/Evc_Management/` | 充電器管理 |
| `Evc_Owner` | `/Evc_Owner/` | 充電器オーナー管理 |
| `Fms_Ocrform` | `/Fms_Ocrform/` | OCR フォーム処理（福祉手当認定診断書＝熊本市が活発に開発中） |
| `Fms_fileshare` | `/Fms_fileshare/` | ファイル共有 |
| `attendance` | `/attendance/` | **従業員勤怠管理（最も活発に開発中）** |
| `commons` | — | 共通ユーティリティ（`mixins.py`, `utils.py`） |
| `Kms_Calendar` | `/calendar/` | Google Calendar 連携（`USE_GOOGLE_CALENDAR=True` のときのみ有効） |

### サイト共通の URL 構成（`config/urls.py`）

```
/              → accounts.EvcLoginView（サイトトップ＝ログイン画面）
/admin/        → Django 管理サイト
/accounts/     → accounts アプリ + django.contrib.auth.urls
/Evc_App/      → Evc_App
/attendance/   → attendance（勤怠）
/health/       → ヘルスチェックエンドポイント（Evc_App.views.health）
/calendar/     → Kms_Calendar（USE_GOOGLE_CALENDAR=True 時のみ）
```

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
| `POSTGRES_DB` / `POSTGRES_DB_KMS` | DB 名（default / kmsdatabase） |
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
  urls.py              — app_name='attendance'（20 URL パターン）
  tests.py             — テストスイート（74件・全件 OK）
  services/
    gaikin.py          — 外勤報告書ファイル I/O（PDF/画像管理・report_id 採番）
    excel_export.py    — 勤務表 Excel 生成（BytesIO を返す）
  utils/
    db_utils.py        — build_user_map(): クロス DB ユーザー一括取得
    log_utils.py       — get_client_ip(), log_user_id(): IP と user_id の SHA256 ハッシュ化
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

### テンプレートディレクトリ

全テンプレートは `Template/`（アプリ内ではなく）に配置される。

```
Template/
  base.html                — メインサイト基底
  attendance/
    base.html              — 勤怠アプリ基底（独自サイドバーナビ）
    403.html               — 権限不足ページ
    attendance_login.html
    dashboard.html
    punch.html
    report.html
    monthly_report.html
    application_form.html
    application_approval.html
    admin_report_list.html
    leave_balance.html
    schedule_preview.html
    gaikin/                — 外勤報告書テンプレート群
    includes/              — 共通パーシャル
```

### 認証・権限

- `EvcUser.user_id` は `EmailField`（Primary Key）。ログインフォームは email アドレス入力。
- 勤怠システム専用ログイン: `AttendanceLoginView`（成功後は打刻画面へ遷移）。
- `is_staff=True` または `is_superuser=True` のユーザーが管理者扱い（`test_func()` で判定）。
- 権限不足は `AttendanceAccessMixin.handle_no_permission()` → `attendance/403.html` を返す。
- ログアウトは **POST** のみ受け付ける（Django 5.x のセキュリティ変更）。テンプレートの
  フォームが `method="post"` になっていることを確認すること。
- ログイン成功時は `session.cycle_key()` でセッション ID を再生成（セッション固定攻撃対策）。

### 月次ロック

`MonthlyReport.status` が `SUBMITTED` または `APPROVED` の月は打刻・日報・申請の
全操作がブロックされる。ガードロジックは `_base.py` にある:

- `LOCKED_STATUSES` — ロック対象ステータスのセット（`frozenset`）
- `is_month_locked(user_id, month_str, *, request=None)` — DB チェック（request 渡しでリクエストスコープキャッシュ）。
  不正な month_str や DB 例外はフェイルセーフとしてロック扱いで返す。
- `MonthLockMixin.month_lock_response()` — POST 先頭で呼び出す

ロック箇所はコード内の `🔒【月次ロック` コメントで検索できる（4 箇所）:
`punch.py` / `report.py`（登録）/ `report.py`（削除）/ `application.py`

### モデルの choice 値（ハードコードしない）

**WorkApplication.apply_type:**
`OVERTIME` / `PAID_LEAVE` / `AM_LEAVE` / `PM_LEAVE` / `COMP_LEAVE` / `CORRECTION`

**WorkApplication.status:**
`PENDING` / `APPROVED` / `REJECTED`

**MonthlyReport.status:**
`UNSUBMITTED` / `SUBMITTED` / `APPROVED` / `REJECTED`

**Attendance.work_type:**
`NORMAL` / `PAID_LEAVE` / `AM_LEAVE` / `PM_LEAVE` / `COMP_LEAVE`

有給消費日数マップ（`_base.py:LEAVE_COST`）と `APPLY_TYPE_CHOICES` は必ずセットで更新すること。

### 承認時の Attendance 更新パターン（重要）

- `CORRECTION`（打刻修正）→ `attendance.save()` 経由で実労働・残業を自動再計算させる
- `OVERTIME` / `PAID_LEAVE` / `COMP_LEAVE` → **`QuerySet.update()` で `save()` をバイパス**
  （`save()` の自動計算で承認値が上書きされるのを防ぐため）
- 有給承認時は `LeaveBalance.used_days += LEAVE_COST[apply_type]`（`get_or_create` で年度レコードを確保）

### Excel エクスポートフロー

`ExportAttendanceExcelView` → `services/excel_export.py:export_attendance_excel()`
→ `Attendance` + `DailyReport`（`location_detail` → 列 E、`task_summary` → 列 G）を読み込み
→ `settings.ATTENDANCE_EXCEL_TEMPLATE_DIR/勤務表テンプレート_{year}.xlsx` を埋める。
テンプレート年は `month < 4`（4月年度始まり）のとき `year - 1`。
テンプレート不在時は `None` を返し、呼び出し元でエラーメッセージ + redirect。

### GaikinReport

テーブル `tr_gaikin_report`（`managed=True`）— Kms_Calendar の `tt_gaikin_report` とは**完全別物**。
物理削除パターン（`delete_flg` なし）。ファイルは `settings.ATTENDANCE_GAIKIN_ROOT` 以下。
`report_id` は `YYYYMMDD_NNNNN`（5桁連番）形式。`services/gaikin.py` で採番・ファイル管理。

### DailyReport の主要フィールド

- `location_detail` — `work_location == 'OUTSIDE'` 時に JS で表示; Excel 列 E / SchedulePreview に流れる
- `task_summary` — Excel 列 G に流れる

### ダッシュボード設計方針

各セクション（本日の状況・月次サマリー・グラフ・申請履歴）を **独立した try-except** で囲む。
グラフ生成だけ失敗しても他セクションは表示を維持する（部分障害耐性）。

---

## Fms_Ocrform アプリ構成（OCR帳票管理・活発に開発中）

写メ（スマホ写真）や PDF でアップロードされた帳票を AI-OCR で読み取り、データ登録する仕組み。
`model_name` パラメータでモデルを汎用的に切り替える設計（勤務表 / 送り状 / JAふくおか八女 /
福祉手当認定診断書＝熊本市子育て支援 の4種を1系統のビュー・テンプレート群でさばく）。

```
Fms_Ocrform/
  models.py           — TtOcrform(フォームテンプレート), TtEntry, TtTimesheet, TtOcrData,
                        TtJafyame, TtAccessLog
  forms.py            — Evc*Form 群（EvcEditKumamotoForm, EvcKumamotoListForm 等）
  urls.py             — model_name汎用ルーティング + export_kumamoto_json
  views.py            — EvcSaveOcrformView / EvcOcrformListView / EvcEditOcrformView
                        （フォームテンプレートの登録・一覧・編集。matrix_name 非依存）
  views_ocrdata.py    — EvcUploadOcrDataView / EvcOcrDataListView / EvcEditOcrDataView
                        （データの保存・一覧・編集。model_name で分岐する汎用ビュー）
  svf_common.py       — align_image()/svf_adjust_image()（画像位置合わせ）,
                        svf_detect_circled_choice()（丸囲み選択肢の判定）, ROOT_FOLDER
  svf_extract_image.py — PDF→画像変換
  svf_extract_text.py  — OCRテキスト抽出・エリア抽出（get_area_textdatas()）
  svf_ocrform.py       — フォームテンプレート関連ヘルパー
  svf_ocrdata.py       — kumamoto関連の定数・キーワード抽出・エリア抽出とのマージロジック一式
  svt_adjust_image.py  — 台形補正（svt_adjust_image_trapezoid）
  static/Fms_Ocrform/js/Fms_timesheet.js — 一覧画面共通の削除確認モーダル・全クリア処理
```

URLパターン（`model_name` は `entry`/`timesheet`/`ocrdata`/`jafyame`/`kumamoto`）:

```
/Fms_Ocrform/upload_ocrform/<data_type>/         → フォームテンプレート登録
/Fms_Ocrform/ocrform_list/<data_type>/           → フォームテンプレート一覧
/Fms_Ocrform/upload_ocrdata/<model_name>/        → データアップロード
/Fms_Ocrform/ocrdata_list/<model_name>/          → データ一覧
/Fms_Ocrform/ocrdata_edit/<model_name>/<id>/<page>/ → データ編集
/Fms_Ocrform/export_kumamoto_json/<ocrdata_id>/  → kumamoto専用JSONダウンロード
```

### 福祉手当認定診断書（kumamoto）

`TtOcrData` を流用（専用テーブルは持たない）。`ocrform_name` が
`KUMAMOTO_FORM_NAME_PREFIX = '福祉手当認定診断書'` で始まるフォームのみが対象
（`get_kumamoto_ocrform_ids()`）。登録済みテンプレート ID: `ofrm_00030`
（実PDFから PyMuPDF で座標を直接抽出して登録。⑦⑧を含む9項目の抽出エリアを持つ）。

**2種類の抽出方式を統合**:

1. **エリア抽出** — `ocrform_area`/`ocrform_text`（200DPIピクセル座標）を
   `get_area_textdatas()`（`svf_extract_text.py`）で読む。結果は英字キー（`item_json`）。
2. **キーワード抽出** — `KUMAMOTO_KEYWORDS`（日本語文字列）を `svf_extract_keywords()` で
   `fulltext` から検索。`KEYWORD_SEPARATORS` を区切り文字として扱う。

`svf_merge_kumamoto_search_text(area_dict, fulltext)` が両者を統合し、
**エリア抽出の値を優先、空の項目だけキーワード抽出で補完**した日本語キーの辞書を作る。
（この統合をしないと、エリア抽出の結果が計算されるだけで画面にもJSONにも出ない
「死んだデータ」になるので注意 — 過去に実際に起きた不具合）。

**`KUMAMOTO_FIELD_MAP`**（日本語キーワード ⇔ 半角英字フィールド名の対応表）が
`get_scon_info()`（初期表示）・`form_valid`の`commit`分岐（登録保存）・
`EvcEditKumamotoForm` の3箇所から汎用的に参照される。
**新しい項目を追加する時は、この表・`KUMAMOTO_KEYWORDS`・`EvcEditKumamotoForm`のフィールド・
`FE_EditKumamoto.html`の`e-data`ブロックをセットで追加すること**（連動していないと
画面・JSONに反映されない）。

**丸で囲む形式の選択肢の自動判定**（`KUMAMOTO_DETECT_CIRCLED_CHOICES`フラグ、現在 **False＝無効**）:
テンプレート画像と位置合わせ済み画像を候補矩形ごとに二値化差分し、最も差分が大きい
選択肢を採用する方式（`svf_detect_circled_choice()`、`min_diff_ratio=0.08`）。
`KUMAMOTO_CIRCLE_FIELDS` に10項目・41択（⑦推定/確認、⑧有/無、⑩胸部Ｘ線所見×6項目×4択、
⑪活動能力の程度5択、⑬安静を要する程度8択）の実座標を登録済み。フラグを `True` にすると
`_KUMAMOTO_CIRCLE_FIELD_MAP` 経由で `KUMAMOTO_FIELD_MAP`/`KUMAMOTO_EXPORT_KEYS`/
フォームフィールドに自動的に合流する（データ駆動、コード変更不要）。単体テストでの
判定精度は確認済みだが、実運用データでの検証待ちのため現状は無効化されている。

**JSONダウンロード**: `export_kumamoto_json`（`KUMAMOTO_EXPORT_KEYS` を参照。フラグが
`False` の間は丸囲み項目を含まない9項目のみ）。画面上のダウンロードボタンは
`FE_EditKumamoto.html` 内で `{% comment %}` により現在非表示。

### 画像位置合わせ（`svf_common.py`）

ORB特徴点 + `knnMatch`(k=2) + Loweの比率テスト（`LOWE_RATIO=0.75`） +
RANSACホモグラフィ（`RANSAC_REPROJ_THRESHOLD=5.0`, `MIN_MATCH_COUNT=10`） +
`cv2.warpPerspective`。`svf_adjust_image()`は`(adjusts, failed_pages)`のタプルを返し、
位置合わせに失敗したページはアップロードエラーとして扱う（サイレントに握りつぶさない）。

### 一覧画面のJS（削除・全クリア）

行削除は `Fms_timesheet.js` の共通クリックハンドラが `data-href` 属性の文字列
（`ocrdata_edit/<model_name>/`）をパースして `ocrdata_id` を抜き出す方式。
**新しい `model_name` を追加する時はこの分岐にも追加すること**
（追加を忘れると削除確認モーダルが開かない — 過去に kumamoto で実際に起きた不具合）。
`clear_all()`（全クリアボタン）は全一覧画面で共有されているため、
**画面に存在しないフィールドを触る時は必ず `getElementById(...) != null` でガードすること**
（ガードが無いと存在しない画面で例外が発生し、それ以降の処理が止まる）。

### スマホ対応の注意点（一覧画面）

一覧画面共通CSS（`Fms_Ocrform/css/FE_TimesheetList.css` → `azborn.css`）は
勤務表の項目構成を前提にした設計のため、新しい一覧画面を追加する際は要注意:

- 検索パネル（`#form-area`）の開閉トグル（`#s-toggle` クリックで `body.s-open` を切替）は
  **一覧画面専用CSS（`FE_TimesheetList.css`）側に実装すること。全ページ共通の`azborn.css`
  に足すと、編集画面が同じ `#s-toggle` という id を別用途（編集アイコン等）で使っており、
  背景色・アイコン色が競合してアイコンが見えなくなる**（実際に発生した回帰）。
- スマホのカード表示は「削除ボタンは3列目（`td:nth-child(3)`）に置き、テーブルは
  4列以上を維持する」という前提。3列に統合すると `.ev-table td:last-child{display:none}`
  が3列目にも掛かってしまい、全項目が消える。
- `.tooltip.sp-hidden`（PC専用のホバー削除アイコン）と `.tooltip{display:inline-block}`
  は詳細度が同点で、宣言順（`.tooltip`側が後勝ち）により `.sp-hidden` が効かないことがある。
  スマホで確実に非表示にしたい場合は `.tooltip.sp-hidden` のように2クラス指定で
  詳細度を上げること。
- `table{box-shadow:...}`（`azborn.css`、角丸なし）は常時有効。行ごとに角丸の影を
  追加する場合はテーブル自体に `box-shadow:none` を当てて打ち消さないと、
  外側に角のない影が二重に見える。
- 検索フォームの `<label>` は付けない（placeholder のみ）のが既存の慣習
  （`FE_JafyameList.html`/`Evc_App/FE_EviList.html` 参照）。`<label for="id_pdf_name">`
  を追加すると、共通CSSの `.read .s-label{grid-area:...}` が別の行にラベルだけ
  飛ばしてしまい崩れる。

### スマホメニュー

`Fms_base_ocrform.html` のスマホ用メニュー先頭2項目は「福祉手当認定診断書保存・一覧」を
常時表示（「フォーム登録」「フォーム一覧」はPC専用）。サイト共通メインメニュー
（`Template/accounts/FE_Menu.html`）の「フォームサービス」リンクもスマホ限定で
福祉手当認定診断書保存画面へ直接遷移する。JAふくおか八女はメニューから削除済み
（機能・URL・ビュー自体は削除していない）。

### アップロードファイルサイズ上限

`DATA_UPLOAD_MAX_MEMORY_SIZE`/`FILE_UPLOAD_MAX_MEMORY_SIZE` = 20MB
（`config/settings.py`。Djangoデフォルトは2.5MBで、スマホカメラの写真（数MB〜10MB）で
413/400エラーになるため引き上げ済み）。本番のリバースプロキシ（nginx等）の
`client_max_body_size` も別途十分な値に設定する必要がある
（このリポジトリには含まれない外部設定）。

---

## テスト設定（`config/settings_test.py`）

両 PostgreSQL DB を SQLite インメモリで代替、Kms_Calendar を無効化、
`MD5PasswordHasher` で高速化、ロギング抑制。**`.env` 不要**。
テストスイートは常に `--settings=config.settings_test` を付けて実行すること。
現在 74 件・全件 OK（0.6 秒）。

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

## Django テンプレートの制約

`{% with %}` は Python 演算子（`or`, `and`, `not`）をサポートしない。
ブール値の組み合わせはビュー側で計算してコンテキスト変数として渡す。
例: `is_red = is_holiday or is_sunday` → テンプレートで `{{ day.is_red }}`

---

## 主要設定値（`config/settings.py`）

```python
AUTH_USER_MODEL         = 'users.EvcUser'
ATTENDANCE_DB           = 'kmsdatabase'
ATTENDANCE_GAIKIN_ROOT  = '/data_root/evc_root/Gaikin'
ATTENDANCE_EXCEL_TEMPLATE_DIR = '/data_root/data/excel_template'
EVC_ROOT                = '/data_root/evc_root/'
USE_GOOGLE_CALENDAR     = True   # 本番は True。目標状態は False（Kms_Calendar 廃止予定）
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # デフォルト2.5MB→20MB（スマホ写真アップロード対応）
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
```

---

## Kms_Calendar（レガシー・廃止予定）

`settings.USE_GOOGLE_CALENDAR`（本番では現在 `True`）で制御。
勤怠との統合は段階的に廃止中 — Excel エクスポートと外勤報告書は `attendance` に移行済み。
目標状態: `USE_GOOGLE_CALENDAR = False`、Kms_Calendar を `INSTALLED_APPS` から除去・削除。

---

## セキュリティ実装（横断的ルール）

| リスク | 対策 | 実装箇所 |
|---|---|---|
| セッション固定攻撃 | ログイン成功時に `session.cycle_key()` | `auth.py` |
| CSV/Excel 数式インジェクション | `=`, `+`, `-`, `@` で始まる値に `'` を付与 | `_base.py:csv_safe()`, `excel_export.py:_sanitize_cell_value()` |
| ユーザーID漏洩 | ログには SHA256 ハッシュのみ記録 | `log_utils.py:log_user_id()` |
| IP 偽装 | `USE_X_FORWARDED_FOR=False`（デフォルト）で X-Forwarded-For を参照しない | `log_utils.py:get_client_ip()` |
| 不正アクセス | `test_func()` 失敗時にアクセスログを残して HTTP 403 | `AttendanceAccessMixin` |

---

## 成果物・設計資料

- `attendance_詳細設計書.xlsx` — /app/ 直下に配置。18 シートでアプリ全体を網羅した詳細設計書。
  （シート構成: 目次 / システム概要 / モデル定義 / URL設計 / 認証・権限 / ダッシュボード /
  打刻処理 / 日報設計 / 月報設計 / 申請フロー / 承認処理 / 管理者機能 / 外勤報告書 /
  Excel出力 / 通知設計 / ユーティリティ / セキュリティ / エラー処理）

---

## コードスタイル・アーキテクチャ

- **ビュー**: 標準 CRUD は CBV（Class-Based Views）。単純な一発処理のみ FBV 可。
- **命名**: モデル → PascalCase; ビュー/フォーム → PascalCase + サフィックス（`PostListView`, `PostForm`）; URL → ハイフン区切り小文字。
- **新規アプリ**: `python manage.py startapp <name>` で作成し、即座に `INSTALLED_APPS` へ追加。
- **モデルファースト**: `views.py` / `forms.py` を編集する前に必ず `models.py` を読んでフィールド名を確認する。
- **CSV インジェクション対策**: ユーザー入力由来の全 CSV セルに `_base.py:csv_safe()` を適用すること。
- **ログ**: `user_id`（メールアドレス）をログに残す場合は必ず `log_utils.py:log_user_id()` で SHA256 ハッシュ化する。
- **エラーハンドリング**: ログレベルは `ERROR` / `WARNING` / `CRITICAL` を明確に分離する。
  `CRITICAL` は「管理者が気づかないと業務継続不能」な障害のみ（例: CSV 全体出力失敗）。
  メール通知失敗は `WARNING` に留め、業務処理（承認）は継続させる。

---

## 行動規範（Anti-Loop）

- **Think Before Coding:** 実装や修正を始める前に、「対象ファイル」「修正方針」「終了条件」を 1 文で提示し、ユーザーの確認を待つか、明確なゴールがある場合のみ実行すること。
- **Surgical Changes Only:** 指示されたバグやエラーの修正だけをピンポイントで行うこと。周辺コードの「ついで修正」・リファクタリング・フォーマット変更は禁止。
- **Verification over Assumption:** 「チェック」を求められたら、必ず `makemigrations --check` や `test` などの具体的コマンドを実行し、その出力を証拠として示すこと。雰囲気で判断しない。
