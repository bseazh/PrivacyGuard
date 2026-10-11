# 安装 FAQ

## 应该选择哪个档位？

只处理可复制文字的 PDF/DOCX 选 basic；需要扫描 PDF 选 standard；需要人脸、印章和签名定位才选 full。

## standard 离线包从哪里下载？

进入[国内平台选择页](https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/)，选择 macOS 或 Windows。系统专用页只展示该平台需要的文件（macOS 4 个、Windows 6 个）。国内镜像不可用时改用 [GitHub Release](https://github.com/bseazh/PrivacyGuard/releases/tag/offline-standard-v0.1.4)，下载后必须用 `SHA256SUMS` 校验。

不想自己操作命令时，复制[完整安装任务书](./copy-paste-agent-prompt.md)给支持终端操作的 Agent。Agent 会先说明路径、预计时间和系统修改，获得确认后再执行。

## 为什么不能只下载运行包？

运行包不包含全部模型权重。standard 还需要 HaS 文本识别模型和 PaddleOCR 模型；请下载系统专用页列出的全部文件（macOS 4 个、Windows 6 个）并放在同一目录。

## 离线版还要安装哪些依赖？

大部分依赖已经包含：构建后的前端、Python 3.11 安装器、llama.cpp、HaS、PaddleOCR，以及 Windows 约 164 个或 macOS 约 166 个 Python wheel。用户下载 macOS 4 个或 Windows 6 个发行文件。standard 离线版不需要 Node.js、Git、Homebrew、WSL、Docker、CUDA 或 NVIDIA GPU。Windows 若缺少 Microsoft Visual C++ 2015–2022 x64 Runtime，需要从微软官方下载；macOS 当前包要求 macOS 14+ Apple Silicon。详见 [环境要求](./requirements.md)。

## 安装前 Agent 应该检查什么？

Agent 应直接读取系统版本、CPU 架构、内存、目标磁盘空间、端口、Python、PowerShell/tar 和 Windows Visual C++ Runtime，不应把这些问题推给零基础用户。随后输出通过、警告和阻塞项，说明安装路径、下载量、预计时间和系统修改，再集中请求一次确认。

## 预计需要多长时间？

macOS 下载约 1.65 GiB，Windows 约 1.61 GiB。10 Mbps 通常约 27–35 分钟，50 Mbps 约 6–10 分钟，100 Mbps 约 3–6 分钟。16 GB 内存机器安装和首次启动通常再需 10–25 分钟；8 GB 机器可能需要 20–45 分钟。杀毒软件实时扫描、机械硬盘和网络抖动都会增加时间。Agent 应在下载 20–30 秒后根据实际速度更新 ETA，不能保证精确完成时刻。

## 下载卡住或中断怎么办？

不要从头重来。保留已下载文件，用支持断点续传的下载方式继续；先校验已有文件，哈希正确的不得重下。国内镜像超时、TLS 失败或持续无速度时切换 GitHub Release；GitHub 不通时保留国内镜像。不得关闭 TLS 校验，也不要求用户必须使用 VPN。

## 没有 D 盘怎么办？

Windows 向导应先询问用户，然后改用 `%USERPROFILE%\Documents\PrivacyGuard\v0.1.4`。不得因为没有 D 盘直接判定电脑不支持。

## 只有 8 GB 内存能安装吗？

可以尝试 standard，但属于最低配置：关闭浏览器大量标签和其他占内存软件，预留更长安装与 OCR 时间，并避免同时处理多份大扫描 PDF。低于 8 GB 应停止 standard 自动安装，建议换机器或使用更轻的 basic 方案。

## 端口 8000、8080 或 8082 被占用怎么办？

新版启动器会先停止自己上次记录的 PrivacyGuard 进程。若端口仍由其他软件占用，不会强行结束该软件，而是依次选择 `18000/18080/18082`、`28000`、`38000` 系列备用端口。实际地址保存在 `.run/runtime.json`（Windows）或 `.run/runtime.env`（macOS），并由启动器自动在浏览器打开。

## Windows 为什么出现 tzdata 或 colorama 找不到？

这是早期 v0.1.0 Windows wheelhouse 漏掉条件依赖导致的。当前包已同时包含应用和 OCR 所需的 `tzdata`，以及 OCR 所需的 `colorama`。请下载 v0.1.4 的完整同版本文件并校验 SHA-256。

## Windows 安装成功却出现中文 UnicodeEncodeError？

旧安装器在 CP1252 控制台打印中文导入结果会触发此错误。当前安装器已启用 Python UTF-8 并使用 ASCII 导入测试输出。若仍出现，先确认下载的是最新 runtime，并把 `logs` 和完整错误交给 Agent，不要修改系统区域设置。

## 杀毒软件或 Gatekeeper 阻止脚本怎么办？

先核对下载来源和 SHA-256。Windows 只对当前启动进程使用 `ExecutionPolicy Bypass`，不要永久降低策略；macOS 不应关闭 Gatekeeper。若系统仍拦截，由用户在系统提示中针对已校验的单个文件确认，Agent 不得全局关闭安全软件。

## Linux 可以直接使用这两个离线包吗？

不可以。当前 standard 离线发行只有 macOS Apple Silicon 和 Windows x64。Agent 检测到 Linux 后应暂停，说明需要单独制作 Linux x64/arm64 包或采用源码部署，不能拿 Windows/macOS 包强行安装。

## 安装后怎么一键启动和检测？

- Windows：双击 `Launch-PrivacyGuard.cmd`；检测用 `Check-PrivacyGuard.cmd`；停止用 `Stop-PrivacyGuard.cmd`。
- macOS：双击 `Launch-PrivacyGuard.command`；检测用 `Test-PrivacyGuard.command`；停止用 `Stop-PrivacyGuard.command`。

启动器会等待后端、HaS 和 OCR ready 后再打开浏览器。检测结果写入 `logs/last-check.json`，方便用户直接发给 Agent。

## 双击安装后显示“安装前检查未通过”怎么办？

这是新版安装门禁在保护电脑和安装结果，并非程序崩溃。先查看输出中的 `[FAIL]`：系统或架构不支持时不能强装；内存或磁盘不足时先释放资源；Windows 缺少 VC++ Runtime 时只从微软官方地址安装；缺少压缩包时把 runtime、HaS、PaddleOCR 和 `SHA256SUMS` 放回同一版本目录；哈希不一致时只重新下载失败文件；目录不可写时换到用户 Documents。所有 FAIL 清零后再双击安装。

## 为什么必须使用同一版本的四个下载文件？

从 v0.1.1 开始 Release 资产不再覆盖更新。runtime、HaS、PaddleOCR 和 `SHA256SUMS` 必须来自同一个版本目录，不能把 v0.1.0 模型包与 v0.1.4 runtime 混用。这样可以避免浏览器或 CDN 缓存旧文件造成哈希不一致。

## Windows 停止时提示“身份记录不一致”怎么办？

停止器会同时核对 PID、可执行文件路径、命令行标记和启动时间。只要任一项不一致，就不会结束该进程，以防 PID 被其他软件复用。v0.1.4 会保留记录并写入 `status: stale`，在问题解决前阻止启动第二套服务。不要手动结束不认识的系统进程，应把警告和 `.run` 目录交给 Agent 核对。

## 启动失败后会不会留下后台进程？

新版 Windows 与 macOS 启动器会在后端、HaS 或 OCR 启动失败时自动清理本次已经启动的 PrivacyGuard 进程，同时保留 `logs` 日志。修复问题后直接重新启动即可，不需要重装或重新下载模型。

## 安装日志在哪里？

Windows 和 macOS 的安装过程都会保存在 `app/logs/install.log`。运行检测后还有 `app/logs/last-check.json`，Windows 与 macOS 服务日志也统一位于 `app/logs`。排查时优先把真实错误和该目录交给 Agent。

## 为什么页面显示离线？

页面通过 `/health/services` 检查本地服务。常见原因是模型未下载、虚拟环境缺依赖、端口占用、服务启动后崩溃，或所选档位本来就没有安装该服务。

## macOS 为什么显示 OCR CPU 兼容模式？

这是预期配置。PaddleOCR 在当前 Mac 方案中使用 CPU；HaS 使用 llama.cpp/Metal，LocateAnything 可尝试 MPS。

## 离线包是否经过真实环境测试？

macOS v0.1.4 已通过本机安装、启动、就绪检测和停止；Windows 配合 r2 补充入口通过[完整测试](https://github.com/bseazh/PrivacyGuard/actions/runs/38122856318)。环境与限制见[验收记录](./validation-v0.1.4.md)。用户电脑仍须预检；本次未覆盖缺少 Python 的全新 Mac 图形安装器，也不能代表所有 Windows 10/11 配置。

## v0.1.2 / v0.1.3 的 Windows 双击安装为什么失败？

早期入口遇到换行兼容问题，随后又发现以反斜杠结尾的目录参数会导致 PowerShell 错误合并参数。v0.1.4 已包含 CRLF 和目录参数修复。不要手动修改哈希或跳过预检，应下载同版本完整文件。

## 为什么 Agent 找不到 v0.1.4 国内下载文件？

国内镜像尚未完成同步确认；请直接使用 GitHub Release，不能将旧版本模型与新 runtime 混用。草稿 Release 也不能作为普通用户下载入口。

## 文件已校验通过，Windows 安装入口为什么仍报 SHA-256 mismatch？

PowerShell 5.1 如果继承了 PowerShell 7 的 PSModulePath，可能加载不兼容模块，使 Get-FileHash 读取失败；旧预检把读取失败误报为哈希不匹配。使用同 Release 补充的 `Install-PrivacyGuard-v0.1.4-r2.cmd`（并用 `INSTALLER-R2-SHA256SUMS` 校验），它隔离模块路径并规范化目录后运行强制预检。无需重下已校验通过的三个压缩包，禁止跳过校验。

## Windows 安装时出现乱码、Unexpected token 或 Missing closing brace？

Windows PowerShell 5.1 按本地代码页读取没有 BOM 的脚本，中文可能被误解析。r2 安装入口会将解压后的 PowerShell 脚本规范为 UTF-8 BOM，再执行安装。该操作只调整文本编码，不修改压缩包与原 SHA256SUMS。

## 启动时报 Errno 10048，但刚才端口检查没有发现占用？

端口检查与实际绑定之间，其他程序也可能刚好启动并占用同一端口。保留 app.err.log，待对方程序稳定监听后再运行启动入口，让启动器选择备用端口；不要结束不认识的进程。自动测试应确认模拟占用进程已监听，不能只固定等待两秒。

## 为什么不提供一个脚本把所有模型全部下载？

模型体积、许可证和硬件要求不同。向所有用户默认下载 full 模型会浪费空间，也可能违反使用目的对应的模型许可。向导会先问能力和授权，再下载必要部分。

## 安装完成为什么还要跑虚构样本？

服务在线只说明进程可访问，不代表识别、坐标映射和 PDF 安全删除都正常。验收必须覆盖一次完整导出。

完整步骤和反馈模板见[安装与验收测试方案](./acceptance-test.md)。

## 可以使用真实合同测试安装吗？

不建议。安装验收应使用仓库提供或单独生成的虚构样本，确认本地隐私边界后再处理真实材料。
