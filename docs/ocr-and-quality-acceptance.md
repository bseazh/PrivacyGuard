# OCR、真实材料标注与回答质量验收

日期：2026-10-17。下列结果来自本地 Apple Silicon 环境，不代表全格式、全材料准确率。

## 逐页 OCR

RedactionEverything 上传、解析后，扫描 PDF 经其本地 `/structure` 服务逐页识别。适配器以 150 DPI 渲染每页，按坐标排序全文框，保留页面边界并记录页码、框数和字符数。总页数必须匹配，每页必须非空；拼接正文必须与逐页文本一致。重建文本再次交回 RedactionEverything 解析与 HaS 识别，偏移以这份完全相同的文本为准。

真实两页图像样本已通过：每页 3 个框、57 字符；HaS 检出 PERSON、PHONE、EMAIL，PrivacyGuard 高层扫描批准。空白第二页会阻断。Mac 使用 PP-StructureV3 CPU 兼容模式的 `/structure`，不是禁用的 PaddleOCR-VL `/ocr`。配置项为 `PRIVACYGUARD_REDACTION_OCR_URL`，默认 `http://127.0.0.1:8082`。

复现：

```bash
.venv/bin/python tests/ocr_coverage_live.py
```

测试只生成虚构临时样本，只输出覆盖统计，不输出正文或安全引用。逐页非空仅证明页面参与识别，不能证明无漏字、无错字或表格关系准确。空白页目前保守阻断；下载采用纯文本重建，扫描图片与原版式不保留。

同一两页扫描 PDF 另经 `process_and_ask(task="summary")` 完整调用本地 LiteLLM/Qwen3，返回 `approved`、PERSON/PHONE/EMAIL 各 1、`safe_file=null`，聊天结果不包含安全正文、引用或原姓名/手机号/邮箱。该项验证扫描到模型的连通与隐私输出边界，不代表摘要全部语义正确。

## 真实材料本地标注

已从仓库外 5 份真实材料提取 17,723 字符，生成 60 个 MLX 候选。候选及原文只存在被 Git 忽略的 `test-results/actual-material-candidates.jsonl` 和 `actual-material-assisted.jsonl`。

当前 gold 为 0，5 份均待人工确认，评估正确返回 `awaiting_human_annotation`。60 个模型候选全部为 PERSON，不能据此认定其他实体不存在，也不能只复核这些候选。因此本轮没有真实材料召回率或误报率。此前 10 份、42 gold 的模拟材料结果不得代替这批真实材料结果。

在本地完成确认、删除误报、补充漏报后再计算：

```bash
.venv/bin/python -m service.annotation_ui --data test-results/actual-material-assisted.jsonl --port 8765
.venv-mlx/bin/python -m service.evaluate_real --input test-results/actual-material-assisted.jsonl --output test-results/actual-material-evaluation.json
```

访问 `http://127.0.0.1:8765`。必须通读每份原文，不能只接受现有候选，否则漏报无法进入 gold。评估是 exact span：precision=TP/(TP+FP)，recall=TP/(TP+FN)；1-precision 是检出结果中的误报占比，不是按所有非实体字符计算的 FPR。当前脚本评估规则、MLX、二者合并，尚不是 HaS/Presidio 全体集成质量评估。

合成回归集只有 3 份、11 个 gold：prompt B、2400/300 分块的 MLX/混合结果为 TP=10、FP=2、FN=1，precision=0.8333、recall=0.9091、F1=0.8696。不能据此承诺真实材料精度。

## LiteLLM 质量

真实 MCP → HaS/规则/Presidio → 发送前 Guardrail → LiteLLM → 本地 Qwen3 1.7B 已通过虚构合同验收。长提示曾引起付款条件与期限混淆、虚构隐含标准以及过度后果推断，因此改成短的证据抽取模板，并增加输出阻断。

回答必须分为事实、风险、待核查三段；引用必须逐字存在于安全材料。风险后果限制为固定中性表述，禁止模型自由推导权利、效力或违约结论。真实验收回答保留了“交付后付款”条件和未约定的期限，风险附原句，不含原人名、手机、邮箱。

这仍是受约束的材料整理，不是全面法律分析正确性证明。事实段与待核查段的全面语义蕴含校验、更多合同基准与人工审阅仍待补充。真实材料 gold 确认、HaS/Presidio 集成召回率、复杂排版 OCR 字符准确率应作为下一阶段门槛。

## 回归结果

本轮定向回归 63 项通过，另有 16 个子用例。`scripts/test_privacyguard.sh` 完整退出码为 0：基础组 53 项、LiteLLM 组 14 项，MCP 六工具发现、TXT/DOCX 导出、默认不导出、显式下载和真实模型调用均通过。两组与定向回归有重叠，不能相加作为独立测试总数。`tests/ocr_coverage_live.py` 也退出 0，验证两页全文标记、跨页敏感值、批准文本去除原值和空白页阻断。
