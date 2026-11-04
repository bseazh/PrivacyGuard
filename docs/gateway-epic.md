# [Epic] PrivacyGuard Gateway：管理员管控与两层隐私保护

## 问题

现有 PrivacyGuard 能通过 MCP 完成文件识别、假名化、验证及 LiteLLM 受控调用，但不能为多个 API 客户端提供统一用户授权、Channel 路由、策略版本和审计。需要新增独立网关，同时保持现有安全引用与文件验证边界。

## 实现目标

管理员可以完成“建用户→配上游→配策略并测试→绑定 Channel→显式启用→发放网关 Key→验收调用→审计/撤销/回滚”。普通用户只配置网关地址、自己的 Key 和允许模型；上游密钥不下发。

设计基线：https://github.com/bseazh/PrivacyGuard/blob/main/docs/gateway-design.md

TODO 与验收矩阵：https://github.com/bseazh/PrivacyGuard/blob/main/docs/gateway-todo.md

## 跟踪清单

- [ ] G0：评审并确认设计基线。
- [ ] G1：最小非流式文本网关、鉴权、请求/回答策略及记录型上游验收。
- [ ] G2：后台页面、角色、策略测试、版本启用/回滚、最小审计。
- [ ] G3：PrivacyGuard 与实际客户端协议接入和验收文档。
- [ ] G4：隔离 Vault 与授权本地 Round Trip 回填。

## 不纳入首版

订阅流量透明接管、OA 同步、复杂组织树、流式、工具调用、多模态、Responses API、生产多实例部署。客户端所需协议未通过测试时不得宣称兼容。G4 回填不自动进入 G1。

## 完成标准

按 TODO 中里程碑逐项提供测试证据；记录型上游证明阻断时零请求、脱敏后无已标注原值；版本发布显式可控、跨租户隔离、失败闭锁、日志不泄露。再用虚构数据验证真实模型与实际客户端。未经评审不将设计当作已实现能力或修改默认安装链路。

本 Issue 用于后续分阶段 PR 跟踪。当前阶段仅方案和任务拆分，不包含网关业务代码。
