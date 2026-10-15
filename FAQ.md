# 常见问题（FAQ）

## 页面一直显示“正在连接本地服务”或“离线”

这通常不是前端样式问题，而是 `127.0.0.1:8766` 的本地 Python 服务没有启动、启动后崩溃，或端口被占用。先访问 `http://127.0.0.1:8766/health`，再查看 `logs/privacyguard.log`。

## macOS 提示无法导入 `mlx` 或 `mlx_lm`

确认使用 Apple Silicon，并从 `.venv-mlx` 启动：

```bash
source .venv-mlx/bin/activate
python -c "import mlx, mlx_lm; print('OK')"
```

Intel Mac 和 Windows 不能使用 MLX，请改用规则模式：`PRIVACYGUARD_NER_BACKEND=rules`。

## 为什么 Windows 识别不到人名或公司名

Windows 当前默认是规则模式，只识别格式稳定的敏感信息。跨平台语义模型后端仍需增加，不能把 MLX 权重直接搬到 Windows 运行。

## PDF 上传成功，但不能导出假名化 PDF

常见原因是 PDF 为扫描图片、字体编码导致搜索文本与提取文本不同，或确认的实体已经被人工修改。系统会拒绝部分成功的输出。扫描件需等待 OCR 坐标版补丁。

## 为什么只导出 TXT，没有保留 PDF 排版

请选择 PDF 文件、完成全部复核、选择“语义假名”或“自然假名”，再点击“导出假名化 PDF”。技术 Token 模式只用于文本和映射，不用于 PDF 原位回写。

## 假名化以后能否恢复

脱敏 PDF 本身不能恢复原文。需要同时保存导出的 AES-256-GCM 加密映射，并妥善备份原始文件。映射加密密钥目前保存在当前应用的本地存储中；清理应用数据前必须先设计密钥备份流程。

## 模型下载很慢或中断

重新运行 `python scripts/download_model.py` 会复用 Hugging Face 缓存。企业网络可设置 `HF_ENDPOINT` 使用可信镜像，但不要关闭 TLS 校验。

## 模型为什么不直接放进 Git

Git 不适合保存数 GB 权重。当前模型约 3.2GB；GitHub Release 单个资产也有大小限制，需要拆成约 1.9GB 的分片。推荐优先使用 Hugging Face，Release 仅作为版本化镜像。

## 可以把 7GB 权重放到 GitHub Release 吗

可以，但必须拆分。执行 `scripts/package_model_release.sh /模型目录` 生成分片和 `SHA256SUMS`，然后用 `gh release upload` 上传。下载端必须合并并校验 SHA-256。更推荐发布到专门的模型仓库。

## `pdftotext` 不存在

macOS 执行 `brew install poppler`；Windows 执行 `winget install oschwartz10612.Poppler`，然后重新打开终端。

## macOS 打包时报找不到 `cargo` 或 `rustc`

执行 `brew install rustup-init && rustup-init -y`，重新打开终端，确认 `cargo --version` 可用。
# Agent 模式常见问题

## 为什么本地服务返回 502？

常见原因是系统代理接管了 `127.0.0.1` 请求。PrivacyGuard 的 Presidio 与 RedactionEverything 适配器已显式忽略代理环境；自定义脚本也应避免让本地回环请求经过代理。

## 为什么服务离线时没有返回原文？

这是 fail-closed 设计。Presidio、OCR、解析或二次检查失败时必须返回 `blocked`，否则原始敏感信息可能进入 Agent 上下文。

## 为什么有文本的 PDF 被认为是扫描件？

部分字体编码会导致 RedactionEverything 判为 `pdf_scanned`。PrivacyGuard 会再用 `pdftotext` 验证文本层；能提取时走文本层，仍为空时阻断并要求 OCR。

## 为什么不能直接把文件路径传给 get_safe_content？

该工具只接受扫描后生成的随机限时引用，防止任意路径绕过检查。

## Presidio 能识别所有中文姓名和地址吗？

不能。当前 sidecar 稳定识别邮箱和中国手机号，身份证由 PrivacyGuard 校验日期与校验位。中文姓名、机构、地址等语义实体仍需现有 MLX 或 RedactionEverything，并需要人工复核。

