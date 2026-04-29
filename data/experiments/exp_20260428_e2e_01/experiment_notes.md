# 实验记录

## 已完成内容

- 完成实验前准备目录创建。
- 完成端到端 QA 小样本链路验证，输出 `eval_report_smoke.json`。
- 完成第 1 个实验的完整 QA 评测，输出 `eval_report_full.json`。
- 修正评分模块，使本地评分模型不再依赖 `text2vec` 与当前 `transformers` 版本不兼容的导入路径。

## 评分模块修正说明

原始错误：

```text
ImportError: cannot import name 'AdamW' from 'transformers.optimization'
```

原因：

`text2vec==1.2.9` 依赖旧版 `transformers` 中的 `AdamW` 导出路径，而当前项目环境为 `transformers==4.57.1`。

处理方式：

本地评分仍使用 `SCORING_MODEL_PATH=./pre_train_model/text2vec-base-chinese` 指向的同一语义模型，但加载方式改为 `transformers.AutoTokenizer` + `transformers.AutoModel`，并使用 mean pooling 后的归一化向量点积计算语义相似度。该处理不切换到 API，不改变 RAG 问答链路。

## 注意事项

`eval_all.py` 当前 `_read_jsonl` 的 `limit=0` 会读取 1 条样本。因此本次报告中的 route 和 OOD 部分各包含 1 条附带样本；第 1 个实验只引用 `qa` 部分作为端到端问答效果结果。
