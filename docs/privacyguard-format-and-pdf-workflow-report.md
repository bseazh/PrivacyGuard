# PrivacyGuard 文件格式与 PDF 接入流程报告

> 后续更新：这是分阶段历史报告。统一处理流程已调整：所有文件必须经 RedactionEverything 解析/HaS，分析不重建文件；显式文本导出生成独立 TXT。PDF 分析同样执行完整源结构检查，当前不放行扫描页/图片/矢量内容。下文 `safe-text-reference` 和 OCR 可分析等旧描述不再代表当前能力。以 [统一处理流程与最新验收](unified-pipeline-verification.md) 为准。

日期：2026-10-15  
用途：供开发团队核对当前能力、Agent 调用路径、PDF 上传处理及已发现的问题。

## 1. 执行摘要

PrivacyGuard 当前并非只能处理 TXT。

按仓库当前实现，Agent 安全链路的有效格式如下：

| 格式 | 仅分析 | 生成安全输出 | 当前限制 |
| --- | --- | --- | --- |
| `.txt` | 支持 | 返回安全文本引用 | 不生成文件容器 |
| `.md` | 支持 | 返回安全文本引用 | 不生成文件容器 |
| `.docx` | 支持 | 生成纯文本重建 DOCX | 图片、修订、外链、域及复杂对象会阻断 |
| `.pdf` | 支持有可验证文本的 PDF | 生成纯文本重建 PDF | 图片、签章、矢量对象、加密、无文本页等会阻断安全副本 |
| `.eml` / `.markdown` | 支持 | 返回安全文本引用 | 按文本格式处理，不生成文件容器 |

本次 TXT 实测流程成功：

```text
privacy_scan_file
    -> approved safe_reference
privacy_secure_ask(task=risk_summary)
    -> approved answer
```

宿主 Agent 没有直接读取原文件。受控调用返回 `guardrail=privacyguard-presidio-pre-send`。

## 2. 当前 TXT 调用路径

### 2.1 只分析，不需要下载安全副本

```text
TXT 绝对路径
    -> privacy_scan_file(file_path)
    -> 检查 status == approved
    -> privacy_secure_ask(safe_reference, task="risk_summary")
    -> 返回本地模型风险摘要
```

关键要求：

- Agent 不得先用文件工具读取 TXT。
- `privacy_secure_ask` 只能接收 `safe_reference`，不能接收原文件路径或正文。
- `task` 只能使用 `risk_summary` 或 `summary`。
- 任一环节返回 `blocked` 都必须终止，不得回退读取原文。

### 2.2 用户要求“先生成安全副本”

仓库当前代码对 TXT 的设计是：

```text
privacy_redact_file(TXT 绝对路径)
    -> approved
    -> output_kind=safe-text-reference
    -> privacy_get_safe_content(safe_reference)
```

TXT 没有 PDF/DOCX 文件容器，因此这里的“安全副本”是安全文本引用，不是另一个 `.txt` 输出路径。该引用也可以直接传给 `privacy_secure_ask`。

## 3. PDF 上传后的推荐调用路径

假设用户上传后的实际文件是：

```text
/Users/Apple/Documents/Project/Ryan/Law/002-Anonymize/PrivacyGuard/samples/fictional_contract.pdf
```

必须把这个真实、绝对、非符号链接路径直接交给 PrivacyGuard。Agent 不应先打开或提取 PDF。

### 3.1 目标是分析 PDF 合同风险

推荐流程：

```text
上传 PDF 到允许目录
    -> privacy_scan_file(file_path="/绝对路径/合同.pdf")
    -> status == approved
    -> privacy_secure_ask(
           safe_reference="扫描返回的临时引用",
           task="risk_summary"
       )
    -> 返回受控模型分析结果
```

伪代码：

```python
scan = privacy_scan_file(file_path=uploaded_pdf_absolute_path)
if scan["status"] != "approved":
    stop(scan["reason"])

result = privacy_secure_ask(
    safe_reference=scan["safe_reference"],
    task="risk_summary",
)
```

此路径用于分析，不会生成一个供用户下载的 PDF。

### 3.2 目标是生成可下载的安全 PDF

推荐流程：

```text
上传 PDF 到允许目录
    -> privacy_redact_file(file_path="/绝对路径/合同.pdf")
    -> status == approved
    -> privacy_get_safe_content(safe_reference)
    -> kind=file
    -> 取得随机命名的安全 PDF 路径
```

如果还要让本地模型分析，可以把同一个已批准引用传给 `privacy_secure_ask`：

```python
exported = privacy_redact_file(file_path=uploaded_pdf_absolute_path)
if exported["status"] != "approved":
    stop(exported["reason"])

safe_file = privacy_get_safe_content(
    safe_reference=exported["safe_reference"],
)

analysis = privacy_secure_ask(
    safe_reference=exported["safe_reference"],
    task="risk_summary",
)
```

安全文件默认位于：

```text
~/.privacyguard/approved/<随机文件名>.pdf
```

不得自行猜测或拼接这个输出路径，必须通过 `privacy_get_safe_content` 取回。原始 PDF 不会被修改。

