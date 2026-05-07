#!/bin/bash
set -e  # エラーで即停止

echo "===== デプロイ開始 ====="

# 移動（必要ならパス変更）
cd /home/deploy/projects/evc_system || exit

echo "Pull latest code..."
git pull origin main || exit

echo "Build containers..."
docker compose build || exit

echo "Start containers..."
docker compose up -d || exit

echo "Apply migrations..."
docker compose exec web python manage.py migrate || exit

echo "----- 静的ファイル収集 -----"
docker compose exec web python manage.py collectstatic --noinput || exit

echo "----- Web再起動 -----"
docker compose restart web

echo "===== デプロイ完了 ====="
