# 可编辑策略、测试后发布与 Trace 验证

日期：2026-11-04。本轮实现范围是本机单管理员网关，见 README 的流程图。回填、多模型、流式/tools/Responses 和原生客户端兼容继续后置；不修改宿主 Codex/WorkBuddy 配置。

## 实际如何操作

1. 打开 `http://127.0.0.1:8787/admin`，使用本机管理员密码登录。
2. 进入“策略编辑、测试与发布”。设置默认动作或类型覆盖，例如请求 `EMAIL=BLOCK`，其他请求仍 `REDACT`；回答默认 `BLOCK`，也可按类型选择 `REDACT` 后复检。
3. 点击“保存草稿”。当前组织只有一份共享草稿；保存立即清除旧测试结果，但不改变任何 Channel。并发编辑以修订号校验，过期页面不能覆盖新修改。
4. 点击“测试已保存草稿”。当前 45 个固定虚构断言包括格式正反例、所有可编辑类型的请求/回答动作、私钥与低置信度实体阻断。动作测试调用线上同一 `Protection` 实现；识别器用虚构受控结果，不调用模型。
5. 全部通过后点击“发布已测试版本”。测试绑定草稿修订、内容摘要和测试套件版本；测试后再修改必须重测。测试失败/崩溃禁止发布。版本 ID 为 `pv-` 加配置与引擎版本的完整 SHA-256，重复发布相同内容复用同一版本，不覆盖旧版本。
6. 选择目标 Channel 和已发布版本，核对当前版本及有效动作差异，再点“将所选版本启用到此通道”。只有这一步改变后续请求；不自动启用禁用的通道，不自动发 Key。
7. 在“授权与 Key”区域使用虚构材料发起真实调用，随后查看自动展开的 Trace，核对 `policy_version`、规则命中、动作和是否经过上游。
8. 如需回滚，在同一版本列表中选择原版本或基线，核对反向差异并再次启用。历史记录保留原版本、新版本、目标通道和时间。

每个 HTTP 请求在鉴权后读取一次策略快照，请求与回答使用同一版本。处理中途启用新版本不会改变该请求的回答规则；下一个请求使用新版本。撤销 Key、禁用用户/Channel、撤销授权仍在发送前与交付前检查；已经发送的数据无法撤回。

## 策略能改什么，不能改什么

| 项目 | 当前行为 |
|---|---|
| 请求/回答默认动作 | REDACT 或 BLOCK |
| 类型覆盖 | 内置格式类型及 PERSON、ORGANIZATION、ADDRESS、PROJECT、DEPARTMENT、COURT、LAW_FIRM |
| 未单独配置的类型 | 仍识别，继承该方向默认动作；不会漏过未知但合法的实体类型 |
| 正则表达式、校验器 | 在代码中维护、展示；不提供任意表达式输入或执行 |
| ALLOW | 仅所有检查成功且没有需处理实体时产生；不能配置为敏感原值直通 |
| 私钥/sk- 标记、不确定语义、无效检测结果 | 强制阻断，不接受策略覆盖 |
| 重叠实体 | 在合并前检查所有候选的 BLOCK，避免被较长 REDACT 实体覆盖 |
| 重复实体 | 单次请求内同类型、同原值用相同占位符；不承诺跨请求稳定 |
| 回答 REDACT | 保留已登记占位符、替换新增实体，再做残留复检；未知占位符阻断 |
| 复检失败、依赖故障、审计失败 | 故障闭锁；不回退原文 |

内置 11 个格式正反例针对单个规则；完整动作测试额外覆盖各类型。身份证格式不匹配仍可能被银行卡候选规则命中。测试结果不能当作 HaS/Presidio 真实材料召回率，也不能保证模型法律分析正确。

## 后端接口与数据

管理接口需要管理员会话、同源请求和 CSRF；模型调用 Key 无权使用管理接口。

| 接口 | 作用 |
|---|---|
| GET `/admin/api/policy-workflow` | 草稿、测试结果、已发布版本、Channel 绑定及切换记录 |
| POST `/admin/api/policy-save` | `generation, content`；保存并使旧测试失效 |
| POST `/admin/api/policy-check` | `generation`；固定虚构测试，不接受客户材料 |
| POST `/admin/api/policy-publish` | `generation`；仅当前通过测试的内容可发布 |
| POST `/admin/api/policy-activate` | `channel, version, expected`；校验所属组织和当前版本后原子切换 |
| GET `/admin/api/trace?id=…` | 请求事件及七阶段执行结果 |