## 4. 上传路径应该如何设计

### 4.1 当前默认允许目录

未设置 `PRIVACYGUARD_ALLOWED_ROOTS` 时，代码默认允许：

```text
~/Documents
~/Desktop
~/Downloads
```

本项目路径位于 `~/Documents` 下，因此默认满足目录限制。

### 4.2 推荐的产品化上传目录

建议为上传文件设置独立入口目录，例如：

```text
/Users/Apple/Documents/PrivacyGuard/inbox
```

启动 MCP 时显式配置：

```text
PRIVACYGUARD_ALLOWED_ROOTS=/Users/Apple/Documents/PrivacyGuard/inbox
```

如需多个目录，使用操作系统路径分隔符配置，并在修改环境变量后重启 MCP 进程。

上传处理端应完成：

1. 将文件写入允许目录中的普通文件，而不是符号链接。
2. 获取落盘后的规范化绝对路径。
3. 将绝对路径交给 `privacy_scan_file` 或 `privacy_redact_file`。
4. 不把浏览器伪路径（如 `C:\\fakepath\\...`）、文件名或相对路径传给 MCP。
5. 不把用户上传文件直接写入 `~/.privacyguard/approved`；该目录只用于 PrivacyGuard 自己批准的输出。

### 4.3 路径校验条件

当前代码要求：

- 必须是绝对路径；
- 文件必须真实存在且为普通文件；
- 路径及其任一级目录不得为符号链接；
- 文件必须位于允许目录内；
- 默认大小为 `1` 字节至 `50 MiB`；
- 扩展名必须进入安全白名单。

不满足任一条件时应返回 `blocked`，客户端不得自行搬运或解析原文件来绕过。

## 5. PDF 的实际处理边界

### 5.1 有文本层的普通 PDF

可以走 `privacy_scan_file` 进行脱敏分析。如果需要安全文件，可再走 `privacy_redact_file`。

Agent 安全副本不是在原 PDF 上盖白框，而是提取已验证文本、脱敏后重新生成一个纯文本 PDF。它不会保留原排版、分页、字体、图片、附件、批注、表单、链接和元数据。

### 5.2 扫描 PDF

分析链路中，`privacy_scan_file` 会先请求 RedactionEverything。只有它返回可验证文本，或本地确实存在可提取文本层时，才可能继续；没有可验证文本时必须阻断。

当前安全文件导出链路更加严格：`privacy_redact_file` 会拒绝包含图片或无文本页面的 PDF。因此纯扫描件、含扫描签章或页面图片的合同通常无法生成安全 PDF 副本。

不得在阻断后由 Agent 自行调用 `pdftotext`、OCR 或通用 PDF 库提取原文继续分析。OCR 坐标回写和视觉对象验证完成前，正确行为是返回阻断原因。

### 5.3 常见会被阻断的 PDF

- 加密 PDF；
- 含图片、印章或扫描页；
- 含矢量绘图或复杂图层；
- 任一页面没有可验证文本；
- 含 JavaScript、动态动作、表单、XFA 或复杂对象；
- 无法验证 OCR 结果；
- 存在低置信度语义实体且安全副本流程要求人工确认；
- Presidio、RedactionEverything、MLX 或输出复检失败。

## 6. 安全引用与数据边界

`safe_reference` 是短期访问凭证，不是文件路径。

当前源码默认有效期为 `900` 秒，即 15 分钟。它不应进入长期日志、报告、Git、错误追踪或用户可复制的调试信息。

客户端应遵循：

- 优先消费 MCP 的 `structuredContent`；
- 只有客户端不支持结构化结果时才回退到文本内容；
- 不要同时打印文本内容和 `structuredContent`，避免同一 JSON 重复出现；
- 日志中对安全引用进行掩码；
- 引用过期或输出哈希变化后重新扫描，不得继续使用旧引用。

## 7. 本次实测结果

### 7.1 TXT 受控分析

```text
privacy_scan_file: approved
privacy_secure_ask: approved
task: risk_summary
guardrail: privacyguard-presidio-pre-send
```

识别出的敏感实体类型包括组织、人员、电话、邮箱和证件号。报告不记录任何原始值或具体安全引用。

### 7.2 自动化测试

执行：

```text
.venv/bin/python -m pytest -q \
  tests/test_safe_files.py \
  tests/test_secure_ask.py \
  tests/test_privacyguard_core.py
```

结果：

```text
32 passed, 11 subtests passed
```

## 8. 已发现的开发问题

### 已解决：运行中的 MCP 与当前仓库代码不一致

先前实际调用 `privacy_redact_file` 处理 TXT 时返回：

```text
status=blocked
reason=安全副本阻断：source-inspection (ValueError)
```

但当前仓库 `PrivacyGuard.redact_file()` 已在进入 `source-inspection` 前把 `.txt` 路由到 `scan_file()`，预期应返回 `safe-text-reference`。

同时，运行中 MCP 暴露的工具描述仍把 `privacy_redact_file` 描述为 PDF/DOCX 安全副本工具，而当前源码已描述 TXT/Markdown/EML/PDF/DOCX。

