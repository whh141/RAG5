# exp_20260428_e2e_01

## 作用

本目录用于保存本科毕设实验的第 1 组实验数据：完整 Agent-RAG 端到端问答效果实验。

## 实验目标

验证系统在固定知识库和固定问答评测集上，是否能完成从问题理解、路由、规划、检索、证据抽取、答案生成、反思到最终引用输出的完整链路。

## 输入数据

- `data/eval_qa.jsonl`：端到端问答评测集。
- `data/route_labels.jsonl`：路由评测集，随 `eval_all.py` 一起运行并保存到同一报告。
- `data/ood_questions.jsonl`：越界问题评测集，随 `eval_all.py` 一起运行并保存到同一报告。
- `data/kb_docs/`：本地知识库文档。
- `data/faq_database.json`：结构化 FAQ 知识文件，会并入本地 RAG 知识库。

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 说明本次实验目录的用途、输入、输出和图表 prompt。 |
| `eval_report_full.json` | 第 1 个实验的完整评测报告，包含 route、qa、ood 三部分。 |
| `environment_snapshot.json` | 实验环境快照，用于论文复现，包括 Git 版本、Python 版本、工作区状态摘要。 |
| `requirements_snapshot.txt` | Python 依赖快照。 |
| `model_config_snapshot.json` | 模型与检索后端配置快照，不保存 API Key 明文。 |
| `dataset_manifest.json` | 本次实验使用的数据集文件统计。 |
| `chart_prompt.md` | 生成端到端问答实验图表时使用的 prompt。 |

## 运行命令

```powershell
venv\Scripts\python.exe eval_all.py --output-json data\experiments\exp_20260428_e2e_01\eval_report_full.json
```

## 当前执行状态

实验已完成，完整报告已保存为 `eval_report_full.json`。

本次执行命令为：

```powershell
venv\Scripts\python.exe eval_all.py --route-limit 0 --ood-limit 0 --output-json data\experiments\exp_20260428_e2e_01\eval_report_full.json
```

说明：`eval_all.py` 当前的 `limit=0` 实现会保留 1 条样本，因此报告中 route 和 OOD 部分各包含 1 条附带样本；第 1 个实验的主要分析对象是 `qa` 部分的 148 条完整问答评测样本。

## 实验结果摘要

| 指标 | 数值 |
|---|---:|
| QA 样本数 | 148 |
| QA 路由准确率 | 0.9662 |
| QA 引用存在率 | 0.9865 |
| QA 问答通过率 | 0.9527 |
| QA 平均语义相似度 | 0.8798 |
| QA 链路失败率 | 0.0135 |
| QA 执行失败样本数 | 2 |
| QA 答案未通过样本数 | 7 |
| QA 路由错误样本数 | 5 |
| QA 引用缺失样本数 | 2 |

## 评价指标

- `route.accuracy`：自主路由准确率。
- `qa.answer_pass_rate`：端到端问答通过率。
- `qa.avg_semantic_similarity`：答案与标准答案的平均语义相似度。
- `qa.citation_rate`：答案引用存在率。
- `qa.failure_rate`：问答链路失败率。
- `ood.refuse_accuracy`：越界问题严格拒答准确率。
