# PrivacyGuard 新手入口

当前仓库有两套互补入口：

- 桌面端：人工查看、确认和导出假名化结果。
- Agent 安全入口：Presidio + PrivacyGuard Core + MCP + Skill。

## 本机首次安装

```bash
cd /Users/Apple/Documents/Project/Ryan/Law/002-Anonymize/PrivacyGuard
chmod +x scripts/*.sh
./scripts/bootstrap_privacyguard.sh
./scripts/start_privacyguard.sh
./scripts/test_privacyguard.sh
```

安装会使用 Python 3.11 和独立 `.venv`。本机已有 `000-Assets/presidio-main` 时优先以 editable 方式引用该源码；普通用户没有本地源码时会安装锁定版本 `2.2.364`。

## 每次重启电脑后

```bash
cd /Users/Apple/Documents/Project/Ryan/Law/002-Anonymize/PrivacyGuard
./scripts/start_privacyguard.sh
```

现有 RedactionEverything 仍按它自己的方式启动。PrivacyGuard 不会重装或覆盖它。

## 验证一句话流程

安装 Codex 集成会修改用户目录，脚本会先显示目标并要求输入 `INSTALL`：

```bash
./scripts/install_codex_integration.sh
```

完成后完全退出并重新打开 Codex。

安装 MCP 与 Skill 后，在新的 Codex 会话中输入：

```text
$privacyguard 请先保护隐私，再分析 /绝对路径/虚构合同.txt 并总结风险。不要先读取原文件。
```

只有 `privacy_scan_file` 返回 `approved` 后，Agent 才能用 `privacy_get_safe_content` 获取安全内容。

要生成可交付文件，输入：`$privacyguard 请为 /绝对路径/合同.docx 生成安全副本，不要先读取原文件。` Agent 应调用 `privacy_redact_file`，得到 `approved` 后再通过 `privacy_get_safe_content` 获取副本路径。PDF 同理。文件存放于 `PRIVACYGUARD_DATA_DIR/approved`（默认 `~/.privacyguard/approved`），随机命名，引用默认一小时有效。原文件不会被修改。

默认合并规则、Presidio、RedactionEverything NER。Apple Silicon 已安装 MLX 时，在启动 MCP 的环境中设置 `PRIVACYGUARD_MLX_PYTHON` 为 `.venv-mlx/bin/python` 的绝对路径，可加入第四路 MLX；已运行的 MCP/Codex 需要重启。

如果希望由 PrivacyGuard 自己调用本机 Qwen3 分析：先启动本机 MLX OpenAI-compatible server（端口 8011），再在启动 MCP 的配置中设置 `PRIVACYGUARD_LLM_MODEL=openai//绝对路径/到/models/qwen3/Qwen3-1.7B-bf16`、`PRIVACYGUARD_LLM_BASE_URL=http://127.0.0.1:8011/v1`、`PRIVACYGUARD_LLM_API_KEY=local-only`，重启 Codex。再调用 `privacy_secure_ask`，只传批准引用和 `risk_summary`/`summary`。接口在发送模型前运行 Presidio，不接管 Agent 自身的模型流量。正式配置步骤和实测见 [LiteLLM 受控调用验收](docs/litellm-secure-ask.md)。

## 当前限制

- 普通 Skill/MCP 无法强制阻止宿主 Agent 在调用工具前自行读取原文件。
- 扫描 PDF 必须从 RedactionEverything 获得可验证 OCR 文本，否则阻断。
- Presidio 默认模型不等于完整中文姓名和地址识别，中文语义由 RedactionEverything NER 和可选 MLX 补充；上游识别或复检失败会阻断。
- 安全文件导出是纯文本重建，不保留原排版。扫描件、图片、矢量图、修订和复杂对象不在可验证范围内，会阻断，而非只盖色块后放行。
- 检测通过表示已通过当前规则与服务验证，不表示数学意义上的零漏检。
