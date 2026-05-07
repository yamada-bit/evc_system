#!/bin/bash
set -e

echo "===== DB同期開始 ====="

PROD_DB=evc_db
PROD_USER=postgres
PROD_DB_KMS=kms_db

STG_DB=stg_evc_db
STG_USER=postgres
STG_DB_KMS=stg_kms_db

DATE=$(date +%Y%m%d_%H%M)
DUMP_FILE="/tmp/db_${DATE}.dump"
DUMP_FILE_KMS="/tmp/db_kms_${DATE}.dump"

# dump
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U $PROD_USER -d $PROD_DB -Fc \
  > $DUMP_FILE
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U $PROD_USER -d $PROD_DB_KMS -Fc \
  > $DUMP_FILE_KMS

# stgリセット
docker compose -f docker-compose.stg.yml exec db_stg \
  psql -U $STG_USER -d postgres -c "DROP DATABASE IF EXISTS $STG_DB;"
docker compose -f docker-compose.stg.yml exec db_stg \
  psql -U $STG_USER -d postgres -c "DROP DATABASE IF EXISTS $STG_DB_KMS;"

docker compose -f docker-compose.stg.yml exec db_stg \
  psql -U $STG_USER -d postgres -c "CREATE DATABASE $STG_DB;"
docker compose -f docker-compose.stg.yml exec db_stg \
  psql -U $STG_USER -d postgres -c "CREATE DATABASE $STG_DB_KMS;"

# restore
cat $DUMP_FILE | docker compose -f docker-compose.stg.yml exec -T db_stg \
  pg_restore -U $STG_USER -d $STG_DB
cat $DUMP_FILE_KMS | docker compose -f docker-compose.stg.yml exec -T db_stg \
  pg_restore -U $STG_USER -d $STG_DB_KMS

# mkdir -p "/home/deploy/projects/evc_system/data_root_stg"
# cp -a /home/deploy/projects/evc_system/data_root /home/deploy/projects/evc_system/data_root_stg

echo "===== DB同期完了 ====="