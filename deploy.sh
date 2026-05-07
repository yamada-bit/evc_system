#!/bin/bash
set -e  # エラーで即停止

echo "===== デプロイ開始 ====="

# 設定
COMPOSE="docker compose -f docker-compose.prod.yml"
PROJECT_DIR="/home/deploy/projects/evc_system"

# 移動
cd $PROJECT_DIR

echo "----- Git更新 -----"
git pull origin main

echo "Dockerビルド"
$COMPOSE build

echo "コンテナ起動"
$COMPOSE up -d

echo "マイグレーション"
$COMPOSE exec web python manage.py migrate

echo "静的ファイル収集"
$COMPOSE exec web python manage.py collectstatic --noinput

echo "----- Web再起動 -----"
$COMPOSE restart web

echo "===== デプロイ完了 ====="
