#!/bin/bash
set -euo pipefail

PROJECT_NAME="evc_web"
PROD_COMPOSE="docker-compose.prod.yml"

# =========================
# タグ生成（必ず一意）
# =========================
DATE=$(date +%Y%m%d_%H%M)
GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "no-git")
NEW_TAG="${DATE}_${GIT_HASH}"

echo "======================================"
echo ">>> START DEPLOY: ${NEW_TAG}"
echo "======================================"

# =========================
# STGイメージ存在チェック
# =========================
echo ">>> check stg image exists"
if ! docker image inspect ${PROJECT_NAME}:stg >/dev/null 2>&1; then
  echo "ERROR: stg image not found"
  exit 1
fi

# =========================
# タグ昇格
# =========================
echo ">>> promote image to prod tag: ${NEW_TAG}"
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
if grep -q "^IMAGE_TAG=" .env.prod; then
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${NEW_TAG}/" .env.prod
else
  echo "IMAGE_TAG=${NEW_TAG}" >> .env.prod
fi

echo ">>> current IMAGE_TAG"
grep IMAGE_TAG .env.prod
# =========================
# デプロイ
# =========================
echo ">>> deploy"
# docker compose -f ${PROD_COMPOSE} up -d --no-build
# docker compose -f ${PROD_COMPOSE} up -d --no-deps web
# docker compose -f ${PROD_COMPOSE} up -d --no-deps --force-recreate web
docker compose --env-file .env.prod -f ${PROD_COMPOSE} up -d --no-deps --force-recreate web
# =========================
# ヘルスチェック（任意）
# =========================
echo ">>> health check"
sleep 5
SUCCESS=0
for i in {1..5}; do
  if curl -f http://localhost/health >/dev/null 2>&1; then
    SUCCESS=1  
    break
  fi
  sleep 3
done
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
