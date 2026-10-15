# 安装指南

正式下载入口：<https://privacyguard.snorlaxden.fun/>。安装包、版本清单和 SHA-256 均以该国内站点为准，不使用 GitHub Release。

## Agent 模式（Presidio + MCP）

安装 Python 3.11 后执行：

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_privacyguard.sh
./scripts/start_privacyguard.sh
./scripts/test_privacyguard.sh
```

Python 环境位于 `.venv`，不会覆盖桌面端使用的 `.venv-mlx`。若仓库旁存在 `000-Assets/presidio-main`，安装器引用这份本地源码；否则从 Python 包源安装锁定版 2.2.364。默认允许读取 `Documents`、`Desktop`、`Downloads`，可用 `PRIVACYGUARD_ALLOWED_ROOTS` 收窄或修改。

停止服务：

```bash
./scripts/stop_privacyguard.sh
```

可选 Docker Compose 使用官方 GHCR 2.2.364 镜像，但原生 analyzer 不包含本项目的中文补充识别器。本机 Docker daemon 未运行时，应使用上述已验证的 Python sidecar。

## macOS（推荐：Apple Silicon）

完整模式使用 Apple MLX，适用于 M1/M2/M3/M4 等 Apple Silicon Mac。至少建议 16GB 内存和 10GB 可用磁盘。进入国内下载站，下载 `PrivacyGuard-v0.1.5-macos-arm64.dmg`。该文件约 2.8GB，已包含本地模型。

下载后可执行 `shasum -a 256 PrivacyGuard-v0.1.5-macos-arm64.dmg`，并与下载站的 `SHA256SUMS` 比对。首次启动请在访达中右键 PrivacyGuard，选择“打开”。

Intel Mac 可启动规则模式，但不能运行 MLX 语义模型。启动脚本会自动设置规则模式。

## Windows 10/11

Windows x64 的 `v0.1.5` 安装包尚未通过 Windows 实机安装和启动验收，因此下载站暂不开放。当前不能把旧版离线包作为 `v0.1.5` 使用。Windows 只能运行规则模式，语义识别能力与 macOS 不同。

## PDF 假名化说明

- 当前支持有可搜索文本层的 PDF。
- 导出时会先使用 PDF redaction 删除原文字，再原位写入语义假名或自然假名。
- 如果任一确认实体无法在 PDF 中精确定位，程序会停止导出，防止产生“看起来遮住但原文仍存在”的伪脱敏文件。
- 扫描 PDF 尚需 OCR 坐标链路，当前版本不会将扫描件误报为成功。
- PyMuPDF 采用 AGPL/商业双许可证；若将软件闭源商用分发，请购买 Artifex 商业许可或替换 PDF 引擎。