配置形状示例：

```json
{
  "request": {"default": "REDACT", "EMAIL": "BLOCK"},
  "response": {"default": "BLOCK"}
}
```

新增 SQLite 表是 `policy_drafts`、`policy_versions`、`policy_bindings`、`policy_activations`。增量建表保留旧 Key、Channel 和审计；未配置的老通道使用明确的基线版本。每个版本存配置、匹配引擎标识、测试摘要和时间；管理操作写入同一事务的审计。草稿和版本均按组织隔离。

当前固定匹配器引擎为 `legal-basic-2:actions-1`，测试套件为 `policy-workflow-2`。修改匹配器/动作语义必须更新引擎标识；修改测试必须更新套件标识。已绑定版本与部署引擎不兼容或内容摘要异常时阻断，需重新测试、发布、显式绑定，不自动降级。完整模型权重、检测服务部署的不可变依赖快照尚未实现；这些升级应另行验收。

## Trace 如何证明实际生效

每条已接纳请求的事件 `revision` 包含 Channel、模型配置摘要及 `pv-…`。授权、请求策略、回答策略阶段记录该完整策略版本。请求 BLOCK 时没有 `upstream.call`；回答 BLOCK 时可以已经调用上游，但不返回违规正文。回答脱敏另记 `redacted_entity_counts`。

原值、客户正文、完整模型回答、Key、映射不写入 Trace。后台真实测试回答只在当前页面临时展示。生产角色分权、保留期/清理、备份恢复、分页检索仍待补充。

## 验收与复现

```bash
.venv/bin/python -m pytest -q tests/test_gateway_policy_versions.py tests/test_gateway.py tests/test_gateway_admin.py tests/test_gateway_policy_trace.py tests/test_secure_ask.py tests/test_privacyguard_core.py
.venv/bin/python scripts/manage_gateway.py stop --directory local-config/gateway-dev-20261104
.venv/bin/python scripts/manage_gateway.py start --directory local-config/gateway-dev-20261104
node scripts/gateway_admin_browser.mjs local-config/gateway-dev-20261104
```

最后三个命令用于本机已有的验收目录；其他电脑应先按 [启动指南](gateway-local-run.md) 初始化自己的目录。浏览器脚本依赖该指南中的本机识别服务、模型服务和 Chrome，仅使用虚构邮箱/手机号，不使用客户材料。

自动回归：105 项测试与 12 个子测试通过。覆盖未测/失败禁止发布、测试后修改、测试中并发编辑、不可变重复发布、并发切换拒绝、组织隔离、重启保留、重叠 BLOCK 优先、回答脱敏、版本损坏闭锁及处理中切换版本。

真实浏览器：登录 → 内置例子 → 建用户与通道 → 授权发 Key → HaS/Presidio/LiteLLM/本机模型成功回答 → 编辑 EMAIL 请求 BLOCK → 保存/测试/发布 → 查看差异并启用 → 实际请求阻断且无上游阶段 → 回滚基线 → 实际模型调用再次成功 → 撤销授权、Key，禁用测试资源 → 登出。页面无 JavaScript 异常。验收保留匿名化的管理操作和请求元数据，不保留可用测试 Key。

浏览器脚本修改本机组织的共享草稿、发布测试版本，并只切换新建的测试通道；不会改变原有业务通道绑定。运行前不要与其他管理员同时编辑这份草稿。

## 常见问题

- `draft_changed_reload`：页面草稿已过期，刷新后重新编辑，不强制覆盖。
- `passing_current_tests_required`：没有当前版本通过测试的记录，或保存/升级套件后测试失效；先重测再发布。
- `binding_changed_reload`：另一次操作已切换该通道，刷新、核对当前版本后再操作。
- 发布后规则没有变化：发布不等于启用；检查 Channel 绑定，再看新请求 Trace。已经在执行的请求仍使用旧版本。
- 请求 `policy_blocked`：命中了本次版本配置的 BLOCK，检查请求策略阶段的命中类型；不是上游网络故障。
- 测试通过但真实调用失败：固定测试不验证服务在线状态、完整语义识别或模型质量。按 Trace 找到失败阶段，检查依赖；不要关闭检测绕过。
- 升级后策略不可用：检查引擎兼容和数据库完整性；重新验证配置后发布绑定，不修改旧版本表冒充兼容。

下一阶段优先补管理员恢复、审计保留/备份恢复和真实标注样例质量验收；更多模型、原生客户端协议和回填保持独立任务。
