# 可复现验收与反馈

在仓库根目录执行。以下分开验证代码、真实服务和识别质量，不要求新用户一次运行全部步骤。命令以现有 macOS 开发环境 `.venv/bin/python` 为例；不是已验收的 Windows 启动承诺。

## 1. 无真实模型的代码回归

前提：Python 3.11 虚拟环境与项目依赖已按安装指南准备好。如需补测试依赖：

```bash
.venv/bin/python -m pip install -e '.[gateway,test]'
.venv/bin/python -m pytest -q \
  tests/test_gateway_policy_versions.py tests/test_gateway.py \
  tests/test_gateway_admin.py tests/test_gateway_policy_trace.py \
  tests/test_secure_ask.py tests/test_privacyguard_core.py
```

这些测试使用受控识别结果、模拟适配器或本机记录型 HTTP 上游，不需要下载新权重。检查草稿过期、失败禁止发布、重复/重叠实体、发送前脱敏、回答拦截、依赖失败、授权撤销和 Trace 不留正文。既有验收记录为 105 项与 12 个子测试通过，具体以当前执行输出为准；通过不证明真实识别模型在线。

## 2. 初始化独立的本机网关验收目录

先启动已安装的 RedactionEverything/HaS、Presidio 和分析模型，默认对应 8000/8080、5002、8011。下面的模型路径必须与 8011 服务实际提供的模型一致。目录已存在时不要重复初始化或删除业务数据。

```bash
.venv/bin/python -m privacyguard.gateway init \
  --directory local-config/gateway-acceptance \
  --model "openai/$PWD/models/qwen3/Qwen3-1.7B-bf16"
.venv/bin/python -m privacyguard.gateway init-admin \
  --directory local-config/gateway-acceptance
.venv/bin/python scripts/manage_gateway.py start \
  --directory local-config/gateway-acceptance
```

8787 已被已有网关占用时，优先使用其状态目录进行验收，不启动第二套服务、不结束未知进程。需要切换时先确认实例身份再用停止脚本停止原实例。

`GET http://127.0.0.1:8787/health` 的 alive 仅表示进程存活；`ready: not_probed` 不能当作识别模型和上游就绪。

## 3. SDK 真实服务往返

```bash
.venv/bin/python scripts/gateway_smoke.py \
  --client-config local-config/gateway-acceptance/client.json
```

预期出现 models、private_key_block、stream_rejected、real_model_roundtrip 的 PASS。脚本使用虚构邮箱/手机号，禁止用客户材料替换。真实模型测试需要完整依赖在线；失败时保留错误码和请求 ID，不以健康接口代替往返验收。

Key 默认 24 小时有效。过期后在管理员后台重新发放并保存新的接入配置，将 `--client-config` 指向该文件；不需要重建数据库。不要公开文件中的 Key。

## 4. 管理后台完整策略闭环

打开 `http://127.0.0.1:8787/admin`，从对应状态目录选取 `admin-login.txt` 登录，按照 [策略工作流](gateway-policy-workflow.md) 执行：

| 操作 | 必须看到的结果 |
|---|---|
| 创建专用测试用户/Channel、启用、授权发 Key | 只获得本通道模型访问权限 |
| 基线发送虚构邮箱/手机号测试 | 脱敏后模型往返，Trace 显示实际版本与检查阶段 |
| 请求 EMAIL 改为 BLOCK，保存 | 当前通道不变；旧测试失效 |
| 测试、发布 | 固定虚构断言通过才可发布；发布仍不改变绑定 |
| 比较差异并启用到测试 Channel | 新请求 BLOCK；Trace 没有 upstream.call |
| 回滚基线再测试 | 新请求恢复模型往返；Trace 版本对应基线 |
| 撤销授权/Key | 旧 Key 被拒绝；最后禁用测试用户和通道 |

已有浏览器自动化需要 Node、`app/node_modules/playwright-core` 和 macOS Chrome：

```bash
node scripts/gateway_admin_browser.mjs local-config/gateway-acceptance
```

此脚本会修改组织共享草稿、发布测试版本、新建并最终禁用测试资源；仅切换新建测试通道，不改变旧业务通道绑定。不要与管理员同时编辑共享草稿。失败中止时必须检查测试用户、Key 和通道并手动撤销；当前脚本不能保证异常中途也完整清理。截图输出到忽略提交的 `test-results/gateway-admin.png`。

## 5. MCP 文件链路单独验收

参考 [WorkBuddy 配置](workbuddy.md) 和 [统一流程](unified-pipeline-verification.md)。只提交虚构材料路径，要求调用 `privacy_process_and_ask`；默认只分析，明确要求下载才设置 `create_safe_copy=true`。

开发者已有本地模型环境可执行：

```bash
PRIVACYGUARD_LLM_MODEL="openai/$PWD/models/qwen3/Qwen3-1.7B-bf16" \
PRIVACYGUARD_LLM_BASE_URL="http://127.0.0.1:8011/v1" \
PRIVACYGUARD_LLM_API_KEY="local-only" \
  .venv/bin/python tests/secure_ask_live.py
```

该脚本生成虚构 DOCX/TXT、走真实 MCP 和配置模型，检查导出、受控问答、分析不生成文件、统一入口下载及原始路径不能冒充安全引用。它不覆盖扫描 PDF；扫描件验收另见 [OCR 报告](ocr-and-quality-acceptance.md)。脚本测试目录会清理，但解析服务上传副本不因此保证删除。

若 `blocked`，不要让 Agent 自行读取原文、换普通 OCR 或把原文发给模型。安全文件磁盘路径不能替代 `safe_reference`；引用到期需重新走审批/处理，不手工伪造引用。

## 6. 质量评估与测试反馈

真实材料召回率必须依赖人工标注，见 [标注指南](real-annotation-guide.md)。分别报告按类型召回率、误报率、尾部实体、OCR 缺字和模型分析事实依据；不能用虚构动作测试通过率替代。

反馈记录以下内容即可：日期、系统/架构、Git 提交、入口（MCP/Gateway）、依赖是否在线、使用的虚构样例编号、预期动作、实际状态/错误码、request_id、策略版本、失败阶段、上游是否被调用、测试资源是否清理。

不要附原文、完整请求/回答、映射、Key、密码文件或引用 token。模型测试可能耗时，当前无通用完成时间承诺；服务超时算失败，不算通过。没有执行的项目标记“未执行”，不要引用历史结果冒充本轮结果。
