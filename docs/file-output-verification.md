# 中文识别合并与安全文件输出验收

日期：2026-10-13。本机 Apple Silicon，核心 Python 3.11，MLX 使用独立 `.venv-mlx`。未修改或重装既有 RedactionEverything。

## 实现范围

- 默认合并规则、Presidio、RedactionEverything NER；环境变量 `PRIVACYGUARD_MLX_PYTHON` 指定已有 MLX Python 时加入 MLX。
- 2400 字符窗口，300 字符重叠，覆盖长文档尾部；验证每个实体的原文及偏移，兼容 confidence=null。
- 重叠实体覆盖区间取并集；已知值扩展到全文重复位置，同类型同值使用同一占位符。
- 二次检测新增实体回映原文重新替换，最多三轮；不收敛或任一识别服务失败即阻断，不降级到原文。
- 新增 `privacy_redact_file` 和 CLI `privacyguard redact`。安全引用只能在全部验证后生成，读取时验证输出 SHA-256。

## 文件检查策略

输出是独立纯文本重建副本，原文件不修改，不保留原始排版。上游 execute/download 接口已接通，但下载结果仅作为候选，绝不直接作为安全副本发布。

| 格式 | 检查与处理 | 无法验证时 |
| --- | --- | --- |
| PDF | 提取文本层（包括可提取的不可见文字），新建文件，清空属性/XMP，不复制批注、附件、链接；重新检查文字、属性、批注、附件、表单 | 图片、矢量绘图、动态/复杂对象、加密和无文本页阻断 |
| DOCX | 读取正文、表格段落、页眉页脚、脚注尾注；新建文件，不复制批注、customXml、文档属性；检查输出全部 XML 和核心属性 | 图片、嵌入对象、外链、修订、域及复杂对象阻断 |

这里的“检查”不表示能够保留所有原文对象。无法完整验证的对象会拒绝处理，隐藏属性等通过不复制来消除，而非仅覆盖可见区域。已识别原值不得出现在输出文本/XML中，输出另作语义复检。

## 已执行测试

- `./scripts/test_privacyguard.sh`：Core/文件输出 36 项、8 个格式子测试通过，LiteLLM 受控调用另有 6 项、3 个子测试通过；MCP stdio 发现五个工具，实际文本脱敏、扫描、PDF/DOCX 安全副本导出与引用读取通过。
- `.venv/bin/python tests/file_output_live.py`：真实 Presidio + RedactionEverything NER/execute/download，PDF 和 DOCX 均通过。
- `PRIVACYGUARD_MLX_PYTHON="$PWD/.venv-mlx/bin/python" .venv/bin/python tests/file_output_live.py`：加上真实 Qwen3 MLX，两种格式均通过。
- 每份虚构样本计数：ORGANIZATION=1、PERSON=2、ADDRESS=1、PHONE=1、EMAIL=1。人名两处共用同一占位符。
- 自动回归覆盖：重叠并集、重复同名、10,000+ 字符尾部、页眉页脚、作者属性、PDF 批注/附件、不可见文字、修订/矢量阻断、输出篡改、晚发现实体、损坏 DOCX、导出失败不生成引用。
- `pip check`：依赖一致。

真实集成样本与输出在临时目录中创建，结束自动清理。未将真实客户文件作为本次测试输入。

## 使用与存储

MCP：`privacy_redact_file(path)` -> approved reference -> `privacy_get_safe_content(reference)` -> 安全文本与输出路径。分析请求仍使用 `privacy_scan_file`。

CLI（仓库根目录）：

```bash
.venv/bin/privacyguard redact /绝对路径/合同.docx
# 使用返回的 safe_reference 获取副本路径：
.venv/bin/privacyguard get 返回的safe_reference
```

实际 CLI 参数以 `.venv/bin/privacyguard --help` 为准。输出位于 `PRIVACYGUARD_DATA_DIR/approved`，默认 `~/.privacyguard/approved`；引用默认 15 分钟过期，可通过 `PRIVACYGUARD_REFERENCE_TTL` 调整，但文件没有自动清理。上游上传的原文/分块也可能被其持久保存，应遵守本地保留策略。

本次本机测试结束后，Presidio 使用会话级 `launchctl submit` 留在后台（标签 `com.privacyguard.presidio`，未创建登录启动项）。健康接口 `http://127.0.0.1:5002/health` 已检查通过；停止该测试后台任务可执行 `launchctl remove com.privacyguard.presidio`。普通安装仍按仓库启动脚本使用。

## 仍然有限制

- 语义识别可能漏检或过度识别，批准不等于零风险，交付前仍需人工复核。
- 含签章、扫描图或复杂排版的真实法律材料不能承诺直接导出；本次仅验收可验证文本样本。
- MLX 每次调用加载模型，长文档可能较慢，子进程上限 600 秒；未做完整 Windows/Linux 实机验收。
- 本次验证 Core、真实上游和 MCP 客户端；未单独重跑宿主 Codex 的新文件导出端到端验收。
- 本机标准 Codex 和 BigApple Codex 的 PrivacyGuard MCP 配置已启用现有 MLX Python，重启后生效；其他机器仍需按各自路径配置。
- 桌面端旧导出不会自动获得这条批准引用；不能将它等同于本次新安全副本链路。
- Skill/MCP 无法强制阻止宿主提前读取文件；`privacy_secure_ask` 已通过 LiteLLM Guardrail 接入本地模型，但不接管 Codex/WorkBuddy 内置模型流量。
- PyMuPDF 为 AGPL/商业双许可，分发前需核对许可。
