# migrate_prod.sh
#!/bin/bash
set -e

echo "=== [1/4] DB バックアップ ==="
pg_dump -U postgres -d prod_db > /backup/prod_$(date +%Y%m%d_%H%M).sql
echo "バックアップ完了"

echo ""
echo "=== [2/4] 実行予定の migrate を確認 ==="
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm web \
  python manage.py migrate --plan

echo ""
echo "続行しますか？ (yes/no)"
read -r answer
if [ "$answer" != "yes" ]; then
  echo "中断しました"
  exit 0
fi

echo "=== [3/4] migrate 実行 ==="
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm web \
  python manage.py migrate

echo "=== [4/4] 確認 ==="
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm web \
  python manage.py showmigrations

echo "=== migrate 完了 ==="