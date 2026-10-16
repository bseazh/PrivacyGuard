# PrivacyGuard 技术架构

README 中的 Mermaid 图是当前架构基线，包含分析、下载、失败闭锁和模型边界。本文保留实现约束和组件职责，任何新增格式或模型都必须接入该主流程。

## 边界

- `privacyguard/core.py` 是唯一 Agent 业务入口。
- `security.py` 解析绝对路径、限制白名单/格式/大小并拒绝路径中的符号链接。
- `store.py` 只接受随机令牌，保存短期有效的批准结果；任意原路径不能绕过。
- `adapters/presidio.py` 和 `adapters/redaction_everything.py` 只访问回环地址，忽略系统代理。
- 日志和 MCP 扫描结果只暴露类别与数量，不暴露原始敏感值。

## 文件处理

所有文件先上传到 RedactionEverything 解析并执行 HaS 识别。空正文、识别失败、无效偏移或无法覆盖完整内容时阻断；PrivacyGuard 不用本地提取或通用 OCR 绕过上游失败。`privacy_process_and_ask` 默认只保存内部安全文本，不重建文件；明确下载时，`safe_files.py` 创建全新 TXT/PDF/DOCX，检查原值、隐藏 XML、附件、批注和属性，再进行语义复检；全部通过才写入批准目录并生成引用。

安全副本不保留排版，源文件图片、矢量绘图、修订、域、外链和复杂对象无法验证时阻断。文本采用 2400/300 重叠分块；重叠区间取并集，已知实体扩展到全文重复位置。二次检测新增实体可回映原文重新替换，最多三轮，仍不收敛则阻断。MLX 使用独立 Python 子进程，设置 `PRIVACYGUARD_MLX_PYTHON` 才启用。

## LiteLLM 后续位置

`privacy_secure_ask` 只接受已批准引用和两个固定任务。重验引用及文件摘要、重新抽取安全副本文本、再次运行 PrivacyGuard 实体检测后，直接调用 LiteLLM `CustomGuardrail.apply_guardrail`，再由 LiteLLM SDK 发出请求。请求 guardrail 固定为本机 Presidio，失败即阻断；输出再经语义检测。审计测试记录了 `guardrail.start -> Presidio HTTP -> guardrail.passed -> upstream.received` 顺序，并覆盖 guardrail 错误时上游收件数为 0。

真实模型配置可指向本机 MLX server 或 HTTPS OpenAI-compatible provider。只适用于 PrivacyGuard 自身控制的调用，不能描述为接管 Codex 或 WorkBuddy 的内置模型流量。LiteLLM telemetry、消息 logging 和 SDK callbacks 均关闭；HTTP 使用 `trust_env=False`，禁用重试和重定向。
