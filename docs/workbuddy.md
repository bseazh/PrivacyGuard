# WorkBuddy 接入

使用仓库内标准 Skill 目录 `skills/privacyguard/` 和 stdio 命令 `.venv/bin/privacyguard-mcp`。

不同 WorkBuddy 版本的 Skill/MCP 配置位置可能不同。接入时应确认该版本是否支持：stdio MCP、服务器环境变量、绝对命令路径和工具调用超时。未经对应版本实测，不宣称配置格式与 Codex 相同。

无论平台如何配置，Agent 工作流必须保持：先 `privacy_scan_file`，仅在 `approved` 后用返回的 `safe_reference` 调用 `privacy_get_safe_content`，失败不得读取原文。
