#!/bin/bash
set -euo pipefail

PROJECT_NAME="evc_web"
STG_COMPOSE="docker-compose.stg.yml"
TAG_FILE=".last_stg_tag"
export IMAGE_TAG="stg"
# DATE=$(date +%Y%m%d_%H%M)
# GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "no-git")
# IMAGE_TAG="${DATE}_${GIT_HASH}"
# .env.stgに固定
# IMAGE_TAG=stg

echo "======================================="
echo " STG Deploy Start"
echo " IMAGE_TAG=${IMAGE_TAG}"
echo "======================================="
# 🔴 念のためチェック（重要）
if [ -z "$IMAGE_TAG" ]; then
  echo "ERROR: IMAGE_TAG is empty"
  exit 1
fi
# PROJECT_DIR="/home/deploy/projects/evc_system"
# # 移動
# cd $PROJECT_DIR

# echo "----- Git更新 -----"
# git pull origin staging

# =========================
# 1. build
# =========================
echo ">>> build image"
docker build -t ${PROJECT_NAME}:${IMAGE_TAG} -f docker/Dockerfile.prod .

# =========================
# 2. stgコンテナ更新（安全）
# =========================
echo ">>> deploy stg"
# 環境変数として渡す
IMAGE_TAG=${IMAGE_TAG} docker compose -f ${STG_COMPOSE} --env-file .env.stg up -d --force-recreate web_stg nginx_stg db_stg
echo "IMAGE_TAG=${IMAGE_TAG}"

echo ">>> migrate"
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T web_stg python manage.py migrate
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T web_stg python manage.py migrate --database=kmsdatabase
# =========================
# 3. 起動確認（超重要）
# =========================
echo ">>> health check"

#sleep 5
echo ">>> wait for app"

for i in $(seq 1 15); do
  if curl -s http://localhost:8080/health/ -H "Host: stg.sysbevc.com" > /dev/null; then
    echo "OK"
    break
  fi
  echo "waiting... ($i)"
  sleep 2
done

curl -f http://localhost:8080/health/ -H "Host: stg.sysbevc.com" || {
  echo "ERROR: app health check failed"
  docker compose -f ${STG_COMPOSE} logs web_stg --tail=50
  exit 1
}

# for i in $(seq 1 10); do
#   docker inspect evc_web_stg --format='{{.State.Status}}' | grep -q "running" && break
#   echo "waiting... ($i)"
#   sleep 3
# done

# # コンテナのステータスがhealthyかrunningか確認
# docker inspect evc_web_stg --format='{{.State.Status}}' | grep -q "running" || {
#   echo "ERROR: evc_web_stg が running になっていません"
#   docker compose -f ${STG_COMPOSE} logs web_stg --tail=50
#   exit 1
# }
# # ① アプリ生存確認（メイン）
# # curl -f http://localhost:8080 || {
# # deploy_stg.sh のヘルスチェック部分
# # curl -f http://localhost:8080/health/ -H "Host: stg.sysbevc.com" || {
# curl -f http://localhost:8080 -H "Host: stg.sysbevc.com" || {
#   echo "ERROR: app health check failed"
#   exit 1
# }
# # ② HTTPS確認（軽く）
# curl -k -s https://localhost:8443 > /dev/null || {
#   echo "WARN: https check failed"
# }
# =========================
# 4. nginx reload（安全）
# =========================
# Reload nginx in stg
# nginxのreloadは起動確認後に実行
echo ">>> nginx reload"
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T nginx_stg nginx -t
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T nginx_stg nginx -s reload
# =========================
# 5. タグ保存
# =========================
echo "${IMAGE_TAG}" > ${TAG_FILE}

# =========================
# 6. 古いimage削除（安全）
# =========================
echo ">>> cleanup old images"
docker image prune -f     # danglingのみ
# docker image prune -a -f  # 未使用image全部
echo ""
echo "======================================="
echo " ✅ STGデプロイ完了"
echo " IMAGE_TAG=${IMAGE_TAG}"
echo ""
echo " 次の手順:"
echo "   → ブラウザでstg確認"
echo "   → OKなら deploy_prod.sh"
echo "======================================="

