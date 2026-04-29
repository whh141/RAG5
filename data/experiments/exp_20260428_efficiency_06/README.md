# exp_20260428_efficiency_06

## 作用

本目录用于保存本科毕设实验的第 6 组实验数据：系统效率实验。

## 实验目标

统计系统在不同问题类型下的端到端响应时间、各节点耗时、实际路由和反思次数，分析系统主要耗时来源。

## 输入数据

本实验从以下文件中抽样：

- `data/eval_qa.jsonl`：抽取 `simple_fact` 和 `complex_reasoning` 样本。
- `data/route_labels.jsonl`：抽取 `time_sensitive` 样本。
- `data/ood_questions.jsonl`：抽取 OOD 样本。

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 说明实验目的、输入、输出和结果摘要。 |
| `run_efficiency_eval.py` | 本实验独立执行脚本，构建带计时的 LangGraph。 |
| `efficiency_report.json` | 效率实验完整报告。 |
| `efficiency_case_details.csv` | 每条样本的总耗时、路由、反思次数和各节点耗时。 |
| `efficiency_summary_metrics.csv` | 按问题类型分组的平均耗时、P50、P95 等指标。 |
| `stage_time_summary.csv` | 各节点平均耗时与耗时占比。 |
| `chart_prompt.md` | 生成效率实验图表时使用的 prompt。 |

## 运行命令

```powershell
venv\Scripts\python.exe data\experiments\exp_20260428_efficiency_06\run_efficiency_eval.py --per-type 3
```

## 指标说明

- 总响应时间：单条问题从进入图到最终输出或异常的总耗时。
- 节点耗时：`question_decompose`、`intent_classify`、`planning`、`tool_execution`、`synthesize`、`reflection`、`finalize` 的耗时。
- P50/P95：每类问题总响应时间的中位数和 95 分位值。
- 平均反思次数：每类问题触发 Reflection 的平均次数。

## 实验结果摘要

本次实验每类抽取 3 条样本，共 12 条。

| 问题类型 | 样本数 | 失败数 | 平均总耗时(s) | P50(s) | P95(s) | 平均反思次数 |
|---|---:|---:|---:|---:|---:|---:|
| simple_fact | 3 | 0 | 21.8599 | 19.8209 | 26.4383 | 1.0000 |
| complex_reasoning | 3 | 0 | 20.6323 | 20.4261 | 21.4276 | 1.0000 |
| time_sensitive | 3 | 0 | 29.6361 | 24.1952 | 42.7007 | 3.0000 |
| ood | 3 | 1 | 7.5345 | 6.4586 | 12.4874 | 0.6667 |

## 节点耗时摘要

| 节点 | 总耗时(s) | 平均耗时(s) | 耗时占比 |
|---|---:|---:|---:|
| question_decompose | 0.0002 | 0.0000 | 0.0000 |
| intent_classify | 20.9269 | 1.7439 | 0.0876 |
| planning | 6.3186 | 0.5265 | 0.0264 |
| tool_execution | 174.3651 | 14.5304 | 0.7298 |
| composite_execution | 0.0000 | 0.0000 | 0.0000 |
| synthesize | 0.0002 | 0.0000 | 0.0000 |
| reflection | 37.3119 | 3.1093 | 0.1562 |
| finalize | 0.0001 | 0.0000 | 0.0000 |

## 结果解释

系统主要耗时集中在 `tool_execution`，占比约 72.98%，其中包含本地 RAG 检索、重排序、证据抽取、答案生成或联网检索。第二大耗时来自 `reflection`，占比约 15.62%。

`time_sensitive` 样本平均耗时最高，为 29.6361 秒，主要原因是该类问题触发联网检索，并且本次 3 条样本平均反思次数达到 3.0000，出现了多轮同路由重试。OOD 样本平均耗时较低，但包含 1 条失败样本，说明越界问题如果被正确拒答会很快完成，如果误入本地 RAG 则可能在检索证据阶段失败。
