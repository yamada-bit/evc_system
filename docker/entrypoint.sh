#!/bin/sh
set -e

echo "=============================="
echo " Django Startup"
echo "=============================="

if [ "$RUN_MIGRATE" = "1" ]; then
  echo ">>> migrate"
  python manage.py migrate --noinput
fi

if [ "$SKIP_COLLECTSTATIC" != "1" ]; then
  echo ">>> collectstatic"
  python manage.py collectstatic --noinput
fi

echo ">>> start server"
exec "$@"
