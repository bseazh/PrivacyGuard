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

## 当前 Codex 会话实测与答案约束修订

本轮后续已在当前 Codex 会话发现并直接调用 `mcp__privacyguard__privacy_process_and_ask`，使用仓库中的虚构 TXT 样本，参数为 `risk_summary`、`create_safe_copy=false`。按 Skill 从 `structuredContent` 读取返回值；没有使用正文读取工具或 `privacy_get_safe_content`。返回 `approved`，姓名、邮箱、手机号各 1 个，`safe_file=null`，没有 `content` 或 `safe_reference`。

第一版收紧提示词后仍发现错误法律推断：“可能导致买方无权拒绝验收”“影响合同效力”。因此第二版进一步限定缺失条款的风险只讨论约定不清、理解分歧、举证困难及争议可能性，不判断权利有无与合同效力，要求事实依据、风险与待核查事项分开。第二版真实调用消除了此前错误，但新增“未约定付款条件”的事实混淆。第三版明确区分付款条件和期限，禁止把缺失验收标准直接推成实际交付不合格。

注意 MCP 是长驻进程，第一次调用后已缓存 Python 模块。第二版代码通过新启动的 MCP 实例测试，不能把新实例结果冒称为当前会话长驻进程已经热更新。用户下次完全退出并重开 Codex 后才会加载最终版本；本次不强制退出正在使用的聊天应用。

新增 `tests/answer_quality_live.py`：只传文件路径，不读取源文件或安全正文；检查返回字段、原值残留、章节区分和已发现的错误推断。该测试针对虚构样本的已知回归，不证明任意回答的事实正确性。仍须人工审阅答案。

最终代码的 Core/受控调用回归检查为 27 项测试、9 个子测试。真实质量测试复测方式：先配置本机 MLX 的 `PRIVACYGUARD_MLX_PYTHON` 与 LiteLLM 的模型名、地址和密钥环境变量，再运行 `.venv/bin/python tests/answer_quality_live.py`。测试失败时不会把失败答案冒称为已通过的安全分析；脚本只用于虚构样本验收。

### 答案质量结论：未通过

第三版提示词的真实输出仍出现“付款条件未明确”“未约定付款前提”，并把被脱敏的联系人说成“联系人信息未提供”。此前只检查旧措辞的窄回归没有捕获这些新错误，现已把这些已观察到的错误加入测试。不能因为某几个禁用词消失就判定事实正确。

这意味着当前 1.7B 模型不适合未经人工确认直接输出合同风险结论。当前运行时 `approved` 只表示隐私处理与发送前后敏感信息检查通过，**不表示法律结论已核验**。本轮没有给生产系统添加一个能够证明事实正确的校验器，也没有把黑名单检查包装成这种能力。

补全回归检查后再次真实运行，脚本以退出码 1 结束，错误为 `AssertionError: Known unsupported inference returned`，确认这些答案问题会被本次样本的质量验收识别。该失败应保留在验收记录中，不能改成跳过测试。

建议下一阶段使用更强的本地模型进行同样的事实支持度评测，并加入逐项证据引用与可程序校验的结构化输出；先保持人工核查。模型升级不能替代事实验收。WorkBuddy 未配置、自然语言自动触发未测试的限制仍然存在。

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

- 当前 Codex 会话显式调用已验证；重启后最终版本以及 WorkBuddy 聊天行为仍需单独验证，不能据此宣称自然语言自动触发已经验收。
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
