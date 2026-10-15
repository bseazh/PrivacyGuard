# PrivacyGuard 技术架构

```text
Codex / WorkBuddy
       |
       v
Skill -> MCP Server -> PrivacyGuard Core
                         |       |
                         v       v
                  Presidio   RedactionEverything
                         \       /
                          Validation
                              |
                    Approved reference / Blocked
```

## 边界

- `privacyguard/core.py` 是唯一 Agent 业务入口。
- `security.py` 解析绝对路径、限制白名单/格式/大小并拒绝路径中的符号链接。
- `store.py` 只接受随机令牌，保存一小时有效的批准结果；任意原路径不能绕过。
- `adapters/presidio.py` 和 `adapters/redaction_everything.py` 只访问回环地址，忽略系统代理。
- 日志和 MCP 扫描结果只暴露类别与数量，不暴露原始敏感值。

## PDF 分流

文本扫描先真实上传到 RedactionEverything。若其返回 OCR/文本内容，进入合并识别和二次扫描；若其误判而 PDF 本身存在可提取文本层，使用本地 `pdftotext`；两者均无内容则阻断。

桌面端原位导出与 Agent 安全副本是两条独立链路。`privacy_redact_file` 先检查源结构，再合并规则、分块 Presidio、RedactionEverything NER 和可选 MLX，执行上游脱敏并下载候选，但不会直接发布该候选。`safe_files.py` 从脱敏后的文本创建全新 PDF/DOCX，检查原值、隐藏 XML、附件、批注和属性，再进行语义复检；全部通过才写入批准目录并生成带 SHA-256 的引用。读取引用时重新验证文件完整性。

安全副本不保留排版，源文件图片、矢量绘图、修订、域、外链和复杂对象无法验证时阻断。文本采用 2400/300 重叠分块；重叠区间取并集，已知实体扩展到全文重复位置。二次检测新增实体可回映原文重新替换，最多三轮，仍不收敛则阻断。MLX 使用独立 Python 子进程，设置 `PRIVACYGUARD_MLX_PYTHON` 才启用。

## LiteLLM 后续位置

`privacy_secure_ask` 只接受已批准引用和两个固定任务。重验引用及文件摘要、重新抽取安全副本文本、再次运行 PrivacyGuard 实体检测后，直接调用 LiteLLM `CustomGuardrail.apply_guardrail`，再由 LiteLLM SDK 发出请求。请求 guardrail 固定为本机 Presidio，失败即阻断；输出再经语义检测。审计测试记录了 `guardrail.start -> Presidio HTTP -> guardrail.passed -> upstream.received` 顺序，并覆盖 guardrail 错误时上游收件数为 0。

真实模型配置可指向本机 MLX server 或 HTTPS OpenAI-compatible provider。只适用于 PrivacyGuard 自身控制的调用，不能描述为接管 Codex 或 WorkBuddy 的内置模型流量。LiteLLM telemetry、消息 logging 和 SDK callbacks 均关闭；HTTP 使用 `trust_env=False`，禁用重试和重定向。
