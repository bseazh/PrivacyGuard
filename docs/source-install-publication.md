# 源码安装入口与发布记录

日期：2026-10-18。本次不制作 DMG，不向 GitHub Release 上传模型。

## 分发边界

- GitHub：代码、安装脚本、MCP 配置生成器、Skill、README/FAQ、无凭据 SVG 示意图。
- 源码选择：`config/source-release.json` 指向固定 Git 提交及该提交源码 tar.gz 的 SHA-256，下载后必须匹配才解压。
- 国内服务器：`https://privacyguard.snorlaxden.fun/v0.1.5/` 下的 RedactionEverything 源码、Qwen3、HaS、PaddleOCR 独立组件。保持原文件与哈希，不覆盖旧组件。
- 新安装器标记：`source-v0.1.6`。旧非空目标目录拒绝覆盖；旧版本升级迁移本次未实现。
- 本机生成配置：`local-config/workbuddy-mcp.json`（已忽略），含本机绝对路径；不会复制现有 WorkBuddy 凭据进仓库。

## 本轮验证

65 项定向测试通过（含配置保留、备份、重复安装幂等和同名冲突拒绝）；bash 语法检查通过。Apple Silicon 16GB 当前设备的安装预检通过，目标分区有充足空间，Python 3.11 和编译工具存在。生成的 MCP 命令及模型路径存在，配置权限为 0600，未修改用户正在使用的 WorkBuddy 配置。

国内四组件 HTTPS HEAD 均为 200；下载约 540KB 的 RedactionEverything 源码重新校验，匹配既有 SHA-256。大模型未在本轮重复下载 4GB。既有 OCR/MCP/真实模型端到端验收见 [质量验收](ocr-and-quality-acceptance.md)。新增安装器仍需在全新用户环境完成依赖安装验收，不能将现有虚拟环境的成功当作新机安装证明。

## 国内服务器同步

地址 `134.175.154.244`，账号 `ubuntu`。公钥认证失败后，用户提供的密码认证成功。Caddy 已确认站点根目录为 `/home/ubuntu/Project/Documents/PrivacyGuard`，无需改动代理或重启服务。

顶层 install.sh、下载页、latest.json 同步本仓库；旧文件备份到 `.deploy-20261018`。固定提交源码及发布清单位于 `source-v0.1.6/`，源码 SHA-256 与 GitHub codeload 完整提交地址一致。安装器从国内优先读取清单和源码，GitHub 备用。已有 v0.1.5 模型和校验清单不覆盖，无需重传模型。密码不写入仓库或脚本。

## 用户验收

安装器执行 MCP smoke、真实文件/模型测试、OCR 页覆盖及回答质量测试后才报告核心链路完成。WorkBuddy 要再安全合并 MCP、重启应用、发现六工具，并按 [WorkBuddy 指南](workbuddy.md) 用虚构材料实际调用。自然语言触发和宿主附件读取仍是协作边界，不作强制流量拦截保证。
