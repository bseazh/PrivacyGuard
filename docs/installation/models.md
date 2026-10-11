# 模型权重


> v0.1.4 国内镜像尚未确认同步，当前请使用 GitHub Release；不要使用草稿链接或混用版本。macOS 包只支持 macOS 14+ Apple Silicon，Intel Mac 不适配。
模型文件不纳入 Git。下载前必须核对模型卡与许可证。

已获授权的 standard v0.1.4 离线发行可从[国内平台选择页](https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/)或 [GitHub Release](https://github.com/bseazh/PrivacyGuard/releases/tag/offline-standard-v0.1.4)下载。请选择自己的系统页面，不要遗漏 HaS、PaddleOCR 与 `SHA256SUMS`。

| 能力 | 预期位置 | 说明 |
|---|---|---|
| HaS GGUF | `backend/models/has/has_4.0_0.6B.gguf` | macOS start 脚本当前使用的语义识别权重 |
| HaS HF | `backend/models/has/HaS_Text_0209_0.6B/` | Windows/vLLM 路径 |
| LocateAnything | `backend/models/locateanything/LocateAnything-3B-HF/` | full 视觉模式，非商用许可 |
| PaddleOCR | Paddle/ModelScope 缓存 | 首次启动可能自动下载 OCR 模型 |

下载完成后应保存来源、版本、文件大小和 SHA-256。不要把数 GB 权重直接提交到 GitHub；若使用 Release，应分片并提供校验文件。

模型目录不完整时，启动脚本应降级并明确报告，不得显示为“全部在线”。
