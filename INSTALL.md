# 安装指南

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

完整模式使用 Apple MLX，适用于 M1/M2/M3/M4 等 Apple Silicon Mac。至少建议 16GB 内存和 10GB 可用磁盘。

```bash
git clone https://github.com/bseazh/PrivacyGuard.git
cd PrivacyGuard
chmod +x scripts/*.sh
./scripts/bootstrap_macos.sh
./scripts/start_macos.sh
```

脚本会安装 Python、Node.js、Poppler、Rust，创建 `.venv-mlx`，安装前后端依赖并从 Hugging Face 下载约 3.2GB 的 Qwen3 MLX 权重。首次下载和首次推理会比较慢。

Intel Mac 可启动规则模式，但不能运行 MLX 语义模型。启动脚本会自动设置规则模式。

## Windows 10/11

当前 Windows 安装提供可运行的规则模式，可识别身份证、手机号、邮箱、银行卡号、案号等确定格式。MLX 不支持 Windows，因此人名、机构、地址等语义识别暂未与 macOS 完全对齐。

先在管理员 PowerShell 中安装基础环境：

```powershell
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install oschwartz10612.Poppler
```

重新打开 PowerShell 后执行：

```powershell
git clone https://github.com/bseazh/PrivacyGuard.git
cd PrivacyGuard
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
```

浏览器打开 Vite 输出的本地地址（通常为 `http://localhost:5173`）。所有文件仍在本机处理。

## PDF 假名化说明

- 当前支持有可搜索文本层的 PDF。
- 导出时会先使用 PDF redaction 删除原文字，再原位写入语义假名或自然假名。
- 如果任一确认实体无法在 PDF 中精确定位，程序会停止导出，防止产生“看起来遮住但原文仍存在”的伪脱敏文件。
- 扫描 PDF 尚需 OCR 坐标链路，当前版本不会将扫描件误报为成功。
- PyMuPDF 采用 AGPL/商业双许可证；若将软件闭源商用分发，请购买 Artifex 商业许可或替换 PDF 引擎。
