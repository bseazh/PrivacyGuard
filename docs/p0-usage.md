# P0 原型用法

在 `PrivacyGuard` 目录执行：

```bash
python3 -m service.cli \
  "/path/to/file.docx" "/path/to/file.pdf" \
  --output test-results/p0.json
```

默认只写文件统计和实体结果，不写原文。需要检查脱敏文本时才显式添加 `--include-text`，输出仍应只写入本地测试目录。

P0 当前为规则基线，覆盖身份证号、手机号、邮箱、银行卡号、案号和合同编号。姓名、企业、地址等语义实体等待 NER 后端接入后再评估。
