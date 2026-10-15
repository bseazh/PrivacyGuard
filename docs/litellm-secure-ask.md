# LiteLLM 受控调用验收

日期：2026-10-13。本机 macOS Apple Silicon。LiteLLM SDK 固定 `1.105.0`；模型使用本机 Qwen3-1.7B MLX，不使用外部 API key 或外部模型服务。

## 流程边界

`privacy_secure_ask(safe_reference, task)` 只接受批准引用、`risk_summary` 或 `summary`。它不接受文件路径、任意 prompt、模型名、URL、headers 或额外 SDK 参数。源文件链路需先通过 `privacy_scan_file`/`privacy_redact_file`；纯文本需先通过 `privacy_scrub_text`。

调用顺序：

1. 验证 token、有效期、输出文件 SHA-256；对文件重新提取文本并要求与批准文本一致。
2. 再执行 PrivacyGuard 规则、Presidio、RedactionEverything NER 与可选 MLX 二次检测。
3. 通过 LiteLLM `CustomGuardrail.apply_guardrail` 接口，由本地 Presidio 检查最终 system/user 消息。
4. Guardrail 成功后才调用 LiteLLM `acompletion`；本地测试记录到的事件为 `guardrail.start -> presidio.http -> guardrail.passed -> upstream.received`。
5. 重新验证安全引用，再等模型答复；模型输出也经过实体检测，有敏感信息时只返回 blocked，不返回原回答。

Core/安全文本/Presidio/引用/输出文件任一步异常均不发模型请求。`LiteLLM` Telemetry、详细日志、回调关闭；HTTP 禁止环境代理、重定向和 SDK 自动重试。任务与回答均有长度上限，不启用 streaming 或 tools。

## 自动化测试

运行：

```bash
.venv/bin/python -m pytest -q tests/test_secure_ask.py tests/test_safe_files.py
```

测试包括：

- 本机记录型 OpenAI-compatible HTTP 上游收到的请求体不含虚构邮箱、手机号；事件顺序证明 Presidio 在发送前。
- Presidio 离线、响应格式错误、发现实体时模型上游请求数均为 0。
- 引用伪造、原文件路径、非法任务、过期引用不会调用上游。
- 安全 DOCX 再提取与文本一致方可继续；文件改动后摘要验证阻断。
- 语义预检失败 fail-closed。
- 模型输出中的邮箱阻断，响应不泄露邮箱值。
- PDF/DOCX 已知原值残留拦截、隐藏 PDF 文本检查和长文档尾部检查。

## 本机真实模型端到端

本次由已有 MLX runtime 在 `127.0.0.1:8011` 提供 OpenAI-compatible API，调用由 LiteLLM `1.105.0` SDK 发出。安全临时 DOCX 含虚构姓名、邮箱、手机号和付款风险；MCP 实际执行文件脱敏、`privacy_secure_ask` 与原路径拒绝。结果：通过；MCP 只返回模型答案，文件/文本计数为 PERSON=1、EMAIL=1、PHONE=1。回答讨论了付款期限、验收标准和违约责任，并无虚构原姓名、邮箱、手机号回流。模型输出再次运行中文语义检查时偶尔会产生需补充核查项，最终法律判断仍需人工复核。

这完成了 PrivacyGuard-Core -> 本机 Presidio -> LiteLLM SDK -> 本机 MLX 上游的一次端到端验收。模型服务由本机配置的服务进程运行；不是生产级多用户网关，也不是 Codex 内置流量拦截器。

## 配置与运行

安装 SDK：

```bash
.venv/bin/pip install -e '.[secure-llm]'
```

启动 Apple Silicon 本地模型（模型目录是本机已下载的现成权重）：

```bash
.venv-mlx/bin/python -m mlx_lm server \
  --model /绝对路径/PrivacyGuard/models/qwen3/Qwen3-1.7B-bf16 \
  --host 127.0.0.1 --port 8011 \
  --chat-template-args '{"enable_thinking":false}'
```

仓库曾由 `LegalRedaction` 重命名为 `PrivacyGuard`，虚拟环境生成的 `mlx_lm.server` 可执行文件可能仍保留旧 shebang；因此启动脚本固定使用 `.venv-mlx/bin/python -m mlx_lm server`，不要直接调用该旧入口。

在 MCP 的 `env` 中设置：

```toml
PRIVACYGUARD_LLM_MODEL = "openai//绝对路径/PrivacyGuard/models/qwen3/Qwen3-1.7B-bf16"
PRIVACYGUARD_LLM_BASE_URL = "http://127.0.0.1:8011/v1"
PRIVACYGUARD_LLM_API_KEY = "local-only"
```

远程模型必须 HTTPS、单独配置 key，并理解脱敏后的合同内容会发往该提供商。不要将 key 写进仓库或发到聊天中。

## 明确限制

- 此 guardrail 只保护通过 `privacy_secure_ask` 由 PrivacyGuard 发起的请求；不能自动管理或拦截 Codex/WorkBuddy 的原生模型请求。
- LiteLLM 的代码库已下载作参考，本项目运行的是官方 LiteLLM SDK wheel；没有启动一个独立 LiteLLM Proxy 服务。
- 本地上游通过测试替身和真实 MLX 分别验证：测试替身证明执行顺序，真实 MLX 证明端到端请求可用。MLX 服务只绑定 loopback。
- 自动识别无法保证零漏检；语义识别和回答仍需要人工校核。
