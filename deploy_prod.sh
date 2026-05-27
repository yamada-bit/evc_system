#!/bin/bash

# 厳格モード
set -euo pipefail

#######################################
# 基本設定
#######################################
PROJECT_NAME="evc_web"

# 本番 compose
PROD_COMPOSE="docker-compose.prod.yml"

# =========================
# タグ生成（必ず一意）
# =========================
# 例: 20260525_1530
DATE=$(date +%Y%m%d_%H%M)
# git hash
# git 管理外でも失敗しない
GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "no-git")

# 本番 deploy 用 tag
NEW_TAG="${DATE}_${GIT_HASH}"

echo "======================================"
echo ">>> START DEPLOY: ${NEW_TAG}"
echo "======================================"

# =========================
# STGイメージ存在チェック
# =========================
echo ">>> check stg image exists"

# STG deploy 済 image 必須
if ! docker image inspect ${PROJECT_NAME}:stg >/dev/null 2>&1; then
  echo "ERROR: stg image not found"
  exit 1
fi

# =========================
# タグ昇格(STG image を本番 tag 化)
# =========================
echo ">>> promote image to prod tag: ${NEW_TAG}"

# 同一 image に別 tag 付与
docker tag ${PROJECT_NAME}:stg ${PROJECT_NAME}:${NEW_TAG}

# =========================
# 現在のタグ保存（ロールバック用）
# =========================
PREV_TAG=$(grep IMAGE_TAG .env.prod | cut -d '=' -f2 || echo "")

echo ">>> previous tag: ${PREV_TAG}"

# -------------------------------
# ④ メンテナンスON
# -------------------------------
# echo ">>> maintenance ON"
# docker exec nginx_prod touch /etc/nginx/maintenance.flag || true
# docker exec nginx_prod nginx -s reload || true

# =========================
# .env.prod 更新
# =========================
echo ">>> update .env.prod"

# IMAGE_TAG 更新 or 追加
if grep -q "^IMAGE_TAG=" .env.prod; then
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${NEW_TAG}/" .env.prod
else
  echo "IMAGE_TAG=${NEW_TAG}" >> .env.prod
fi

#######################################
# 現在 tag 確認
#######################################

echo ">>> current IMAGE_TAG"
grep IMAGE_TAG .env.prod
# =========================
# デプロイ
# =========================
echo ">>> deploy"
# docker compose -f ${PROD_COMPOSE} up -d --no-build
# docker compose -f ${PROD_COMPOSE} up -d --no-deps web
# docker compose -f ${PROD_COMPOSE} up -d --no-deps --force-recreate web
# web のみ更新
# nginx/db は触らない
docker compose --env-file .env.prod -f ${PROD_COMPOSE} up -d --no-deps --force-recreate web
# =========================
# ヘルスチェック（任意）
# =========================
echo ">>> health check"
# 起動待機
sleep 5
SUCCESS=0
# 最大 5 回 retry
for i in {1..5}; do
  # nginx 経由 health check
  if curl -f http://localhost/health >/dev/null 2>&1; then
    SUCCESS=1  
    break
  fi
  sleep 3
done

#######################################
# health check failure
#######################################
# if ! curl -f http://localhost/health >/dev/null 2>&1; then
if [ "$SUCCESS" -ne 1 ]; then
  echo "ERROR: health check failed"

  if [ -n "${PREV_TAG}" ]; then
    echo ">>> rollback to ${PREV_TAG}"

    # 先にenv戻す
    sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${PREV_TAG}/" .env.prod

    # 再デプロイ
    if ! docker compose --env-file .env.prod -f ${PROD_COMPOSE} up -d --no-deps --force-recreate web; then
      echo "CRITICAL: rollback also failed! Manual intervention required."
    fi
  fi

  exit 1
fi
# -------------------------------
# ⑩ メンテナンスOFF
# -------------------------------
# echo ">>> maintenance OFF"
# docker exec nginx_prod rm /etc/nginx/maintenance.flag || true
# docker exec nginx_prod nginx -s reload || true

# =========================
# 最新タグも付与
# =========================
echo ">>> tag prod-latest"
# 最新 deploy alias
docker tag ${PROJECT_NAME}:${NEW_TAG} ${PROJECT_NAME}:prod-latest

# -----------------------------
# ⑤ nginx reload（安全）
# -----------------------------
# webだけ更新）なら基本「不要」
# nginx設定を変えたときだけ必要

# echo ">>> nginx reload"
# docker compose -f ${PROD_COMPOSE} exec nginx_prod nginx -t
# docker compose -f ${PROD_COMPOSE} exec nginx_prod nginx -s reload

echo "======================================"
echo ">>> SUCCESS: deployed ${NEW_TAG}"
echo "======================================"
