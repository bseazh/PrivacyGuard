# Agent 新手安装向导


> v0.1.4 国内镜像尚未确认同步，当前请使用 GitHub Release；不要使用草稿链接或混用版本。macOS 包只支持 macOS 14+ Apple Silicon，Intel Mac 不适配。
本文件提供给能运行终端命令的 Agent。Agent 不得一上来就执行安装，必须先完成问答和只读检查。

面向最终用户的整段可复制任务书见 [copy-paste-agent-prompt.md](./copy-paste-agent-prompt.md)。执行该任务书时，本文件仍是必须遵守的安全与验收规范。

## 必须先检测和询问的内容

Agent 能操作终端时，系统、架构、内存、磁盘、端口、Python 和网络连通性必须由 Agent 读取，不得反问用户这些可以自动获取的信息。只有使用性质、安装位置变更和系统级修改许可需要询问用户。

1. 自动检测：系统、版本、CPU 架构、内存、目标盘可用空间、端口、PowerShell/Python、Visual C++ Runtime（Windows）及下载源连通性；
2. 询问使用性质：个人非商用、机构评估、机构/律所生产；
3. 询问能力：文本、扫描 PDF/OCR，还是还需要人脸、印章、签名；
4. 给出推荐安装路径、需要下载的 4 个文件、实际预计下载量、预计时间和会发生的系统修改；
5. 集中取得一次安装确认。执行中只有新增系统级修改或变更安装盘时才再次询问。

若用户选择机构生产、付费交付或商业集成，先展示许可证风险并请求用户确认已取得所需授权。不得自行替用户判断授权有效。

## standard 离线包下载源选择

1. 必须先确认用户使用 macOS 还是 Windows，不得先给出一整页混合文件让用户自行判断；
2. macOS 用户给出 `https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/macos.html`，Windows 用户给出 `https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/windows.html`；尚未确认系统时才给平台选择页 `https://privacyguard.snorlaxden.fun/offline-standard-v0.1.4/`；
3. 先探测对应国内页面；若连接超时、TLS 错误或返回非 2xx，则改用 GitHub Release：`https://github.com/bseazh/PrivacyGuard/releases/tag/offline-standard-v0.1.4`；
4. macOS 下载 macOS runtime、HaS、PaddleOCR 和 `SHA256SUMS`；Windows 下载 Windows runtime、HaS、PaddleOCR 和 `SHA256SUMS`；
5. 支持断点续传，但不得通过关闭 TLS 校验解决网络问题；
6. 下载完成后必须校验 SHA-256，失败的文件应删除并重新下载。

## 执行流程

1. 读取本文件、[requirements.md](./requirements.md) 和对应系统指南；
2. 运行 `doctor-macos.sh` 或 `doctor-windows.ps1`；
3. 根据答案推荐 `basic/standard/full`，说明缺失能力；
4. 安装前输出“安装前报告”：检测值、通过/警告/阻塞、4 个下载文件、macOS 约 1.65 GiB 或 Windows 约 1.61 GiB、166/164 个随包 wheels、至少 10 GB（建议 15 GB）空间和系统修改；离线版不要误报 Node、Git、Homebrew、WSL、Docker 或 CUDA 为必需依赖；
5. 根据用户提供的带宽或下载开始后 20–30 秒的实际速度计算 ETA，并说明它是区间而非承诺；下载阶段持续显示已完成量、速度、剩余时间和当前来源；
6. 创建隔离虚拟环境，不污染系统 Python；每个阶段显示 `[当前步骤/总步骤]`，失败后保留已下载文件和日志；
7. 下载模型时记录来源和校验值；哈希正确的文件不得重复下载；
8. 安装后使用双击入口启动，读取启动器记录的实际端口，不假定一定为 8000；
9. 运行平台检测脚本，检查 `/health`、`/health/services`、HaS reachable、OCR reachable + ready；
10. 使用虚构样本完成文本识别和一份扫描 PDF 验收；如测试自然假名 PDF，还要确认原敏感文字无法搜索；
11. 按 [验收测试方案](./acceptance-test.md)输出测试反馈，包含成功、警告、失败、实际耗时、应用地址、日志和恢复建议。

## 端口处理原则

- 默认使用应用 `8000`、HaS `8080`、OCR `8082`；
- 重启时只停止 `.run` 中记录的 PrivacyGuard 进程或固定 launchd job；
- 如果端口被其他软件占用，不得强杀未知进程，自动选择 `18000/18080/18082`，再依次尝试 `28000`、`38000` 系列；
- 实际地址保存在 `.run/runtime.json`（Windows）或 `.run/runtime.env`（macOS）；Agent 和检测脚本必须读取这里的地址。

## 禁止事项

- 不得上传用户文件、数据库、日志、权重或输出到 Git；
- 不得关闭 TLS 校验、Gatekeeper、杀毒软件或系统安全策略；
- 不得把“网页打开”当成安装成功；
- 不得把 CPU 回退的重型模型报告为正常 GPU 运行；
- 不得在用户未确认前下载 full 档位的大模型；
- 不得处理真实案件材料作为安装测试。

## Agent 最终验收模板

```text
安装档位：standard
系统：macOS / Apple Silicon / 16GB
安装路径：...
下载源：国内 / GitHub
下载量与实际耗时：...
安装与首次启动耗时：...
SHA-256：通过
后端：在线
HaS：在线
OCR：在线（Mac CPU 兼容模式）
视觉模型：未安装（不影响本档位）
实际应用地址：http://127.0.0.1:<实际端口>
虚构样本识别：通过
假名化 PDF：通过
原文残留搜索：通过
检测报告：.../logs/last-check.json
启动命令：...
停止命令：...
```
