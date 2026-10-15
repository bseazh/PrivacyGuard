# MVP 实测报告

测试日期：2026-10-13，macOS 14.8.1，Apple Silicon，Python 3.11.14。

## 已验证

- Presidio Analyzer/Anonymizer 2.2.364 从本地官方源码安装成功。
- `127.0.0.1:5002` 真实识别英文邮箱和中国手机号，匿名化结果不含原值。
- 更新后的 Core、文件输出与既有关键测试：36 passed，8 个格式子测试通过；LiteLLM 受控调用另有 6 项、3 个子测试通过。
- 既有 MLX 解析测试在 `.venv-mlx`：7 passed。
- MCP 2.3 stdio 客户端发现五个工具，并实际完成文本脱敏、文件扫描、PDF/DOCX 安全副本导出与引用读取。
- Codex MCP 与 `$privacyguard` Skill 已安装到当前 BigApple Codex 和标准 `~/.codex` 两套用户目录。
- 显式 `$privacyguard` 端到端测试按 `privacy_scan_file -> privacy_get_safe_content -> 风险分析` 执行，没有先读取原文件。
- 自然语言“注意保护隐私”能够自动发现 Skill，并按相同顺序完成处理。
- 两次最终回答均未出现虚构测试邮箱、手机号和身份证原值。
- 非交互 Codex 未授权 MCP 调用时，Agent 会停止且不回退读取原文件，fail-closed 行为符合预期。
- 路径白名单、相对路径、符号链接、引用过期、Presidio 离线均有自动测试。
- RedactionEverything 健康接口以及真实 PDF 上传、解析和 NER 接口已调用；`confidence: null` 已按兼容值处理，实体区间会与文本逐项核验。

## 真实发现的限制

本次新增真实 PDF/DOCX 脱敏执行、下载、独立重建及复检，两种格式均通过；启用 MLX 四路合并后也通过。每份虚构样本识别机构 1、人名出现 2、地址 1、手机 1、邮箱 1。范围和复现命令见 [文件输出验收](file-output-verification.md)。新增工具的宿主 Codex 端到端导出尚未单独验证，不能以此前文本分析验收替代。

测试 PDF 有可提取文本层，但 RedactionEverything 将其判定为 `pdf_scanned` 并返回空内容；PrivacyGuard 增加了本地文本层验证分流。真正扫描件若仍无 OCR 内容会保持 `blocked`。

## 尚未声称完成

- WorkBuddy 特定版本的配置实测。
- 自然语言触发单次实测成功，但不承诺所有措辞都能稳定自动触发；显式 `$privacyguard` 仍是可重复入口。
- 宿主 Agent 调用工具前的强制文件读取拦截。
- `privacy_secure_ask` 已完成记录型上游顺序验收和本机 Qwen3/MLX 真实端到端；详见 [LiteLLM 受控调用验收](litellm-secure-ask.md)。尚未验证远程商业模型，也不接管宿主 Agent 内置流量。
