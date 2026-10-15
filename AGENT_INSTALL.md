# Agent 安装任务书

目标：在 macOS Apple Silicon 上安装完整 PrivacyGuard，不使用 DMG、桌面安装包或 GitHub Release。

执行：

```bash
curl -fsSL https://privacyguard.snorlaxden.fun/install.sh | bash
```

Agent 应向用户说明：默认安装到 `~/Documents/PrivacyGuard`；下载约 4GB；100Mbps 网络理论下载约 6 分钟，20Mbps 约 28 分钟，实际还需 10–30 分钟安装 Python 依赖和首次加载模型。脚本会检查架构、内存、磁盘、Python、端口服务、SHA-256，并保留下载缓存以便断点续传。

不得关闭 TLS 或跳过 SHA-256。不得在未通过 `tests/mcp_smoke.py` 和 `tests/secure_ask_live.py` 时报告安装成功。检测到已有非空目标目录、已有同名 Codex MCP 或 Skill 时必须停止，不能静默覆盖。

完成后要求用户完全退出并重新打开 Codex，再输入：

```text
请使用 $privacyguard 保护隐私后，分析这份虚构合同并总结风险：/绝对路径/合同.docx
```

Agent 不得先读取原文件；默认必须一次调用 `privacy_process_and_ask`，且不得把安全正文取回宿主上下文。只有用户明确要求下载安全副本时才设置 `create_safe_copy=true`。LiteLLM 只保护 PrivacyGuard 管理的受控调用，不能声称其自动保护 Codex 原生流量。
