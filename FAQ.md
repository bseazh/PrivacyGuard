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

## 一句话安装下载很慢或中断

直接重新执行同一条安装命令。组件缓存在 `~/Library/Caches/PrivacyGuardInstaller/v0.1.5`，`curl -C -` 会从已下载位置继续，不会从头开始。不要删除缓存、关闭 TLS 或跳过 SHA-256。

## 模型从哪里下载

安装器从国内服务器下载三个独立组件：Qwen3 压缩包约 2.5GB（解压约 3.2GB）、HaS 约 0.9GB、PaddleOCR 约 0.5GB。它们不是 DMG 或捆绑应用；脚本校验后解压到安装目录。

## 为什么不再使用 GitHub Release 或 DMG

当前正式入口统一为 `https://privacyguard.snorlaxden.fun/install.sh`。国内服务器只托管安装脚本、源码和独立模型组件，以改善国内下载与断点续传；用户最终得到的是普通源码目录和 Python 虚拟环境，不是捆绑应用。

## 是否需要 VPN

正常情况下不需要。源码和大模型组件来自国内下载域名，Python 包优先使用清华镜像；只有镜像缺包时才回退官方 PyPI。若公司网络同时阻止国内域名和 PyPI，应由网络管理员放行 HTTPS，不要关闭证书校验。

## 为什么 RedactionEverything 显示部分离线

一句话安装启用的是当前安全链路实际需要的 HaS 与 PaddleOCR。LocateAnything 视觉定位模型约 7.3GB，不参与文本安全引用和 LiteLLM 验收，因此默认不下载。健康页可能把视觉服务标为离线，这不代表“识别 + Presidio + LiteLLM”链路失败。

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

部分字体编码会导致 RedactionEverything 判为 `pdf_scanned`。PrivacyGuard 会将每页渲染后调用本地 `/structure`，按页重建全文，再把完全相同的文本交回 HaS。页数不一致、任一页无文本、OCR 服务失败或重解析文本变化都会阻断。覆盖通过不代表字符级识别绝对准确，重要材料仍需人工抽查。

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

必须在启动 MCP 的环境中同时设置 `PRIVACYGUARD_ENABLE_MLX_ENSEMBLE=1` 和 `PRIVACYGUARD_MLX_PYTHON`（已有 MLX Python 的绝对路径），并重启 MCP/Codex。默认使用 HaS、规则和 Presidio；仅设置 Python 路径不会启用额外 MLX 实体识别。这不影响 LiteLLM 使用 MLX/Qwen3 做分析。额外识别每次需加载模型，长文档更慢；显式启用后超时或模型失败会阻断。

## 显示安全副本阻断时如何排查？

错误只显示阶段和异常类型，不暴露原值。当前 `source-preparation` 涵盖上游上传/解析/HaS、源文件结构检查、补充检测和文本复检；`semantic-review` 表示有低置信度实体需要人工确认；`text-rescan` 是文本残留检查；`output-rebuild`/`file-rescan` 是输出结构或复检未通过。旧版的 `source-inspection`、`upstream-export` 等阶段请结合历史报告排查。先用虚构样本复现，不要把真实文档内容贴进日志或远程对话。

## 为什么很短的 PDF 也会阻断？

RedactionEverything 可能把每页平均少于 100 字的文件判为扫描件。PrivacyGuard 现在会调用 CPU 兼容的 `/structure` 逐页 OCR，并校验每页非空、页码连续和总页数一致；两页扫描样本已完成真实链路验收。真正的空白页仍会阻断，混合 PDF 若不能证明全部页面都已覆盖也会阻断。`/ocr` 对应 PaddleOCR-VL，在 Mac CPU 模式下禁用不是故障。

## LiteLLM 为什么在模型已经回答后仍显示 blocked？

`risk_summary` 的回答还要通过输出质量检查：必须有三个固定分段、风险项必须附可在安全正文中逐字核对的引文，且只能使用批准的中性风险表述。付款条件与付款期限混淆、默认/隐含条款、合同效力或其他无依据后果都会在 `response-check` 阶段阻断。该检查降低已知小模型误推断，但不等于法律意见或全面正确性证明。

## 只分析会生成文件吗？TXT 能下载吗？

`privacy_process_and_ask(..., create_safe_copy=false)` 仅保存内部批准文本和短期引用，不生成文档副本；聊天只返回回答与统计。明确要求下载时设置 `true`，TXT/MD/Markdown/纯文本 EML 生成独立 `.txt`，PDF/DOCX 生成纯文本重建副本。Presidio 或 HaS 不可用、复检失败时不会调用模型。内部安全文本和上游原文仍可能持久存储，并非零落盘。

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
