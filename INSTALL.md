# 安装指南

## 当前支持范围

一句话完整安装仅支持 macOS Apple Silicon（M1/M2/M3/M4）。建议至少 16GB 内存；安装器最低要求 12GB 内存和 12GB 可用磁盘。Windows 与 Intel Mac 尚未完成同等能力验收。

## 安装

打开“终端”，粘贴：

```bash
curl -fsSL https://privacyguard.snorlaxden.fun/install.sh | bash
```

默认目录为 `~/Documents/PrivacyGuard`。不安装 DMG，不创建捆绑应用。脚本会下载约 4GB 的源码、HaS、PaddleOCR 和 Qwen3 模型组件，支持断点续传并逐一校验 SHA-256；Python 包优先使用清华镜像，失败时切换官方 PyPI。

安装器自动完成：预检、Python 环境、Presidio、RedactionEverything、MLX、LiteLLM、服务启动、MCP 测试、真实 LiteLLM 测试，以及 Codex MCP/Skill 注册。

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