2026-10-15 复核确认：Codex MCP 已指向当前工作区 `.venv/bin/privacyguard-mcp`；MCP 冒烟测试中 TXT 已返回 `safe-text-reference`。更新 MCP 或 Skill 后仍必须完全重启 Codex/WorkBuddy，避免旧进程和工具描述缓存。

建议：

1. 确认 Codex/BigApple MCP 配置中的 executable、cwd 和 `PYTHONPATH`。
2. 检查实际启动的是工作区 `.venv/bin/privacyguard-mcp` 还是安装目录中的旧副本。
3. 更新安装包后完全重启 MCP/Codex，不只重启本地模型服务。
4. 在健康信息中加入版本号、commit/build ID 和代码根路径。
5. 增加端到端断言：TXT 调用 `privacy_redact_file` 必须返回 `output_kind=safe-text-reference`。

### 已解决：格式声明与路径白名单不一致

`security.py`、本地文本解析器、API 白名单和测试矩阵现已统一支持：

```text
.txt .md .markdown .eml .docx .pdf
```

`.eml` 和 `.markdown` 按安全文本引用处理，不进入 PDF/DOCX 文件重建分支。

建议统一以下位置的格式集合：

- `security.py::SUPPORTED_SUFFIXES`
- `mcp_server.py` 工具描述
- `core.py::redact_file`
- 本地文本解析器
- README、Skill 和测试矩阵

### P1：PDF“分析支持”与“安全副本支持”容易混淆

`privacy_scan_file` 对可验证 OCR 文本或文本层 PDF 可以生成安全文本引用；`privacy_redact_file` 则会因图片、无文本页或矢量内容阻断。产品文案应分别描述“可分析”和“可导出安全 PDF”，避免用户理解为所有可分析 PDF 都能导出。

### P2：引用有效期文档漂移

当前源码默认 `PRIVACYGUARD_REFERENCE_TTL=900` 秒，FAQ 也写 15 分钟；部分旧文档仍写默认一小时。应统一为配置项的真实默认值。

### P2：MCP 结果重复展示

MCP 同时提供文本兼容结果和 `structuredContent`。若调用端同时展开两者，会看到同一 JSON 两次。应在客户端只消费 `structuredContent`，文本仅作兼容回退。

## 9. 建议的验收用例

| 用例 | 预期结果 |
| --- | --- |
| TXT -> scan -> secure ask | 分析成功，模型请求中无原始敏感值 |
| TXT -> redact -> get | 返回 `kind=text`，不进入文件检查分支 |
| 文本层 PDF -> scan -> secure ask | 分析成功 |
| 纯文本且无复杂对象 PDF -> redact -> get | 返回随机路径的重建 PDF |
| 扫描 PDF -> scan | 仅在 OCR 文本可验证时批准，否则阻断 |
| 扫描 PDF -> redact | 当前应阻断 |
| 含签章图片 PDF -> redact | 当前应阻断 |
| PDF 位于允许目录外 | 阻断 |
| 相对路径或符号链接 | 阻断 |
| 将原路径传给 secure ask | 阻断且不得调用模型 |
| 过期或篡改的引用 | 阻断 |
| `.eml` / `.markdown` | 返回批准的安全文本引用，并可继续受控分析 |

## 10. 推荐给 Agent 的标准指令

仅分析 PDF：

```text
请使用 $privacyguard 保护隐私。不要直接读取原文件；先调用
privacy_scan_file 获取安全引用，通过后调用 privacy_secure_ask，
task 使用 risk_summary。

文件路径：/绝对路径/合同.pdf
```

生成安全 PDF 并分析：

```text
请使用 $privacyguard 保护隐私。不要直接读取原文件；先调用
privacy_redact_file 生成安全副本，通过后用 privacy_get_safe_content
取得安全文件路径，并将同一安全引用交给 privacy_secure_ask，
task 使用 risk_summary。任何环节 blocked 都立即停止。

文件路径：/绝对路径/合同.pdf
```

## 11. 结论

系统目前可以处理 TXT、MD、DOCX 和受限 PDF，并非只能处理 TXT。PDF 的正确入口仍是用户上传文件落盘后的绝对路径：只分析走 `privacy_scan_file -> privacy_secure_ask`；需要安全文件走 `privacy_redact_file -> privacy_get_safe_content`，并可继续把同一安全引用交给 `privacy_secure_ask`。

运行中 MCP 路径、文本格式白名单和高层 MCP 编排入口已经统一；扫描 PDF 和含签章、图片、复杂对象的 PDF 仍应按 fail-closed 方式阻断，不能由 Agent 绕过 PrivacyGuard 自行提取。

## 12. 后续实现状态

高层 MCP 工具 `privacy_process_and_ask` 已加入当前分支。它默认不返回安全正文或 `safe_reference`，在内部完成扫描、引用隔离、LiteLLM/Presidio 发送前检查和回答复检；只有用户明确要求安全副本时才返回已批准的文件路径。Codex/WorkBuddy Skill 应优先调用该工具，旧五工具保留用于测试和受控分步流程。
