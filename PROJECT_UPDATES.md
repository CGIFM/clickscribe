# PROJECT_UPDATES.md — clickscribe 更新日志

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
