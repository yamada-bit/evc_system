#!/bin/bash
set -euo pipefail

cd /home/deploy/projects/evc_system

docker compose \
  --env-file .env.prod \
  -f docker-compose.prod.yml \
  run --rm certbot renew \
  --webroot -w /var/www/certbot

docker exec nginx_prod nginx -s reload