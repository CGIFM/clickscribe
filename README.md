# clickscribe

> 本地点击截图 → 自动生成操作文档。macOS 上的轻量开源 Scribe/Folge 替代品。

**用法**：点「开始录制」→ 正常操作软件 → 每点一次鼠标自动截一张图（带红圈标注点击位置）→「停止录制」→ 在浏览器里编辑每一步的标题/说明（可 AI 自动生成）→ 导出 Markdown / HTML / JSON。

完全本地运行，零费用；AI 步骤说明走你已有的 CC Switch 路由（不产生额外 API 费用）。

---

## ✨ 功能

- 🖱️ **全局点击监听**：基于 macOS `CGEventTap`，每次鼠标左键按下自动截图
- 🟧 **点击位置标注**：点击处画半透明橙色光圈 + 鼠标光标（仿 Glitter 橙色圈效果）
- ✂️ **聚焦裁切**：编辑器一键切换「全屏 / 聚焦」，聚焦模式以点击点为中心裁出局部特写
- 📝 **步骤卡片编辑器**（仿 Folge）：改标题/说明、上下移动、删除步骤
- ✨ **AI 自动写说明**：glm-5.1 看每张截图，生成「第 N 步：点击 XX」
- 📤 **多格式导出**：Markdown（zip 含图片）/ HTML（单文件内嵌图）/ JSON
- 🔒 **完全离线、数据本地**：截图和会话都在 `sessions/`，不上云

## 🚀 快速开始

```bash
cd ~/Projects/clickscribe
./run.sh
```

浏览器自动打开 **http://127.0.0.1:5577**（没自动开就手动开）。

## 🔐 首次需授予权限（重要）

录制全局点击需要 macOS 两个权限。首次运行 `./run.sh` 后，去：

**系统设置 → 隐私与安全性**
1. **辅助功能**（Accessibility）→ 加入运行本程序的「终端」（Terminal/iTerm）→ 打开开关
2. **屏幕录制**（Screen Recording）→ 同样加入终端 → 打开开关

授权后**重启 `./run.sh`**。编辑器顶部会显示权限状态。

> 截图由系统自带 `screencapture` 完成，必须给它（及其宿主终端）屏幕录制权限，否则截出黑屏。

## 🧠 AI 接入说明（CC Switch 路由）

| 组件 | 地址 | 作用 |
|---|---|---|
| CC Switch | `127.0.0.1:15721` | 按 `/v1/messages` `/v1/chat/completions` `/v1beta` 分流 |
| 跟随代理 | `127.0.0.1:7999` | 实时读 CC Switch 当前 Claude 供应商，转发并强制 model 跟随 |
| clickscribe | → 7999 | **只接 7999**，直连 15721 会走 Codex 通道失败 |

当前供应商 = jlc 中转 / 模型 `glm-5.1`（支持视觉）。图片会先缩放+JPEG 压缩再发送，降低 token 与限流概率，带 429 自动重试。

换环境变量可覆盖：
```bash
CCSWITCH_BASE=http://127.0.0.1:7999 CCSWITCH_MODEL=glm-5.1 ./run.sh
```

## 🏗️ 工作原理

```
鼠标点击 ──CGEventTap──▶ 截屏(screencapture) ──▶ 记录坐标+图片
                                                      │
停止录制 ──▶ 归档到 sessions/<id>/ ──▶ Flask 编辑器(浏览器)
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                   AI 生成说明      编辑/排序/删除       导出
                   (glm-5.1)         (步骤卡片)      MD/HTML/JSON
```

## 📁 目录结构

```
clickscribe/
├── app.py                 # Flask：录制控制 + 编辑器 + 导出 API
├── run.sh                 # 一键启动（建 venv + 装依赖 + 跑服务）
├── requirements.txt
├── clickscribe/
│   ├── recorder.py        # CGEventTap 全局点击监听 + 截图
│   ├── ai_writer.py       # 走跟随代理调 glm-5.1 生成步骤说明
│   ├── store.py           # 会话存储（JSON + 截图）
│   └── exporter.py        # 导出 Markdown/HTML/JSON
├── templates/editor.html  # 仿 Folge 的步骤卡片编辑器
├── sessions/              # 录制输出（git 忽略 _recording）
└── exports/               # 导出文件（git 忽略）
```

## 🔧 技术栈

Python 3.14 · pyobjc（CGEventTap）· Pillow · Flask · 系统自带 `screencapture`

## 📋 迭代历史

- **v0.1.0** (2026-06-29)：首发。全局点击自动截图 + 红圈标注 + 步骤卡片编辑器 + AI 说明（CC Switch/glm-5.1）+ MD/HTML/JSON 导出。

## 🙏 参考

调研过 [folge.me](https://folge.me)（闭源，编辑器体验参考）、[openstep](https://github.com/ebanez8/openstep)（Windows only 的开源步骤记录器，功能设计参考）、[desktop-automation-agent](https://github.com/ralfboltshauser/desktop-automation-agent)（macOS 左键截图+VLM 理念参考）。clickscribe 是它们思路的轻量本地实现。
