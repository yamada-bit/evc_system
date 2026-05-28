#!/bin/bash
set -euo pipefail

cd /home/deploy/projects/evc_system

exec >> /home/deploy/projects/evc_system/logs/cert_renew.log 2>&1

echo "=== START $(date) ==="

docker compose \
  --env-file .env.prod \
  -f docker-compose.prod.yml \
  run --rm -T certbot renew

docker exec nginx_prod nginx -s reload

echo "=== END $(date) ==="