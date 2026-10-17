# 真实材料标注指南

候选文件位于 `test-results/real-annotation-candidates.jsonl`，仅限本机使用，已被 `.gitignore` 排除。它包含原文，因此不能提交、上传或复制到外部服务。

不同批次应使用独立路径，避免覆盖已经人工确认的数据：

```bash
.venv-mlx/bin/python -m service.prepare_real_annotation --output test-results/batch-candidates.jsonl /绝对路径/材料1.pdf /绝对路径/材料2.docx
.venv/bin/python -m service.assist_annotation --input test-results/batch-candidates.jsonl --output test-results/batch-assisted.jsonl
.venv/bin/python -m service.annotation_ui --data test-results/batch-assisted.jsonl --port 8765
.venv-mlx/bin/python -m service.evaluate_real --input test-results/batch-assisted.jsonl --output test-results/batch-evaluation.json
```

最后一个命令在任一文件未确认或 gold 为空时必须返回 `awaiting_human_annotation`，不能用 AI 候选直接计算模型指标。

## 每条样本需要确认

将人工确认后的实体写入 `gold_entities`：

```json
{"type":"PERSON","value":"某某","start":10,"end":12,"review":"confirmed"}
```

实体类型固定为：

- `PERSON`：自然人姓名；
- `ORGANIZATION`：公司、律所、法院、机构、学校等；
- `PHONE`：手机号或电话；
- `ID_NUMBER`：身份证、护照或其他个人证件号；
- `BANK_CARD`：银行卡号；
- `ADDRESS`：可定位个人/机构的完整地址；
- `CASE_NUMBER`：案号；
- `CONTRACT_NUMBER`：合同/协议/委托编号；
- `EMAIL`：电子邮箱。

## 标注原则

1. 按原文逐字标注，使用 Python 半开区间 `[start,end)`；
2. 同一实体每次出现都标注；
3. 不把“原告”“被告”“甲方”等角色词单独标为 PERSON；如需评估角色关系，另加备注；
4. 组织名称标完整，不只标“公司”或“律所”；
5. 地址标到足以识别地点的完整片段；
6. 金额、日期默认不纳入本阶段九类 gold，但若其包含身份证、案号或合同编号的一部分，只标对应实体；
7. 模型候选不能直接视为正确，必须人工确认、修改或删除；
8. 在 `review_notes` 记录会改变主体、金额、日期或法律事实的误报。

## 完成条件

- 当前批次的全部文件完成 `review_status=confirmed`；
- gold 实体数量以实际材料为准；100 个只是建议目标，不是硬性门槛；
- 每个 span 通过原文切片校验；
- 记录人工确认、修改、忽略数量；
- 再运行规则、FP16 NER、规则+FP16 NER 的真实评估。
