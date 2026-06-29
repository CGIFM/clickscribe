# PROJECT_UPDATES.md — clickscribe 更新日志

## 2026-06-29 — v0.5.1 HTML 鼠标动效 + 关闭服务

- HTML 导出动效改为 **SVG 鼠标光标**（箭头尖端对准点击点）+ 橙色脉冲圈 + 灰橙小圈（之前只有圆，没有鼠标）
- `/api/shutdown` + 编辑器「⏻ 关闭服务」按钮，点击即停服务
- 空闲 30 分钟自动关闭服务，默认不常驻（关 App/网页后不占资源）

## 2026-06-29 — v0.5.0 封装 Mac 本地 App

- `build_app.sh` 生成「步骤记录.app」到 `~/Applications` + 桌面快捷方式
- 双击自动用项目 venv 启动服务并打开网页；服务已在跑则直接打开网页（避免重复启动）
- `LSUIElement` 让启动器不占 Dock；进程后台常驻
- ⚠️ 从 App 启动的 python 与终端启动的是不同进程，首次录制需在「辅助功能」里重新给 python 授权

## 2026-06-29 — v0.4.0 AI 多接入 + 看全图生成 + 可停止

- **AI 设置面板**：支持三种接入 —— CC Switch 跟随代理（默认免配置）/ 智谱 GLM 直连（填 API Key，glm-4v-plus）/ 自定义 API（base_url + key + model，OpenAI 兼容）
- **看全图生成**：改成一次把所有截图发给模型，理解整个流程上下文后为每步生成连贯说明（替代之前的逐步独立看）
- **可停止**：AI 生成中按钮变「⏹ 停止生成」，AbortController 中断；后端检测客户端断开不保存部分结果
- **配置安全**：`config.json` 存配置并 gitignore；接口返回 key 脱敏
- 后端 `/api/config` GET/POST + `/api/ai` 改看全图 SSE（start/done/error）

## 2026-06-29 — v0.3.0 超清 + 动效 + 进度条 + 多选（大版本）

- **超清截图**：recorder 不再缩放，存 retina 原图（3024×1964），step 记录 `scale`；annotator 用 scale 把逻辑点映射到像素，quality 95、max_side 2880。标注图 1512 → **2880 宽，翻倍清晰**
- **HTML 动效标注**：导出 HTML 用干净原图 + CSS 脉冲圈叠加（深橙线/浅橙半透明填充/灰橙小圈），圈是**动效动画**，不再烧进像素；MD 仍用静态烧录标注
- **AI 流式进度条**：`/api/ai` 改 SSE（start/done/finish 事件），前端实时进度条 X/N，每步完成即时显示说明
- **步骤多选/全选/批量删除** + **一键清空 AI 说明**
- **紧凑布局**：卡片瘦身、截图限高 230px（点击全屏放大），一页显示更多步骤
- 修复：会话不存在 404（非 500）

## 2026-06-29 — v0.2.1 光圈改为 Glitter 三层样式

- 外圈：深橙色描边线 `(220,95,0)`
- 中间：浅橙色半透明填充（高透明度，透出底图）
- 鼠标尖周围：灰橙色小圈环（描边环围绕光标尖端，不再被光标遮挡）
- 像素级验证三层 RGB 各异、层次分明

## 2026-06-29 — v0.2.0 点击标注增强

- 新增 `annotator.py`：半透明橙色光圈 + 箭头鼠标光标（白底、八方向黑边描边，任意背景都清晰）
- 全屏 / 聚焦裁切双模式：聚焦模式以点击点为中心裁出 880×560 局部特写
- 编辑器加「🎯 切聚焦」按钮，全屏 / 聚焦实时切换
- 修复 retina 坐标偏移：`screencapture` 默认 2x 输出 → 按 `backingScaleFactor` 缩放到逻辑 points，对齐鼠标坐标（否则标注画偏左上角）
- 导出 HTML / Markdown 同步带橙色光圈 + 鼠标标注
- 像素级验证通过：光圈 + 光标精确落在点击点

## 2026-06-29 — v0.1.0 首发

**起因**：用户想要 macOS 上「点击某位置自动截图 → 生成操作步骤文档」的工具，类似 Scribe/Folge，但免费/开源/本地。

**调研**：
- 商业工具 Scribe/Tango/Snagit/Folge 都收费或闭源；Folge 有免费档但要 $89 解锁完整。
- GitHub 桌面端对口开源项目只有 3 个：`openstep`(C#, Windows only)、`desktop-automation-agent`(star 0, 过重)、`AgentRunnerRecorder`(无 AI 文档)。**没有即用、完美对口的**。
- 结论：自己造。

**实现**：
- 技术栈 Python 3.14 + pyobjc(`CGEventTap`) + Flask + Pillow + 系统 `screencapture`
- 核心交互：全局常驻监听左键 → 每次点击截全屏 + 记录坐标 → 停止后归档
- 编辑器（仿 Folge）：步骤卡片，可改标题/说明、上下移动、删除
- AI 说明：走 CC Switch 跟随代理(7999) → jlc/glm-5.1 视觉识别
- 导出：Markdown(zip) / HTML(内嵌图) / JSON

**关键坑与解决**：
1. pyobjc 在 Python 3.14 → 有 cp314 wheel（12.2.1），一次装通
2. CC Switch 路径分流 → 不能直连 15721（会走 Codex/OpenAI 通道 502），改走跟随代理 7999
3. jlc/glm-5.1 视觉请求 429 限流 → 图片先缩放+JPEG 压缩，加 429/5xx 重试（3 次指数退避）

**待办**（后续迭代）：
- 截图标注增强：箭头/模糊敏感信息/高亮框（更接近 Folge）
- 导出 PDF / DOCX / PPTX（reportlab / python-docx / python-pptx）
- 插入手动步骤（无截图）
- 录制时实时预览缩略图
