# PrivacyGuard 文档导航

当前说明核对日期：2026-11-04。先按入口选择文档；历史验收只代表报告日期、配置和样例，不等于当前所有电脑均通过。

## 按使用目的阅读

| 读者 / 任务 | 建议顺序 |
|---|---|
| 新用户安装 | [新手入口](../START_HERE.md) → [README 安装](../README.md#一句话安装) → [WorkBuddy 配置与聊天验收](workbuddy.md) |
| 使用 MCP 处理文件 | [脱敏原理](privacy-principles.md) → [统一文件流程](unified-pipeline-verification.md) → [文件输出验证](file-output-verification.md) |
| 管理文本网关 | [本机启动](gateway-local-run.md) → [后台使用](gateway-admin.md) → [策略编辑、测试、发布和回滚](gateway-policy-workflow.md) → [Trace](gateway-policy-trace.md) |
| 评估隐私与安全 | [数据流、安全边界和缺口](data-flow-and-boundaries.md) → [可复现验收](reproducible-acceptance.md) |
| 开发者理解实现 | [README 路线图](../README.md#总体架构与执行边界) → [识别管道代码依据](gateway-recognition-architecture.md) → [Gateway TODO](gateway-todo.md) |

## 当前实现与长期规划

- 当前管道原理：[安全脱敏原理](privacy-principles.md)、[识别技术路线](gateway-recognition-architecture.md)。
- 当前安全与数据生命周期：[安全边界](data-flow-and-boundaries.md)。
- 可复现测试和反馈格式：[验收指南](reproducible-acceptance.md)。
- 长期目标：[Gateway 设计](gateway-design.md)、[Epic](gateway-epic.md)。这些文档包含尚未实现的角色分权、上游管理和回填，不应当作使用手册。
- 专题历史证据：[OCR 与分析质量](ocr-and-quality-acceptance.md)、[真实材料标注](real-annotation-guide.md)、[执行报告](privacyguard-execution-report.md)。历史路径、版本、测试数量及服务状态以当时报告为准。

## 阅读时的三个区别

1. MCP 文件处理、Gateway 文本 API、桌面人工操作是不同入口，功能不自动互通。
2. 自动化测试通过、真实服务调用通过、真实材料识别质量达标是不同层次的结论。
3. `approved` 表示当前检查通过，不是零漏检证明，也不是法律分析正确性保证。

遇到不一致，以当前代码和可复现实测为依据，将差异登记到 [明确缺口](data-flow-and-boundaries.md#明确缺口与处理顺序)，不要静默绕过阻断。
