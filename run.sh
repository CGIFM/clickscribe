#!/usr/bin/env bash
# 启动 clickscribe：建虚拟环境、装依赖、跑服务。
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
  echo "📦 创建虚拟环境 ($PY)…"
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo ""
echo "🚀 启动服务…（首次运行需授予「辅助功能」+「屏幕录制」权限）"
echo "   浏览器打开: http://127.0.0.1:5577"
echo ""
exec python app.py
