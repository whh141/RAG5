# exp_20260428_retrieval_03

## 作用

本目录用于保存本科毕设实验的第 3 组实验数据：检索与重排序消融实验。

## 实验目标

比较不同检索策略在本地知识库问答任务上的证据覆盖能力，验证 BM25、FAISS、混合检索和重排序对检索质量的影响。

## 重要说明

当前 `data/eval_qa.jsonl` 只有问题和标准答案，没有 `support_doc_id` 或 `support_source_file` 等金标准证据标注。因此本实验不把自动结果称为严格 `Recall@K` 或严格 `MRR`。

本实验使用固定评分模型计算“检索文档片段与标准答案”的语义相似度，并报告：

- 语义覆盖率@K：Top-K 文档中是否存在与标准答案语义相似度达到阈值的片段。
- 平均最佳语义相似度@K：Top-K 文档中与标准答案最相似片段的平均分。
- 语义命中 MRR：第一个达到语义阈值的文档排名倒数的平均值。

同时导出 `retrieval_candidates_top5.csv`，用于后续人工标注支持文档。人工标注完成后，才能计算严格 Recall@K 和 MRR。

## 输入数据

- `data/eval_qa.jsonl`：问答评测集，仅使用 `expected_route == retrieve_local` 的本地 RAG 样本。
- `data/kb_docs/`：本地知识库文档。
- `data/faq_database.json`：结构化 FAQ 知识文件。

## 对比方法

| 方法 | 含义 |
|---|---|
| `bm25_only` | 仅使用 BM25 关键词检索。 |
| `faiss_only` | 仅使用 FAISS 向量检索。 |
| `hybrid` | FAISS + BM25 合并后进行预排序。 |
| `hybrid_rerank` | FAISS + BM25 合并、预排序后使用 Rerank 加权重排。 |

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 说明实验目的、指标定义和结果摘要。 |
| `run_retrieval_ablation.py` | 本实验独立执行脚本。 |
| `retrieval_ablation_report.json` | 检索消融完整报告。 |
| `retrieval_summary_metrics.csv` | 各方法总体指标，可用于论文表格。 |
| `retrieval_at_k_metrics.csv` | 各方法不同 K 值下的语义覆盖指标。 |
| `retrieval_candidates_top5.csv` | 每个问题各方法 Top-5 候选文档，用于人工证据标注。 |
| `chart_prompt.md` | 生成检索消融图表时使用的 prompt。 |

## 运行命令

```powershell
venv\Scripts\python.exe data\experiments\exp_20260428_retrieval_03\run_retrieval_ablation.py
```

## 实际执行命令

由于本地 BGE Rerank 在 CPU 环境下耗时较长，本次实验采用分层抽样方式执行，保证 `simple_fact` 与 `complex_reasoning` 样本数量一致，所有检索策略使用同一批样本。

```powershell
venv\Scripts\python.exe data\experiments\exp_20260428_retrieval_03\run_retrieval_ablation.py --stratified-limit 30
```

样本分布：

| 意图类型 | 样本数 |
|---|---:|
| simple_fact | 15 |
| complex_reasoning | 15 |

## 实验结果摘要

| 方法 | 样本数 | 语义阈值 | 语义命中 MRR | 语义覆盖率@1 | 语义覆盖率@3 | 语义覆盖率@5 | 语义覆盖率@20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| bm25_only | 30 | 0.72 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| faiss_only | 30 | 0.72 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hybrid | 30 | 0.72 | 0.9778 | 0.9667 | 1.0000 | 1.0000 | 1.0000 |
| hybrid_rerank | 30 | 0.72 | 0.9833 | 0.9667 | 1.0000 | 1.0000 | 1.0000 |

## 结果解释

在本次分层抽样的 30 条本地 RAG 样本中，四种检索策略在 Top-3 以后均达到 1.0000 的语义覆盖率，说明当前知识库和测试问题匹配度较高。Top-1 指标上，BM25 和 FAISS 均达到 1.0000，Hybrid 与 Hybrid+Rerank 为 0.9667；Hybrid+Rerank 的语义命中 MRR 高于 Hybrid，说明重排序对个别样本的排序位置有修正作用。

该结果不能替代人工证据标注下的严格 Recall@K/MRR。若论文需要严格检索召回指标，应基于 `retrieval_candidates_top5.csv` 补充人工 `human_support_label` 后再统计。
