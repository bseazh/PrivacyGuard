# Windows 安装


> v0.1.4 国内镜像尚未确认同步，当前请使用 GitHub Release；不要使用草稿链接或混用版本。macOS 包只支持 macOS 14+ Apple Silicon，Intel Mac 不适配。
## standard 离线安装入口

- [Windows x64 专用下载页](https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/windows.html)
- [GitHub Release 备用源](https://github.com/bseazh/PrivacyGuard/releases/tag/offline-standard-v0.1.4)
- [复制给 Agent 的完整安装任务书](./copy-paste-agent-prompt.md)

standard 离线包采用 Windows x64 CPU 兼容模式，不要求 WSL 或 NVIDIA GPU。只有源码安装和 full 视觉方案才需要继续参考下方 WSL/GPU 配置。

离线版要求 Windows 10 22H2/Windows 11 x64、PowerShell 5.1+、系统 `tar.exe`、至少 10 GB 可用磁盘（建议 15 GB）和 8 GB 内存（建议 16 GB）。运行 `scripts\check-offline-windows.ps1` 可只读检查。Python 3.11 安装器已包含；若缺少 Microsoft Visual C++ 2015–2022 x64 Runtime，只能从[微软官方地址](https://aka.ms/vs/17/release/vc_redist.x64.exe)下载。

v0.1.4 Windows 需额外下载同 Release 的 `Install-PrivacyGuard-v0.1.4-r2.cmd` 与 `INSTALLER-R2-SHA256SUMS`，核对 SHA-256 后将 cmd 放入 app。解压后按顺序双击：`Install-PrivacyGuard-v0.1.4-r2.cmd` → `Launch-PrivacyGuard.cmd`。请勿使用 runtime 内旧安装入口。检测使用 `Check-PrivacyGuard.cmd`，停止使用 `Stop-PrivacyGuard.cmd`。

## 源码安装 / full 视觉方案

## 1. 先运行检查

在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\doctor-windows.ps1 -Profile standard
```

## 2. 基础环境

```powershell
winget install Git.Git
winget install OpenJS.NodeJS.LTS
winget install Python.Python.3.11
wsl --install
```

安装 WSL 后通常需要重启。standard/full 推荐在 WSL 中运行模型服务，Windows 侧运行前端和 FastAPI 编排。

## 3. NVIDIA 检查

```powershell
nvidia-smi
wsl nvidia-smi
```

两个命令都应能看到 GPU。full 推荐至少 16GB 显存；显存不足时不要允许关键模型静默回退 CPU。

## 4. 安装和启动

上游 Windows/WSL 环境涉及 Paddle 与 vLLM 两套相互冲突的依赖，必须使用独立虚拟环境。详细命令保留在根目录 README 的“WSL 模型服务环境准备”。完成后：

```powershell
npm ci
npm run dev
```

看到 `[dev] ready: http://localhost:3000` 后仍需检查 `http://127.0.0.1:8000/health/services`。

## 5. 常见阻塞

- `wsl --status` 失败：先启用虚拟化与 WSL2；
- Windows 能看到 GPU、WSL 看不到：更新 NVIDIA Windows 驱动和 WSL；
- 端口占用：先确认占用进程，不要盲目结束系统服务；
- PowerShell 禁止脚本：仅对当前命令使用 `-ExecutionPolicy Bypass`，不要永久关闭安全策略。