## Docker 已安装但不能启动 Compose？

Docker CLI 存在不等于 Docker Desktop daemon 正在运行。本机已验证的默认路径是 Python 3.11 sidecar，不需要 Docker。

## Agent 导出的安全 PDF/DOCX 为什么排版变了？

`privacy_redact_file` 采用独立纯文本重建，不复制原文件对象。这样能够丢弃附件、批注、文档属性等隐藏信息；表格、分页、字体和原位排版不保证保留。它不同于桌面端原位导出。

## 为什么含图片、印章、修订的合同会被阻断？

这些内容尚未通过完整视觉和结构验证。PDF 图片、矢量绘图、动态对象以及 DOCX 图片、嵌入对象、修订、域和外链会阻断安全文件导出。不能通过关闭检查、盖色块或由 Agent 自行提取正文来绕过。

## 怎么判断是否真的启用了 MLX？

必须在启动 MCP 的环境中设置 `PRIVACYGUARD_MLX_PYTHON` 为已有 MLX Python 的绝对路径，并重启 MCP/Codex。未设置时合并规则、Presidio、RedactionEverything；设置后才加入 MLX。Apple Silicon 实测四路合并已通过，但每次调用需加载模型，长文档更慢；超时或模型失败会阻断。

## 显示安全副本阻断时如何排查？

错误只显示阶段和异常类型，不暴露原值。`source-inspection` 查看文件是否包含上述不支持对象；`semantic-detection`/`text-rescan` 检查本地 Presidio、RedactionEverything NER、可选 MLX；`upstream-upload`/`upstream-export` 检查上游上传、脱敏与下载接口；`output-rebuild`/`file-rescan` 是输出结构或复检未通过。先用虚构样本复现，不要把真实文档内容贴进日志或远程对话。

## 引用过期后文件会自动删除吗？

不会。引用过期禁止读取，但批准目录目前没有自动清理任务；上游上传也可能持久保存。请按本地数据保留策略管理 `PRIVACYGUARD_DATA_DIR/approved` 和既有 RedactionEverything 存储。输出文件被修改或替换后，SHA-256 校验会拒绝读取，需重新生成。

## `privacy_secure_ask` 为什么显示 blocked？

它只接受尚未过期的安全引用和 `risk_summary`/`summary`，不能传原文件路径或自由提示词。先确认 Presidio、RedactionEverything、可选 MLX 识别服务可用，再确认 `PRIVACYGUARD_LLM_MODEL`、`PRIVACYGUARD_LLM_BASE_URL`、`PRIVACYGUARD_LLM_API_KEY` 已传给 MCP 进程。Apple Silicon 一键启动脚本在检测到现成模型与 `.venv-mlx` 时会启动 `127.0.0.1:8011`。任何预检、Guardrail、模型或输出复检错误都会 fail-closed。

## LiteLLM 是否会自动保护 Codex 的请求？

不会。LiteLLM 只用于 `privacy_secure_ask` 内部由 PrivacyGuard 发起的请求，无法拦截 Codex、WorkBuddy 或其他应用自己的模型流量。使用远程模型时，即使内容已经脱敏，也仍会发送给该模型提供商；需要另行审查其隐私条款和数据保留策略。
## 识别结果为什么会显示“需要人工确认”？

中文项目名、机构、地址、法院和律师事务所属于语义实体。PrivacyGuard 会先自动识别，但低置信度结果不会直接生成安全副本，必须在桌面端确认或忽略。普通的“合同、协议、测试、项目、系统”等业务词不会单独作为项目名脱敏。

安全副本导出遇到低置信度语义实体时会阻断，这是故意的安全策略，不是服务故障。请在桌面端确认实体后导出；Agent 的文件级安全副本接口仍然采用 fail-closed 策略。

## 安全引用有效期和日志

安全引用默认有效期为 15 分钟，可通过 `PRIVACYGUARD_REFERENCE_TTL` 调整。引用是临时凭证，不应写入报告、聊天记录或 Git。MCP 客户端应优先读取 `structuredContent`，不要同时打印 `content` 和 `structuredContent`，也不要记录完整 `safe_reference`。
