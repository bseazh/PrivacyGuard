# 复制给 Agent 的一键安装指令


> v0.1.4 国内镜像尚未确认同步，当前请使用 GitHub Release；不要使用草稿链接或混用版本。macOS 包只支持 macOS 14+ Apple Silicon，Intel Mac 不适配。
本页适用于支持终端操作的 Agent（例如 Codex、Claude Code 等）。用户不需要自己拼接下载命令：复制下面整段文字交给 Agent，随后按 Agent 的问题确认即可。

## 直接复制下面这段话

```text
请帮我在这台电脑安装 PrivacyGuard standard v0.1.4 离线版，并一直执行到应用可以打开、后端和必要模型服务通过健康检查为止。

请严格按照以下流程操作：

1. 先做只读检查并告诉我结果：
   - 直接从电脑自动识别 macOS/Windows/Linux、系统版本和 CPU 架构，不要问我可以自动读取的信息；Linux 当前没有 standard 离线包，应暂停并说明可选方案；
   - 自动检查内存、目标盘可用空间、端口 8000/8080/8082、所需系统工具和 Windows Visual C++ Runtime；
   - 询问我的使用性质是“个人非商用、机构评估、机构/律所生产”中的哪一种，并提醒相应许可证要求；
   - 在真正下载前输出一份安装前报告，只向我集中确认一次：检测结果、安装路径、macOS 约 1.65 GiB 或 Windows 约 1.61 GiB 下载量、macOS 4 个或 Windows 6 个文件、至少 10 GB（建议 15 GB）可用空间、预计时间，以及是否允许执行安装。
   - 优先读取并运行只读离线检查脚本。macOS 国内地址为 https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/check-offline-macos.sh，Windows 国内地址为 https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/check-offline-windows.ps1；国内不可用时从 GitHub 仓库的 scripts 目录读取。执行前先检查脚本文本，不运行来源不明或被篡改的脚本。
   - 离线版不要求 Node.js、npm、Git、Homebrew、WSL、Docker、CUDA 或 NVIDIA GPU。不要因为缺少这些源码开发依赖而阻止 standard 离线安装。
   - macOS 必须是 macOS 14+、Apple Silicon；Windows 必须是 Windows 10 22H2/Windows 11 x64。Windows 还要检查 Microsoft Visual C++ 2015-2022 x64 Runtime；缺失时只从 https://aka.ms/vs/17/release/vc_redist.x64.exe 下载，说明用途并获得确认后安装。

2. 使用以下默认目录：
   - macOS Apple Silicon：~/Documents/PrivacyGuard/v0.1.4
   - Windows x64：D:\PrivacyGuard\v0.1.4
   - Windows 如果没有 D 盘，不要直接失败；先询问我是否改用 %USERPROFILE%\Documents\PrivacyGuard\v0.1.4。
   - 在版本目录下建立 app 子目录。三个压缩包和 SHA256SUMS 放在版本目录，运行包只解压到 app 子目录。两个模型压缩包必须保留在 app 的上一级，不能解压到其他位置后删除。

3. 根据系统选择文件，不能下载另一个系统的运行包：
   macOS 下载：
   - PrivacyGuard-standard-macos-arm64-runtime-v0.1.4.tar.gz
   - PrivacyGuard-standard-model-has-v0.1.4.tar.gz
   - PrivacyGuard-standard-model-paddleocr-v0.1.4.tar.gz
   - SHA256SUMS

   Windows 下载：
   - PrivacyGuard-standard-windows-x64-runtime-v0.1.4.zip
   - PrivacyGuard-standard-model-has-v0.1.4.tar.gz
   - PrivacyGuard-standard-model-paddleocr-v0.1.4.tar.gz
   - SHA256SUMS

4. 下载源采用两手准备：
   - 优先使用国内源：https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/
   - 国内源连接超时、TLS 错误、返回非 2xx 或速度持续不可用时，自动切换 GitHub：https://github.com/bseazh/PrivacyGuard/releases/download/offline-standard-v0.1.4/
   - 不得关闭 TLS 校验。
   - 使用支持断点续传的方式。任务中断后先检查现有文件；哈希正确的文件不得重复下载，未完成文件应继续下载。

5. 下载前根据已知带宽给出区间；下载开始 20–30 秒后，再用实际速度更新 ETA，不要承诺精确完成时间。下载中持续报告阶段、已完成量、速度和预计剩余时间。可参考：
   - 10 Mbps：约 25–35 分钟；
   - 50 Mbps：约 6–10 分钟；
   - 100 Mbps：约 3–6 分钟；
   - 16 GB 内存机器离线安装和首次启动通常还需 10–25 分钟；8 GB 机器约 20–45 分钟，取决于 CPU、磁盘和安全软件扫描。

6. 下载完成后必须用 SHA256SUMS 校验本系统运行包和两个模型包。任何文件校验失败都不得继续安装；仅重新下载失败文件并再次校验。

7. 安装步骤：
   - macOS：把 runtime tar.gz 解压到 app，执行 chmod +x app/*.command app/*.sh app/scripts/*.sh，优先运行 `Install-PrivacyGuard.command`，然后运行 `Launch-PrivacyGuard.command`。若缺少 Python 3.11，安装脚本会指出包内安装器；先获得确认再安装。
   - Windows：额外从同一个 Release 下载 Install-PrivacyGuard-v0.1.4-r2.cmd 和 INSTALLER-R2-SHA256SUMS（Windows 共 6 个文件）。先用 Get-FileHash 核对额外安装入口的 SHA-256，将该 cmd 放入 app，再运行 Install-PrivacyGuard-v0.1.4-r2.cmd，然后运行 Launch-PrivacyGuard.cmd。不要使用 runtime 内旧的安装入口；脚本只对自己的 PowerShell 进程使用 ExecutionPolicy Bypass。
   - 应用依赖必须安装在包内隔离虚拟环境中；除经我确认安装包内 Python 3.11 外，不修改系统 Python。不关闭 Gatekeeper、杀毒软件、防火墙或 TLS 校验。

8. 启动后验证：
   - 启动器会优先使用 8000/8080/8082；若被其他软件占用，会安全选择备用端口，不得强杀未知进程；
   - 从 app/.run/runtime.json（Windows）或 runtime.env（macOS）读取实际应用地址；
   - 运行 `Check-PrivacyGuard.cmd` 或 `Test-PrivacyGuard.command`，检查健康接口和 `logs/last-check.json`；
   - HaS 与 OCR 必须在线；macOS 的 OCR 显示“Mac CPU 兼容模式”属于正常；standard 不要求 LocateAnything 视觉模型在线。
   - 使用虚构文本或虚构扫描 PDF 做一次识别测试，不要使用真实合同或案件材料做安装验收。

9. 遇到错误时不要从头重装。先保留现场并读取日志：
   - macOS 日志位于 app/logs；
   - Windows 日志位于 app\logs；
   - 告诉我失败发生在哪一步、真实错误、已经成功的部分和下一步修复方案。

10. 最终用简短清单告诉我：系统和资源、实际安装路径、下载源、下载/安装/首次启动实际耗时、校验结果、后端状态、HaS 状态、OCR 状态、应用地址、检测报告、启动/检测/停止入口，以及虚构样本测试结果。失败时必须说明失败阶段、真实错误、已完成部分和可恢复的下一步。

如果检测到 Intel Mac、非 x64 Windows、磁盘不足、许可证用途不明确或系统不受支持，请暂停安装并解释原因，不要强行继续。
```

