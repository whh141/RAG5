# exp_20260428_error_07

## 作用

本目录用于保存本科毕设实验的第 7 组实验数据：错误分析实验。

## 实验目标

汇总前六项实验中的失败样本和边界问题，形成统一错误类型分布、典型失败案例表和后续优化方向。

## 输入数据

- `data/experiments/exp_20260428_e2e_01/eval_report_full.json`
- `data/experiments/exp_20260428_route_02/route_report.json`
- `data/experiments/exp_20260428_ood_05/ood_report.json`
- `data/experiments/exp_20260428_complex_04/complex_reasoning_report.json`
- `data/experiments/exp_20260428_efficiency_06/efficiency_report.json`

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 说明实验目的、输入、输出和结果摘要。 |
| `run_error_analysis.py` | 本实验独立汇总脚本。 |
| `error_analysis_report.json` | 统一错误分析完整报告。 |
| `error_cases.csv` | 统一错误样本表。 |
| `error_type_summary.csv` | 错误类型分布统计。 |
| `error_source_summary.csv` | 错误来源实验分布统计。 |
| `chart_prompt.md` | 生成错误分析图表时使用的 prompt。 |

## 运行命令

```powershell
venv\Scripts\python.exe data\experiments\exp_20260428_error_07\run_error_analysis.py
```

## 实验结果摘要

本次统一错误分析共汇总 67 条错误记录。注意：同一问题可能同时出现多个错误标签，例如“答案未通过”和“路由错误”，因此错误记录数不等于唯一问题数。

## 错误类型分布

| 错误类型 | 数量 |
|---|---:|
| OOD 执行异常 | 28 |
| 意图错误 | 19 |
| 答案未通过 | 7 |
| QA 路由错误 | 5 |
| 意图和路径均错误 | 3 |
| 执行异常 | 2 |
| 引用缺失 | 2 |
| 效率实验执行异常 | 1 |

## 错误来源分布

| 来源实验 | 数量 |
|---|---:|
| ood | 28 |
| route | 22 |
| e2e_qa | 16 |
| efficiency | 1 |

## 结果解释

错误主要集中在两个方面：

1. OOD 边界控制不足。越界问题中有 28 条执行异常，主要表现为问题被误路由到本地 RAG 后，知识库无法抽取证据并抛错。
2. 意图粒度识别不足。路由实验中有 19 条意图错误和 3 条意图与路径均错误，主要集中在 `complex_reasoning` 与 `simple_fact` 的混淆。

论文中可以将这部分作为系统局限性和优化方向：后续应加强 OOD 判别规则、补充反例训练/提示样例，并增强复杂推理问题的路由判定标准。
