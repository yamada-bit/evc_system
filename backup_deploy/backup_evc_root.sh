#!/bin/bash

# --- 設定項目 ---
SRC="/home/deploy/projects/evc_system/data_root/evc_root/"  # バックアップ元（末尾に/が必要）
DEST_ROOT="/home/deploy/projects/backup/evc_root"  # バックアップ先
RETENTION_DAYS=15                    # 保存日数（例: 15日分）

TODAY=$(date +%Y%m%d)
YESTERDAY=$(date -d "1 day ago" +%Y%m%d)
DEST_TODAY="${DEST_ROOT}/${TODAY}"
DEST_YESTERDAY="${DEST_ROOT}/${YESTERDAY}"

# 1. バックアップ先ディスクがマウントされているか確認（安全策）
# if ! mountpoint -q /mnt/backup_disk; then
#     echo "Error: Backup disk is not mounted."
#     exit 1
# fi

# 2. バックアップ実行（--link-destで容量節約）
mkdir -p "$DEST_TODAY"
rsync -av --delete \
  --link-dest="$DEST_YESTERDAY" \
  "$SRC" \
  "$DEST_TODAY/"

# 3. 古い世代の削除（15日以上前のディレクトリを削除）
# ※名前が日付形式（YYYYMMDD）のディレクトリのみを対象にする
# -print 追加してログ
# find "$DEST_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +$RETENTION_DAYS -print -exec rm -rf {} \;
# ディレクトリ名（日付）で判定
CUTOFF=$(date -d "-${RETENTION_DAYS} days" +%Y%m%d)
find "$DEST_ROOT" -maxdepth 1 -mindepth 1 -type d | while read DIR; do
  DIRNAME=$(basename "$DIR")
  if [[ "$DIRNAME" =~ ^[0-9]{8}$ ]] && [[ "$DIRNAME" -lt "$CUTOFF" ]]; then
    echo "削除: $DIR"
    rm -rf "$DIR"
  fi
done
echo "Backup completed: $TODAY"
