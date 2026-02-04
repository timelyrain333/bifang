#!/bin/bash
set -e
# 等待 Redis 可用（仅当 CELERY_BROKER_URL 含 redis 时）
if python -c "import os; u=os.environ.get('CELERY_BROKER_URL',''); exit(0 if 'redis' not in u else 1)" 2>/dev/null; then
  : # 未使用 redis，跳过
else
  echo "等待 Redis..."
  while ! python -c "import os, redis; r=redis.from_url(os.environ.get('CELERY_BROKER_URL','redis://redis:6379/0')); r.ping()" 2>/dev/null; do
    sleep 1
  done
  echo "Redis 已就绪"
fi
# 数据库迁移与插件加载（仅主进程需要，celery/dingtalk 可跳过）
if [ "${RUN_MIGRATE:-1}" = "1" ]; then
  python manage.py migrate --no-input
  python manage.py load_plugins
fi
exec "$@"
