# Changelog

## v0.1.4

- 修复 Windows 安装入口目录参数末尾反斜杠导致的 PowerShell 参数合并；
- Windows 测试在安装前记录应用目录，未开始安装时也能安全执行清理；
- 安装指引统一到 v0.1.4，并明确国内镜像同步状态及 Apple Silicon 限制；
- 最终离线包按系统重新验收，结果记录在安装 FAQ。
- 保留原始包不可变，Windows 另提供 r2 安装入口与独立 SHA-256 清单；处理 PowerShell 5.1 的模块继承及 UTF-8 BOM 兼容性。
- macOS 最终包和 Windows 配合 r2 的完整 smoke 均通过，国内镜像待认证后同步。

## v0.1.3

- Windows 双击入口使用 CRLF 换行；该版本仍有安装路径参数问题，推荐修复后的 v0.1.4。

## v0.1.2

- 构建器拒绝覆盖已有版本目录、Git tag 或 GitHub Release；
- Windows 停止失败或身份不一致时保留并标记 stale 进程记录，避免残留服务失去追踪；
- Windows 故障启动测试同时核对进程记录、真实进程、命令行和监听端口；
- macOS 双击安装在缺少 Python 3.11 时自动打开包内官方安装器，并在完成后继续；
- macOS 预检按实际安装目标卷计算可用磁盘空间；
- macOS 服务日志改为持久保存在应用 `logs` 目录，Windows 安装日志保证正常关闭。

## v0.1.1

- Release 资产改为不可变版本，不再覆盖 v0.1.0 文件；
- Windows 与 macOS 双击安装入口强制执行系统、架构、内存、磁盘、依赖、包完整性、SHA-256 和目录写入检查；
- Windows 停止器在结束进程前核对 PID、可执行文件路径、命令行标记和启动时间，避免 PID 复用导致误杀；
- Windows 与 macOS 启动失败时自动清理本次启动的 PrivacyGuard 服务，同时保留诊断日志；
- 安装日志写入 `logs/install.log`，服务检测结果写入 `logs/last-check.json`；
- FAQ 增加预检失败、版本混用、PID 身份不一致、启动失败清理和日志排查说明。

## v0.1.0

- 首个 standard 离线发行；
- 提供 macOS Apple Silicon 与 Windows x64 CPU 兼容运行包；
- 包含 HaS、PaddleOCR、Python 3.11 安装器和离线 wheels；
- 提供双击启动、服务健康检查和端口冲突自动切换。
