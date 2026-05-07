#!/bin/bash

echo "===== Docker掃除 ====="
docker image prune -f
echo "完了"