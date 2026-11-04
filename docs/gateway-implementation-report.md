# Gateway 本机原型实施与验收

关联 Issue #1；本次仅推进 G1 子集，不关闭 Epic。

之前仅有 PrivacyGuard MCP 内部受控调用；现在新增独立本机 HTTP 入口，SDK 客户端可通过个人网关 Key 发送纯文本请求，经 HaS/Presidio/规则假名化与复检后，由 LiteLLM 发给本机模型，回答再次检查后返回。

- 新增 `privacyguard/gateway/`：SQLite Key 校验/到期/撤销、最小审计、固定配置版本、单 Channel、模型白名单、请求与回答策略及限额。
- 新增 `scripts/gateway_smoke.py` 和网关测试；更新 README、TODO、可选依赖与运行说明。
- 本地地址 `http://127.0.0.1:8787/v1`；模型别名 `privacyguard-local`。真实客户端凭据只保存在忽略目录，未提交。

验证（2026-11-04）：

```bash
.venv/bin/python -m pytest -q tests/test_gateway.py tests/test_privacyguard_core.py tests/test_secure_ask.py
```

结果：62 passed，12 subtests passed。包含真实 HTTP 记录型上游验证：私钥阻断时零请求，允许请求中无虚构邮箱/手机号原值；亦覆盖回答漏敏、依赖错误、审计异常、途中撤销、模型和字段限制。

官方 OpenAI Python SDK 的本机烟雾测试通过：模型列表、私钥阻断、流式拒绝、HaS/Presidio → LiteLLM → Qwen3 真实往返。虚构输入 EMAIL/PHONE 共 2 项实体被替换，结果 approved。仅检查隐私链路，不宣称法律分析质量合格。

联调中修复了本机运行状态：RedactionEverything 旧进程引用迁移前路径导致上传 500，已按新路径启动；重装缺失文件的 Presidio 指定版本以恢复回归测试。这些是本机环境操作，未修改或提交外部资产仓库。

限制：仅本机单用户/单 Channel，24 小时 Key、固定预设及回环上游，非流式，回答最多 512 token；无多租户后台、动态策略、回填、tools/Responses/多模态。拒绝客户端预置占位符，因此现有 MCP 路由不变。WorkBuddy/Codex 原生客户端尚未验收。默认安装器和国内服务器不更新，原型不应部署为企业生产网关。

下一步先完成 G1 的组织/用户/Channel 权限模型，再实现 G2 管理后台。运行及停止、撤销方法见 [本机运行指南](gateway-local-run.md)。回滚本次功能可停止 8787 网关并切回 main；不删除本地状态或结束其他服务。
