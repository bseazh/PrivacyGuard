# WorkBuddy 接入

使用仓库内标准 Skill 目录 `skills/privacyguard/` 和 stdio 命令 `.venv/bin/privacyguard-mcp`。

不同 WorkBuddy 版本的 Skill/MCP 配置位置可能不同。接入时应确认该版本是否支持：stdio MCP、服务器环境变量、绝对命令路径和工具调用超时。未经对应版本实测，不宣称配置格式与 Codex 相同。

默认聊天入口是 `privacy_process_and_ask(file_path, task, create_safe_copy)`。WorkBuddy 应把落盘后的绝对路径直接交给该工具，不得先提取或展示附件正文；工具内部完成扫描、脱敏、安全引用隔离、LiteLLM Guardrail 和回答复检，只把分析答案和实体计数返回聊天框。

- 普通分析：`create_safe_copy=false`，不向宿主返回安全正文或引用。
- 后台先使用 RedactionEverything 解析/HaS，再由 PrivacyGuard 假名化并复检；仅内部安全文本进入 Presidio 发送前检查和 LiteLLM。普通分析不重建文档文件。
- 用户明确要求下载安全副本：`create_safe_copy=true`，仅返回已经复检的安全文件路径。
- 任一步返回 `blocked`：停止，不得回退读取原文件或改用通用 OCR。
- 如果 WorkBuddy 只提供附件 ID/临时 URL 而不是本地绝对路径，需要增加附件落盘适配器，把文件写入允许目录后再调用 MCP；未经该版本实测，不宣称附件已被宿主级强制拦截。
