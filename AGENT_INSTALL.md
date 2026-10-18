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

询问用户使用 Codex 还是 WorkBuddy。WorkBuddy 会生成完整示例和单条可粘贴配置；用户授权修改后，先关闭 WorkBuddy，再运行 `scripts/configure_workbuddy.py --apply`。不授权修改时运行 `--copy-entry`，告知用户粘贴到 `mcpServers` 内。必须保留其他 MCP、保留备份、冲突不覆盖。按 `docs/workbuddy.md` 验收六工具与虚构材料；返回的安全副本路径不是安全引用，禁止传给 `privacy_get_safe_content`。

当前新版入口为国内 install.sh，GitHub main/install.sh 备用；固定源码镜像到国内，模型仍来自国内服务器 v0.1.5，不再依赖旧 PrivacyGuard 源码包。无网络或系统依赖时说明阻塞，不关闭 TLS、不跳过测试。完整安装器的本轮验证范围见发布记录，不得声称已在全新用户电脑验收。
