# Gateway 本机原型：运行与客户端验收

日期：2026-11-04。G1 的单用户/单 Channel 子集已跑通。不是完整管理后台，不支持多租户、动态策略发布或回填，不代表 WorkBuddy/Codex 原生模型接入已验收。

后续更新：同日已扩展为本机单组织多用户/多 Channel，并增加管理员登录、授权、Key 发放/撤销与审计页面，见 [后台使用与验收](gateway-admin.md)。以下保留初版数据协议和 SDK 验收说明；后台启动及当前权限以新指南为准。

## 当前可用范围

- HTTP 入口固定 `http://127.0.0.1:8787/v1`，仅监听回环地址。
- 网关模型别名 `privacyguard-local`，绑定一个明确的本机上游；拒绝外部域名、任意内网目标和网关自身端口。上游进程应视为本机可信依赖。
- SQLite 保存 Key 的 SHA-256 校验值、24 小时到期及撤销状态，审计只记录 ID、版本、动作、原因码及实体总数。`client.json` 保存明文调用 Key，目录 0700、文件 0600，禁止上传。
- 请求最多 32KiB、16 条纯文本消息、单条 8000 字符；每用户每分钟 10 次，单实例最多 1 个推理请求，忙时返回 429。
- 必选本地 HaS、规则和 Presidio，假名化后复检；回答中检测到敏感值则阻断。私钥标记及 `sk-` 示例凭据规则直接阻断，规则并不覆盖所有凭据格式。
- 同一次请求内跨消息保持相同原值的占位符一致，不保存可恢复映射。客户端传入占位符暂时拒绝，因此不能直接将现有 MCP 安全文本改路由到本原型；G3 仍待实现。
- 只允许 `model`、`messages`、`stream=false`；不支持流式、tools、Responses API、图片、附件、温度等其他字段，返回 400，不透传。
- LiteLLM 复用既有受控传输适配，固定 temperature=0、max_tokens=512、无重试/重定向；不完整回答阻断。没有对外暴露原 `secure_ask` 的安全引用或固定任务接口。
- 内容检查设阶段预算 120 秒、依赖 HTTP 超时；同步检测在返回时再次检查预算，预算到期不会发给上游，但不保证 CPU/网络任务能立即终止。推理超时 95 秒。
- 审计库写入失败阻断；未认证请求不写业务审计，未提供长期保留/清理、生产监控及多实例限流。
- `GET /health` 仅表示进程存活，明确返回 `ready: not_probed`；需烟雾测试证明依赖与模型实际可用。

## 启动（仓库根目录）

先确保现有 RedactionEverything/HaS、Presidio 和本机模型运行，默认端口分别是 8000/8080、5002、8011。网关不会静默启动或切换检测器。

```bash
.venv/bin/python -m pip install -e '.[gateway,test]'
.venv/bin/python -m privacyguard.gateway init \
  --directory local-config/gateway-dev \
  --model "openai/$PWD/models/qwen3/Qwen3-1.7B-bf16"
.venv/bin/python -m privacyguard.gateway serve --directory local-config/gateway-dev
```

初始化拒绝覆盖现有目录。上述启动是前台运行，Ctrl+C 停止；占用 8787 时启动失败，不结束其他进程。模型配置仍是创建 Channel 时的快照，不随 config.json 自动覆盖。策略动作现可在后台经过草稿、测试、发布和显式启用后生效，不必重启；请求记录模型配置摘要及不可变策略版本，见 [策略工作流](gateway-policy-workflow.md)。

另开终端验收：

```bash
.venv/bin/python scripts/gateway_smoke.py --client-config local-config/gateway-dev/client.json
```

脚本以官方 OpenAI Python SDK 连接网关，验证模型列表、私钥阻断、拒绝流式和真实模型往返；仅使用虚构邮箱/手机号，不打印 Key 或正文。客户端 API 超时设为 240 秒，禁用自动重试。

本次本机状态目录为 `local-config/gateway-dev-20261104/`；复测本次实例时将命令中的目录改成这个名称。密钥 24 小时过期；当前没有续期界面，到期后撤销旧 Key、停止服务，再初始化新的独立目录。

撤销本实例全部 Key：

```bash
.venv/bin/python -m privacyguard.gateway revoke --directory local-config/gateway-dev
```

## 验收证据

`tests/test_gateway.py` 使用记录型适配器及真实 HTTP 测试上游。验证身份与模型拒绝、凭据阻断、出站无虚构原值、跨消息占位符一致、输出漏敏阻断、审计故障、途中撤销、大小/字段/协议限制、速率和上游地址限制。

本机 `gateway_smoke.py` 已得到：`models: PASS`、`private_key_block: PASS`、`stream_rejected: PASS`、`real_model_roundtrip: PASS; entity_count=2`。链路实际使用 RedactionEverything/HaS + Presidio + LiteLLM + 本机 Qwen3，回答未返回虚构邮箱/手机号。

该实测证明 SDK 客户端链路，不证明 WorkBuddy/Codex 的原生界面兼容。网关 `approved` 仅表示隐私策略检查通过，不代表合同法律分析质量通过既有固定任务质量验收。

## 常见问题

- `invalid_key`：Key 缺失、错误、过期或撤销。不要把服务商 Key 当网关 Key。
- `unsupported_request`：客户端发送了 stream/tools/多模态/其他未支持字段。不可通过关闭校验让其透传；应后续实现协议再验收。
- `dependency_failed`：检测或模型异常。先检查相关服务；不返回异常原文，避免日志泄露。
- `review_required` / `residual_detected`：不确定实体或复检残留，转第一层人工复核，不能跳过检测。
- `unregistered_placeholder`：当前原型不接收客户端预先生成的占位符；现有 MCP 继续原链路。
- 后端 `/health` 正常但上传 500：目录迁移后旧进程可能仍引用原 UPLOAD_DIR/DATA_DIR。应以新绝对路径重启对应后端，不能用旧健康响应判断识别正常。本次已修复该运行状态。
- pip 显示已安装但 import 失败：检查包文件是否实际存在。本次 Presidio 依赖出现元数据存在但模块缺失，需重新安装指定版本，不能据元数据声称环境验收通过。
- pip 镜像证书异常：使用可信的官方源 `--index-url https://pypi.org/simple`，不要关闭 TLS 校验。

## 下一步

按 [TODO](gateway-todo.md) 继续 G1 的组织/用户/Channel 模型与权限隔离，再实现 G2 管理后台。当前原型仅供本机开发验收，未加入默认一键安装、未部署国内服务器、未修改宿主客户端配置。
