# NER 阶段实现说明

## 标注格式

`test-data/ner-gold.jsonl` 每行一个样本，包含 `text` 和实体数组。实体使用 Python 半开区间 `[start, end)`，这样评估可以严格检查值和位置。

## 运行模型与混合基线

```bash
.venv-mlx/bin/python -m service.evaluate_mlx
```

脚本使用 Qwen3 1.7B、prompt B 和 2400 字符窗口/300 字符重叠，分别输出 `rules`、`fp16_ner`、`hybrid` 的 exact-span 指标。2026-10-17 的三份合成 gold 结果为：MLX 与 hybrid precision 0.8333、recall 0.9091、F1 0.8696。样本很小，只用于回归，不代表真实材料准确率。

## 真实材料评估

真实材料只保存在 `test-results/` 或仓库外目录。先生成候选，再通过本地 UI 人工确认，最后运行 `service.evaluate_real`。当前 5 份真实材料共 17,723 字符、60 个模型候选，均处于待人工确认状态，所以真实 precision、recall 与误报率尚未产生。

评估必须按实体类型统计，并记录 exact span 的 precision、recall、F1、处理时延和内存；不能只看模型返回了多少实体。
