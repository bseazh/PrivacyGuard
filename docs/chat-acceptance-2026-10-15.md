# 聊天接入验收（2026-10-15）

## 本机检查

- Codex MCP 指向当前仓库 `.venv/bin/privacyguard-mcp`，允许目录包含 Documents、Desktop、Downloads。
- 仓库 Skill 与 `~/.codex/skills/privacyguard/`、BigApple Codex Skill 副本一致。
- WorkBuddy 已安装，但 `~/.workbuddy/mcp.json` 当前只有 `lark-mcp`，尚未注册 PrivacyGuard。本次没有改动其配置。
- 基础自动测试：41 项通过，另有 10 个子测试通过。
- 受控调用测试：10 项通过，另有 3 个子测试通过。使用真实 Presidio 分析器、LiteLLM SDK 与记录请求的测试上游。
- 新增统一入口测试覆盖：不返回正文或内部引用；缺失文件和识别故障不发送模型请求；模型故障不返回答案或文件；显式 DOCX 导出返回独立且经复检的文件。DOCX 导出单元测试替代了上游导出服务，文件重建、复检、引用存储与受控模型调用均实际执行。

真实 MCP → Presidio/RedactionEverything → LiteLLM → 本地 MLX 已通过，整轮约 4 分钟。测试输出确认 `mcp_export`、`text_safe_output`、`mcp_secure_ask`、`privacy_process_and_ask`、`raw_path_blocked` 全部为 true；姓名、邮箱、手机号各识别 1 个。测试断言模型回答和统一入口返回值没有这些原始值。MCP 冒烟验收还覆盖了安全 PDF/DOCX 输出与六个工具发现。

答案质量仍有缺口：模型虽区分“原文事实”和“推测”，但产生了“可能默认按合同签订后一定期限内付款”等无材料依据的说法。下一步应收紧提示词，要求不推定缺失条款，并用人工标注样本测试事实支持度；安全链路通过不等于法律分析准确。

## 用户只需要配合的步骤

1. 保存当前对话，完全退出并重新打开 Codex，开启新对话，使 MCP 与 Skill 配置重新加载。
2. 粘贴下面的测试话术。无需上传真实客户材料，也不要先让通用文件工具提取正文。

```text
请使用 $privacyguard 保护隐私后，分析这份虚构合同并总结风险：
/Users/Apple/Documents/Project/Ryan/Law/002-Anonymize/PrivacyGuard/tests/fixtures/chat-acceptance-contract.txt
不要直接读取文件正文，默认调用 privacy_process_and_ask，且 create_safe_copy=false；如果工具不可用或返回 blocked，请停止并报告原因。
```

3. 把工具调用记录和最终回答提供给维护者，核对：首先调用 `privacy_process_and_ask`；没有先调用文件读取工具；没有调用 `privacy_get_safe_content`；返回 approved；回答包含付款、验收、违约等风险且没有样本中的原始联系方式。若没有工具调用记录，不能据此宣称宿主接入验收通过。
4. 显式 Skill 通过后，再新建对话删除话术中的 `$privacyguard` 测试自然语言触发。自然语言触发仅是便利功能，不是强制安全边界。

WorkBuddy 下一步需先注册同一 stdio MCP、安装 Skill，再重复上述步骤。若附件仅提供 URL/附件 ID，则还需要落盘适配器；先用绝对路径验收。实际入口以安装版本为准，参见 `docs/workbuddy.md`。

## 不能据此宣称已经解决的事情

- 本轮是协议和服务链路验收，尚未实际验证重启后的 Codex/WorkBuddy 聊天行为。
- 固定任务仅支持 `summary`、`risk_summary`，还不能直接传入任意法律问题。
- 受控分析的批准文本超过 20,000 字符会阻断；长文档识别分块不代表长文档模型分析已经支持。
- TXT/Markdown/EML 的导出目前是安全文本引用，不生成可下载文本文件；统一入口返回 `sanitized-text` 且路径为空。
- 安全 PDF/DOCX 是纯文本重建副本，不保留原版式；无法验证的对象会阻断。
- EML 尚不提供完整 MIME 附件的安全处理保证。
- 小模型回答质量和中文识别覆盖率仍需更多人工标注样本评估。本次样本通过不能证明真实材料零漏检。
- Skill/MCP 不能拦截宿主 Agent 自行读取文件或其内置模型流量。
- 本轮未重新部署国内一键安装源，不能把本机测试结果等同于国内发布包验收。

## 复测

在仓库运行 `./scripts/test_privacyguard.sh`。真实模型测试会调用多次本机模型，可能持续数分钟；服务须已启动。单独运行受控调用测试：`.venv/bin/python -m pytest -q tests/test_secure_ask.py`。
