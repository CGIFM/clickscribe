#!/usr/bin/env bash
# 把 clickscribe 封装成 macOS 本地 App「步骤记录.app」
# 放到 ~/Applications，并在桌面建快捷方式。可重复运行（覆盖更新）。
# 用法：bash build_app.sh
set -e

APP_NAME="步骤记录"
APP="$HOME/Applications/${APP_NAME}.app"
DIR="$HOME/Projects/clickscribe"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# ---------- Info.plist ----------
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>步骤记录</string>
  <key>CFBundleDisplayName</key><string>步骤记录</string>
  <key>CFBundleIdentifier</key><string>local.clickscribe.app</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSUIElement</key><true/>
  <key>NSAppleEventsUsageDescription</key><string>用于启动本地步骤记录服务。</string>
</dict>
</plist>
PLIST

# ---------- 启动脚本 ----------
cat > "$APP/Contents/MacOS/launch" <<'LAUNCH'
#!/bin/bash
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH
DIR="$HOME/Projects/clickscribe"
cd "$DIR" || exit 1

# 服务已在跑：直接打开网页
if /usr/sbin/lsof -ti tcp:5577 >/dev/null 2>&1; then
  /usr/bin/open http://127.0.0.1:5577
  exit 0
fi

# 否则后台启动（用项目虚拟环境，保证依赖齐全）
nohup "$DIR/.venv/bin/python" "$DIR/app.py" > /tmp/clickscribe.log 2>&1 &
disown

# 等待就绪（最多 ~20s）
for i in $(/usr/bin/seq 1 40); do
  /usr/bin/curl -s -m 1 http://127.0.0.1:5577/api/state >/dev/null 2>&1 && break
  /bin/sleep 0.5
done

/usr/bin/open http://127.0.0.1:5577
LAUNCH

chmod +x "$APP/Contents/MacOS/launch"

# ---------- 桌面快捷方式 ----------
ln -sf "$APP" "$HOME/Desktop/${APP_NAME}.app"

echo "✅ 已创建 App: $APP"
echo "✅ 桌面快捷方式: $HOME/Desktop/${APP_NAME}.app"
echo ""
echo "首次使用提示："
echo "  • 若双击提示「无法验证开发者」：右键 App → 打开 → 仍要打开"
echo "  • 录制无反应：系统设置 → 隐私与安全性 → 辅助功能，把 Python/Terminal 加入并打开"