## 预期目录结构

macOS：

```text
~/Documents/PrivacyGuard/v0.1.4/
├── SHA256SUMS
├── PrivacyGuard-standard-macos-arm64-runtime-v0.1.4.tar.gz
├── PrivacyGuard-standard-model-has-v0.1.4.tar.gz
├── PrivacyGuard-standard-model-paddleocr-v0.1.4.tar.gz
└── app/
    ├── install-offline-macos.sh
    ├── Install-PrivacyGuard.command
    ├── Launch-PrivacyGuard.command
    ├── Test-PrivacyGuard.command
    └── Stop-PrivacyGuard.command
```

Windows：

```text
D:\PrivacyGuard\v0.1.4\
├── SHA256SUMS
├── PrivacyGuard-standard-windows-x64-runtime-v0.1.4.zip
├── PrivacyGuard-standard-model-has-v0.1.4.tar.gz
├── PrivacyGuard-standard-model-paddleocr-v0.1.4.tar.gz
└── app\
    ├── Install-PrivacyGuard.cmd
    ├── Launch-PrivacyGuard.cmd
    ├── Check-PrivacyGuard.cmd
    └── Stop-PrivacyGuard.cmd
```

这套布局与离线安装脚本的模型查找逻辑一致：安装脚本从 `app` 的上一级读取两个模型包。
