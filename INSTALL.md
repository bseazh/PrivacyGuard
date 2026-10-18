# 安装指南

## 当前支持范围

一句话完整安装仅支持 macOS Apple Silicon（M1/M2/M3/M4）。建议至少 16GB 内存；安装器最低要求 12GB 内存和 12GB 可用磁盘。Windows 与 Intel Mac 尚未完成同等能力验收。

## 安装

打开“终端”，粘贴：

```bash
curl -fsSL https://raw.githubusercontent.com/bseazh/PrivacyGuard/main/install.sh | bash
```

默认目录为 `~/Documents/PrivacyGuard`。不安装 DMG，不创建捆绑应用。脚本会下载约 4GB 的源码、HaS、PaddleOCR 和 Qwen3 模型组件，支持断点续传并逐一校验 SHA-256；Python 包优先使用清华镜像，失败时切换官方 PyPI。

源码从固定 GitHub 提交下载并校验；独立模型和 RedactionEverything 从国内服务器下载。安装器完成 Python 环境、Presidio、RedactionEverything、MLX、LiteLLM、服务启动、MCP 测试、OCR 页覆盖和真实回答质量测试，生成 WorkBuddy 配置，检测到 Codex CLI 时尝试注册 MCP/Skill。同名冲突不会覆盖；模型不上传 GitHub Release。

首次没有 Homebrew/Python 或 Apple 命令行工具时，需要先按终端提示完成系统安装，再执行同一命令。它不是完全离线安装，Python 依赖仍需要镜像/PyPI，源码需要能访问 GitHub。建议预留 20GB 空间，脚本最低门槛为 12GB，实际不足时应增加空间。

WorkBuddy：退出应用后执行 `~/Documents/PrivacyGuard/.venv/bin/python ~/Documents/PrivacyGuard/scripts/configure_workbuddy.py --apply`，再重开应用。[配置窗口图解及聊天验收](docs/workbuddy.md)。自定义安装路径时替换此命令中的两处路径。

新版缓存为 `~/Library/Caches/PrivacyGuardInstaller/source-v0.1.6`，旧版安装目录不会自动升级覆盖；首次安装到已有非同版本非空目录会停止。GitHub 不可达时不能只用旧国内安装器冒充最新版本；国内新版入口需管理员同步后再开放。

## 启停

```bash
~/Documents/PrivacyGuard/scripts/start_privacyguard.sh
~/Documents/PrivacyGuard/scripts/stop_privacyguard.sh
```

本地端口：RedactionEverything `8000`、HaS `8080`、PaddleOCR `8082`、Presidio `5002`、MLX OpenAI-compatible API `8011`。所有服务只监听本机回环地址。

## 验收结果

安装成功必须同时满足：

1. Presidio、RedactionEverything、HaS、PaddleOCR 和 MLX 健康检查可用；
2. MCP 可发现六个 PrivacyGuard 工具，包括默认聊天入口 `privacy_process_and_ask`；
3. 虚构 DOCX 能生成安全副本；
4. LiteLLM 只接收安全引用，拒绝原文件路径；
5. 模型回答不残留测试中的姓名、邮箱和手机号。

LiteLLM 只能保护 `privacy_secure_ask`，不能拦截 Codex 自身的模型流量。
