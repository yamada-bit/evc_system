#!/bin/bash
set -e

PROD_COMPOSE="docker-compose.prod.yml"
CURRENT_FILE=".current_version"
HISTORY_FILE=".deploy_history.log"
# PREV_TAG_FILE=".last_prod_tag"

# if [ ! -f ${PREV_TAG_FILE} ]; then
#   echo "❌ ロールバック履歴なし"
#   exit 1
# fi

# ROLLBACK_TAG=$(cat ${PREV_TAG_FILE})

# echo "ロールバック → ${ROLLBACK_TAG}"

# IMAGE_TAG=${ROLLBACK_TAG} docker compose -f ${PROD_COMPOSE} up -d

########################################
# 引数チェック
########################################
if [ -z "$1" ]; then
  echo "使い方:"
  echo "  ./rollback.sh IMAGE_TAG"
  echo ""
  echo "履歴:"
  cat ${HISTORY_FILE} || echo "履歴なし"
  exit 1
fi

TARGET_TAG=$1

########################################
# 現在のバージョン取得
########################################
if [ -f ${CURRENT_FILE} ]; then
  CURRENT_TAG=$(cat ${CURRENT_FILE})
else
  CURRENT_TAG="unknown"
fi

echo "======================================="
echo ">>> Rollback実行"
echo " CURRENT = ${CURRENT_TAG}"
echo " TARGET  = ${TARGET_TAG}"
echo "======================================="

read -p "本当にロールバックする？ (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "中断"
  exit 0
fi

########################################
# ロールバック実行
########################################
IMAGE_TAG=${TARGET_TAG} docker compose -f ${PROD_COMPOSE} up -d web

# IMAGE_TAG=${TARGET_TAG} docker compose -f ${PROD_COMPOSE} up -d web
# docker compose -f ${PROD_COMPOSE} exec nginx nginx -s reload

########################################
# 履歴更新
########################################
NOW=$(date "+%Y-%m-%d %H:%M:%S")

echo "${NOW} ROLLBACK_TO=${TARGET_TAG} FROM=${CURRENT_TAG}" >> ${HISTORY_FILE}
echo "${TARGET_TAG}" > ${CURRENT_FILE}
echo ">>> nginx reload"
docker compose -f ${PROD_COMPOSE} exec nginx_prod nginx -t
docker compose -f ${PROD_COMPOSE} exec nginx_prod nginx -s reload

########################################
# 完了
########################################
echo ""
echo "======================================="
echo " Rollback完了"
echo " NOW=${TARGET_TAG}"
echo "======================================="
