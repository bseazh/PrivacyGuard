# 本机管理员后台：已运行的用户与 Channel 管控

日期：2026-11-04。状态：G1 用户/通道授权与 G2 基础后台已实现，仍是单组织、本机开发版。现有 MCP 配置未修改；不宣称 WorkBuddy/Codex 原生模型协议已经验收。

## 打开与登录

后台地址：`http://127.0.0.1:8787/admin`。

当前本机状态目录是 `local-config/gateway-dev-20261104/`。管理员密码保存在该目录的 `admin-login.txt`，不是网关 API Key；登录页支持选择此文件自动填入并登录。密码不打印到日志、不写入 Git、不放浏览器 localStorage。管理员会话 1 小时到期，退出立即撤销服务端会话。

首次初始化管理员（每个状态目录仅一次，已有管理员拒绝覆盖）：

```bash
.venv/bin/python -m privacyguard.gateway init-admin --directory local-config/gateway-dev-20261104
```

后台运行与停止：

```bash
.venv/bin/python scripts/manage_gateway.py start --directory local-config/gateway-dev-20261104
.venv/bin/python scripts/manage_gateway.py stop --directory local-config/gateway-dev-20261104
```

启动器后台运行服务，端口占用时拒绝启动，不终止未知进程；停止时验证记录的 PID、启动时间和命令行，身份不符保留记录并停止操作。日志位于该私有目录的 `gateway.log`。当前未配置开机自启。

## 已实现的完整操作

1. 登录后查看用户、通道、Key、调用审计与固定上游。
2. 创建用户；支持启用/禁用。
3. 创建 Channel，指定名称和客户端模型别名。当前上游固定为本机模型，策略固定为 `policy-1`。新 Channel 默认禁用，需要显式启用。
4. 选择用户及 Channel，授予访问权限。
5. 发放 Key：必须已授权且用户/Channel 均启用；Key 有效期 24 小时，明文只在创建响应中出现，随后列表不可读回。
6. 下载接入 JSON，包含 Base URL、该 Channel 的模型别名和个人 Key。文件含密钥，请保存在本机，不上传 GitHub。
7. 点“用虚构材料测试此 Key”，真实调用 HaS/Presidio → LiteLLM → 本机 Qwen3，只显示通过/阻断和实体数量。
8. 查看调用审计及管理操作记录；撤销 Key、撤销授权、禁用用户或禁用 Channel 均立即影响后续请求。发送前与回答前也复核权限，已外发的数据无法撤回。

同一用户可获得多个 Channel 的授权，但每个 Key 只绑定一个 Channel。客户端不能通过改 model 或提交 channel_id 越权切换。后台和数据面均做服务端校验。

## 登录与数据保护

- 管理员随机密码使用带盐 scrypt 保存；与用户模型调用 Key 分离。不存在默认固定密码。
- 管理会话使用 HttpOnly、SameSite=Strict Cookie，本机 HTTP 模式不设置 Secure；仅允许本机服务地址。管理 POST 必须同源 Origin + CSRF Token。
- 每分钟最多 5 次登录尝试；管理输入限制大小/字段。页面使用 textContent，不将用户显示名作为 HTML 执行；CSP 限制脚本、样式和 iframe。
- 数据库迁移至版本 2，保留原 Key、原默认通道和调用记录；重启不会将已禁用通道自动启用。现有 Channel 的模型配置保持其创建快照，不随 config.json 自动覆盖。
- Key 列表不返回 Key 明文或哈希。审计只记录标识、动作、原因码和计数；后台操作与相应审计同一事务提交。
- 数据访问按组织字段约束并测试跨组织拒绝；当前只有本机组织和一个管理员入口，尚无多组织开户、SSO、操作员/审计员角色界面或企业生产部署保证。

## 本轮验收

```bash
.venv/bin/python -m pytest -q tests/test_gateway.py tests/test_gateway_admin.py tests/test_privacyguard_core.py tests/test_secure_ask.py
node scripts/gateway_admin_browser.mjs local-config/gateway-dev-20261104
```

Python 结果：72 passed，12 subtests passed。覆盖迁移后重开、授权前拒绝发 Key、未启用通道拒绝发 Key、跨组织拒绝、模型越权、CSRF/Origin、登录限流、退出、过期、禁用用户/通道、途中失权不返回回答。

浏览器使用独立无头 Chrome，不读取个人浏览器资料：登录 → 建用户/通道 → 显式启用 → 授权 → 发 Key → 真实模型调用 → 撤销授权 → 原 Key 返回 401 → 撤销测试 Key并禁用测试资源 → 退出。全部通过，无页面 JavaScript 异常。测试中的虚构邮箱/手机号共脱敏 2 项，未展示原文回答。截图为 `test-results/gateway-admin.png`，已隐藏明文 Key。

浏览器测试要求本机 Chrome 和 `app/node_modules/playwright-core`；当前脚本是 macOS 开发验收，不是 Windows 测试证明。

## 尚未实现

动态上游管理、策略编辑/单元测试/版本发布回滚、操作员/审计员分权、映射 Vault 与授权回填、生产多组织部署、流式/tools/Responses/多模态和 WorkBuddy/Codex 原生模型接入。不能将基础后台等同于 G2 全部完成。

下一步优先增加策略草稿、测试及显式版本启用，再补协议兼容。当前可直接用后台做用户/Channel 权限和真实模型烟雾验收。
