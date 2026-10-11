# 新手安装入口


> v0.1.4 国内镜像尚未确认同步，当前请使用 GitHub Release；不要使用草稿链接或混用版本。macOS 包只支持 macOS 14+ Apple Silicon，Intel Mac 不适配。
本目录面向第一次安装的用户。建议顺序是：**回答问题 → 环境检查 → 选择档位 → 安装 → 启动 → 验收**。

如果希望由 Agent 完成整个过程，直接复制[一键安装任务书](./copy-paste-agent-prompt.md)中的文字。默认安装路径为 macOS 的 `~/Documents/PrivacyGuard/v0.1.4` 或 Windows 的 `D:\PrivacyGuard\v0.1.4`，并自动在国内镜像与 GitHub 之间切换。

## 第一步：选择使用档位

| 档位 | 主要能力 | 推荐环境 | 预计本地空间 |
|---|---|---|---:|
| `basic` | TXT、DOCX、文本型 PDF、规则与基础处理 | 普通 Mac/Windows | 10GB |
| `standard` | basic + HaS 语义识别 + OCR/扫描 PDF | macOS 14+ Apple Silicon；Windows 10 22H2/11 x64 | 15GB（建议 20GB） |
| `full` | standard + 人脸、印章、签名等视觉定位 | NVIDIA 16GB 显存推荐；Mac MPS 属兼容模式 | 35GB |

不确定时选择 `standard`。只处理有文字层的合同 PDF，可先选 `basic`。

## 第二步：先检查，不要直接安装

macOS：

```bash
chmod +x scripts/doctor-macos.sh
./scripts/doctor-macos.sh standard
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\doctor-windows.ps1 -Profile standard
```

检查脚本只读取系统、硬件、端口和文件状态，不修改系统。

## 第三步：阅读对应系统指南

- [macOS](./macos.md)
- [Windows](./windows.md)
- [模型权重](./models.md)
- [standard 离线包](./offline-standard.md)
- [Agent 安装向导](./agent-guide.md)
- [可直接复制给 Agent 的安装任务书](./copy-paste-agent-prompt.md)
- [FAQ](./faq.md)
- [安装与验收测试方案](./acceptance-test.md)

如选择 standard 离线安装，可直接进入[国内下载页选择 macOS 或 Windows](https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/)。国内镜像不可用时使用 [GitHub Release](https://github.com/bseazh/PrivacyGuard/releases/tag/offline-standard-v0.1.4)。

## 安装完成标准

不能只以“网页能打开”为准，必须同时满足：

1. 后端 `/health` 可访问；
2. `/health/services` 中所选档位的必要服务在线；
3. 虚构 TXT/DOCX 可以识别；
4. 文本 PDF 能导出假名化结果；
5. 导出 PDF 中原敏感文字无法再搜索；
6. standard/full 档位能处理至少一份扫描 PDF；
7. 日志中没有关键模型静默回退或持续崩溃。

安装后无需输入命令：Windows 双击 `Launch-PrivacyGuard.cmd`，macOS 双击 `Launch-PrivacyGuard.command`。检测与停止也有同目录双击入口。默认端口被其他软件占用时，启动器会选择备用端口并自动打开实际地址，不会结束未知进程。

> 本项目采用 Personal Use License。公司、律所、学校、政府、团队及生产用途可能需要商业许可；LocateAnything 权重为非商用许可，PyMuPDF 还涉及 AGPL/商业双许可。
