# v0.1.4 安装验收记录

验收日期：2026-10-11。正式下载：https://github.com/bseazh/PrivacyGuard/releases/tag/offline-standard-v0.1.4

## 发行文件

macOS 下载 runtime、HaS、PaddleOCR 与 SHA256SUMS，共 4 个文件。

Windows 下载 runtime、HaS、PaddleOCR 与 SHA256SUMS，并额外下载 Install-PrivacyGuard-v0.1.4-r2.cmd、INSTALLER-R2-SHA256SUMS，共 6 个文件。核对两份清单后将 r2 cmd 放入 app，双击安装；不要使用原 runtime 的旧安装入口或早期补充入口。安装后使用原 Launch、Check、Stop 入口。

四个压缩包的 GitHub 资产 SHA-256 与本地 SHA256SUMS 一致。原包及原清单未覆盖；Windows 补充入口使用独立名称和校验清单。

## macOS：通过

环境：macOS 14.8.1、Apple Silicon arm64、16 GB 内存，已有 Python 3.11。

在独立目录 /private/tmp/privacyguard-mac-v014.UEv7dW/app 解压最终 runtime，执行真实 Install-PrivacyGuard.command，强制预检及离线依赖安装完成。安装器报告约 1 分钟（本机已有 Python；不是新机器安装耗时承诺）。

启动器及 Test-PrivacyGuard.command 验收结果：后端 online、HaS online、OCR online 且 ready=true，应用地址 http://127.0.0.1:8000。日志在 app/logs，检测报告 last-check.json。

执行 Stop-PrivacyGuard.command 后，复查 launchctl 无 PrivacyGuard 服务记录，8000/8080/8082 无监听。本次最终包没有在缺少 Python 的全新 Mac 上走图形安装器，也未验证 Finder 下载隔离提示。

只支持 macOS 14+ Apple Silicon；Intel Mac 不适配。

## Windows：通过

环境：GitHub 托管 Windows Server 2025 x64；不是所有 Windows 10/11 用户机器的兼容性保证。

完整运行：https://github.com/bseazh/PrivacyGuard/actions/runs/38122127746

总耗时：3 分 10 秒。以下步骤均通过：预检、Release 下载、SHA-256、真实 r2 cmd 离线安装、模型解压、端口冲突切换、后端/HaS/OCR 就绪、停止、PID 身份不一致保留 stale 记录、失败启动清理真实进程及监听端口、日志上传。

发现并处理的问题：目录参数末尾反斜杠；PowerShell 7 模块路径污染 Windows PowerShell 5.1；无 BOM 中文脚本被 PowerShell 5.1 错误解析。r2 入口规范化目录、隔离模块路径并统一解压后 ps1 为 UTF-8 BOM。测试中未跳过完整性检查。

## 国内镜像：待部署

https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/ 当前检查返回 HTTP 404。SSH 默认 22 端口以本机现有密钥连接 ubuntu@134.175.154.244 返回 Permission denied (publickey,password)。没有上传或修改服务器。

待上传目标为 /home/ubuntu/Project/Documents/PrivacyGuard/offline-standard-v0.1.4/，实际 Web 映射应在取得有效 SSH 认证后确认。部署页面已准备在 deploy/download-site/offline-standard-v0.1.4/，需与发行文件一起上传并校验。

## 使用边界

此验收覆盖安装及服务生命周期，不替代一次虚构文档的识别、脱敏和导出验收。下载时间按实测速度动态估计，磁盘、内存与管理员授权仍需每台电脑预检。
