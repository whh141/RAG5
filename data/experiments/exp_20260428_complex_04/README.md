# exp_20260428_complex_04

## 作用

本目录用于保存本科毕设实验的第 4 组实验数据：复杂推理能力实验。

## 实验目标

验证智能体的问题理解、路由规划、结构化推理链和反思机制是否能提升复杂问答效果。

## 输入数据

- `data/eval_qa.jsonl` 中 `intent_label == complex_reasoning` 的样本。

## 对比方法

| 方法 | 含义 |
|---|---|
| `direct_rag` | 普通 RAG，直接使用问题进行本地 RAG 检索、证据抽取、推理链生成和答案生成。 |
| `agent_no_reflection` | Agent-RAG 去掉 Reflection，只保留问题分解、意图路由、规划、工具执行、答案合成和最终化。 |
| `full_agent` | 完整 Agent-RAG，包含 Reflection 与必要的同路由重试。 |

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 说明实验目的、对比方法和结果摘要。 |
| `run_complex_reasoning_eval.py` | 本实验独立执行脚本。 |
| `complex_reasoning_report.json` | 复杂推理实验完整报告。 |
| `complex_summary_metrics.csv` | 各方法核心指标，可用于论文表格。 |
| `complex_case_details.csv` | 每条样本在各方法下的结果细节。 |
| `chart_prompt.md` | 生成复杂推理实验图表时使用的 prompt。 |

## 运行命令

```powershell
venv\Scripts\python.exe data\experiments\exp_20260428_complex_04\run_complex_reasoning_eval.py --limit 15
```

## 指标说明

- 问答通过率：答案与标准答案语义相似度达到阈值 0.72。
- 平均语义相似度：答案主体与标准答案的平均语义相似度。
- 引用存在率：答案是否有引用证据。
- 路由准确率：Agent 方法的实际路由是否等于 `expected_route`。
- 推理链存在率：是否生成 `reasoning_steps`。
- 平均反思次数：完整 Agent-RAG 的 reflection 次数。

## 实验结果摘要

| 方法 | 样本数 | 失败数 | 问答通过率 | 平均语义相似度 | 引用存在率 | 推理链存在率 | 路由准确率 | 平均反思次数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| direct_rag | 15 | 0 | 1.0000 | 0.8551 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| agent_no_reflection | 15 | 0 | 1.0000 | 0.8811 | 1.0000 | 0.4000 | 1.0000 | 0.0000 |
| full_agent | 15 | 0 | 1.0000 | 0.8749 | 1.0000 | 0.3333 | 1.0000 | 1.0000 |

## 结果解释

本次复杂推理实验选取 15 条 `complex_reasoning` 样本。三种方法均达到 1.0000 的问答通过率和引用存在率，说明当前知识库和复杂问题样本整体匹配度较高。

`agent_no_reflection` 的平均语义相似度最高，为 0.8811；完整 Agent-RAG 为 0.8749，略低于无反思版本，但每条样本平均执行 1 次 Reflection，能够提供质量评估和必要的同路由重试能力。`direct_rag` 的推理链存在率为 1.0000，是因为直接以 `complex_reasoning` 调用 RAG 工具时会强制生成结构化推理链；Agent 方法中的部分样本被路由器判定为 `simple_fact`，因此不会生成复杂推理链，这也解释了推理链存在率较低。

该实验说明：在当前样本上，Agent-RAG 的主要价值不体现在简单提高语义相似度，而体现在路由、规划、反思评估和引用链路可观测性上。后续如果要更强地区分复杂推理能力，应补充更多多跳、比较、条件判断类问题，并提供人工拆解标注。
