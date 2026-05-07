#!/bin/bash

########################################
# 完全自動バックアップ＆シャットダウン
# 機能:
# 1. DB / media / data_root / 設定をバックアップ
# 2. 30日以上古いバックアップ削除
# 3. 圧縮して保存
# 4. オプションでシャットダウン（週次 or 指定日）
########################################
########################################
# 曜日・日付・バックアップ時間・保持日数
# 設定ファイル的に上部で自由に変更可能
########################################
# echo "/home/deploy/projects/evc_system/backup_and_shutdown.sh" | at 18:00 Mar 20

# ===== 基本設定 =====
PROJECT_DIR="/home/deploy/projects/evc_system"
BACKUP_BASE="/home/deploy/projects/backup"
DB_CONTAINER="db"
DB_NAME="evc_db"
DB_USER="postgres"

# バックアップ時間（cron外で実行する場合のみ有効）
BACKUP_HOUR=2   # 0～23
BACKUP_MINUTE=0 # 0～59

# バックアップ保持日数
RETENTION_DAYS=30

# ===== シャットダウン設定 =====
# 曜日シャットダウン（0=日曜,1=月曜,...6=土曜）
# 配列に複数指定可能
WEEKLY_SHUTDOWN_DAYS=(5)  # 金曜

# 指定日シャットダウン（毎月の何日か）
# SPECIFIC_DAYS=(17 20)
SPECIFIC_DAYS=()

# ===== スクリプト開始 =====
DATE=$(date +"%Y%m%d_%H%M")
TODAY_DAY=$(date +"%-d")        # 1～31
TODAY_WEEKDAY=$(date +"%-w")    # 0=日曜, 5=金, etc.
BACKUP_DIR="$BACKUP_BASE/$DATE"

mkdir -p "$BACKUP_DIR"

echo "===== Backup Start $DATE ====="

# 1️⃣ DBバックアップ
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" \
exec -T $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME > "$BACKUP_DIR/db.sql"
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" \
exec -T $DB_CONTAINER pg_dump -U $DB_USER kms_db > "$BACKUP_DIR/kms_db.sql"

# 2️⃣ mediaディレクトリ
# cp -a "$PROJECT_DIR/data_root/media" "$BACKUP_DIR/data_root"

# 3️⃣ data
cp -a "$PROJECT_DIR/data_root/data" "$BACKUP_DIR/data_root"

# 3️⃣ evc_help
cp -a "$PROJECT_DIR/data_root/evc_help" "$BACKUP_DIR/data_root"

# 4️⃣ 設定ファイル
cp -a "$PROJECT_DIR/.env.prod" "$BACKUP_DIR/"
cp -a "$PROJECT_DIR/docker-compose.prod.yml" "$BACKUP_DIR/"
cp -a $PROJECT_DIR/docker $BACKUP_DIR/
cp -a $PROJECT_DIR/nginx $BACKUP_DIR/

# evc_rootバックアップ
/home/deploy/projects/evc_system/backup_deploy/backup_evc_root.sh

echo "===== Backup Complete ====="

# 5️⃣ 古いバックアップ削除
find "$BACKUP_BASE" -mindepth 1 -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \;

# 6️⃣ 圧縮
tar -czf "$BACKUP_BASE/$DATE.tar.gz" -C "$BACKUP_BASE" "$DATE"
rm -rf "$BACKUP_DIR"

# 7️⃣ シャットダウン判定
SHUTDOWN=false

# 曜日シャットダウンチェック
for wd in "${WEEKLY_SHUTDOWN_DAYS[@]}"; do
    if [ "$TODAY_WEEKDAY" -eq "$wd" ]; then
        SHUTDOWN=true
        break
    fi
done

# 指定日シャットダウンチェック
for day in "${SPECIFIC_DAYS[@]}"; do
    if [ "$TODAY_DAY" -eq "$day" ]; then
        SHUTDOWN=true
        break
    fi
done

# 8️⃣ シャットダウン実行
if [ "$SHUTDOWN" = true ]; then
    echo "===== Shutdown Scheduled ====="
    /sbin/shutdown -h now
fi