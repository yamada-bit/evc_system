#!/bin/bash

# エラー時に即終了
# -e : コマンド失敗時に終了
# -u : 未定義変数使用時にエラー
# -o pipefail : パイプ途中で失敗しても検知
set -euo pipefail

#######################################
# 基本設定
#######################################

# Docker image 名
PROJECT_NAME="evc_web"
# 使用する compose ファイル
STG_COMPOSE="docker-compose.stg.yml"
# 最後に deploy した tag を保存するファイル
TAG_FILE=".last_stg_tag"
# STG 用 image tag
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
#######################################
# IMAGE_TAG チェック
#######################################
# 空文字防止
if [ -z "$IMAGE_TAG" ]; then
  echo "ERROR: IMAGE_TAG is empty"
  exit 1
fi
# PROJECT_DIR="/home/deploy/projects/evc_system"
# # 移動
# cd $PROJECT_DIR

# echo "----- Git更新 -----"
# git pull origin staging

#######################################
# Docker image build
#######################################
echo ">>> build image"

# Dockerfile.prod を使って image build
# STG は常に :stg tag を使用
docker build -t ${PROJECT_NAME}:${IMAGE_TAG} -f docker/Dockerfile.prod .

#######################################
# コンテナ起動
#######################################
echo ">>> deploy stg"
# web/nginx/db を再生成して起動
# --force-recreate により必ず作り直す
# 環境変数として渡す
IMAGE_TAG=${IMAGE_TAG} docker compose -f ${STG_COMPOSE} --env-file .env.stg up -d --force-recreate web_stg nginx_stg db_stg

echo "IMAGE_TAG=${IMAGE_TAG}"

#######################################
# migrate 実行
#######################################
echo ">>> migrate"

# DB migration 実行
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T web_stg python manage.py migrate
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T web_stg python manage.py migrate --database=kmsdatabase
#######################################
# health check(起動確認)
#######################################
echo ">>> health check"

#sleep 5
echo ">>> wait for app"

# 起動待機
# 最大 15 回 (30 秒)
for i in $(seq 1 15); do
  # nginx -> django health endpoint
  if curl -s http://localhost:8080/health/ -H "Host: stg.sysbevc.com" > /dev/null; then
    echo "OK"
    break
  fi
  echo "waiting... ($i)"
  sleep 2
done
#######################################
# 最終 health check
#######################################
# 失敗時:
# - ログ表示
# - deploy 失敗終了
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
#######################################
# nginx reload
#######################################

echo ">>> nginx reload"
# nginx config syntax check
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T nginx_stg nginx -t
# graceful reload
docker compose -f ${STG_COMPOSE} --env-file .env.stg exec -T nginx_stg nginx -s reload

#######################################
# deploy tag 保存
#######################################
echo "${IMAGE_TAG}" > ${TAG_FILE}

#######################################
# 不要 image cleanup
#######################################
echo ">>> cleanup old images"

# dangling image 削除
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

