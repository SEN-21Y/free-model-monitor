#!/usr/bin/env bash
# cron 调用包装：切换到脚本所在目录，日志按天追加
set -euo pipefail
cd "$(dirname "$0")"

# 授权码也可通过环境变量注入，避免写进 config.json：
# export MONITOR_EMAIL_PASSWORD="your-smtp-password"

python3 main.py >> data/run.log 2>&1
