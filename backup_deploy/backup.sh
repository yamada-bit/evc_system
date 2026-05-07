#!/bin/bash

DATE=$(date +"%Y%m%d_%H%M")
BACKUP_DIR="/home/deploy/projects/backup/$DATE"
PROJECT_DIR="/home/deploy/projects/evc_system"
CONTAINER_NAME="db" # service名
DB_USER="postgres"
DB_NAME="evc_db"
KMS_DB_NAME="kms_db"

mkdir -p $BACKUP_DIR/data_root

echo "===== Backup Start $DATE ====="

# ① DBバックアップ
docker compose -f $PROJECT_DIR/docker-compose.prod.yml \
  exec -T $CONTAINER_NAME \
  pg_dump -U $DB_USER -d $DB_NAME -Fc > $BACKUP_DIR/evc_db.dump
docker compose -f $PROJECT_DIR/docker-compose.prod.yml \
  exec -T $CONTAINER_NAME \
  pg_dump -U $DB_USER -d $KMS_DB_NAME -Fc > $BACKUP_DIR/kms_db.dump

# docker compose -f $PROJECT_DIR/docker-compose.prod.yml \
# exec -T db pg_dump -U postgres evc_db > $BACKUP_DIR/evc_db.sql
# docker compose -f $PROJECT_DIR/docker-compose.prod.yml \
# exec -T db pg_dump -U postgres kms_db > "$BACKUP_DIR/kms_db.sql"

# ② media
# cp -a $PROJECT_DIR/data_root/media $BACKUP_DIR/data_root

# ③ data
cp -a $PROJECT_DIR/data_root/data $BACKUP_DIR/data_root

# ③ evc_help
cp -a $PROJECT_DIR/data_root/evc_help $BACKUP_DIR/data_root

# ④ 設定ファイル
cp -a $PROJECT_DIR/.env.prod $BACKUP_DIR/
cp -a $PROJECT_DIR/.env.stg $BACKUP_DIR/
cp -a $PROJECT_DIR/docker-compose.prod.yml $BACKUP_DIR/
cp -a $PROJECT_DIR/docker-compose.stg.yml $BACKUP_DIR/
cp -a $PROJECT_DIR/docker $BACKUP_DIR/
cp -a $PROJECT_DIR/nginx $BACKUP_DIR/

# evc_rootバックアップ
/home/deploy/projects/evc_system/backup_deploy/backup_evc_root.sh

echo "===== Backup Complete ====="

# ⑤ 30日以上前のバックアップ削除
find /home/deploy/projects/backup -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;

# ⑥ 圧縮して容量削減
tar -czf /home/deploy/projects/backup/$DATE.tar.gz -C /home/deploy/projects/backup $DATE
rm -rf $BACKUP_DIR