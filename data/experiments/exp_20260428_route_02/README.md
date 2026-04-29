# exp_20260428_route_02

## 作用

本目录用于保存本科毕设实验的第 2 组实验数据：智能体自主路由实验。

## 实验目标

验证系统能否根据用户问题自主判断问题意图，并选择正确执行路径。该实验对应论文中“自主推理与检索”的自主决策能力验证。

## 输入数据

- `data/route_labels.jsonl`：路由评测集。

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 说明本次实验目录的用途、输入、输出和结果摘要。 |
| `run_route_eval.py` | 本实验的独立执行脚本，只运行路由评测，不运行 QA/OOD。 |
| `route_report.json` | 路由评测完整结果，包含每条样本的期望与实际路由。 |
| `route_summary_metrics.csv` | 路由实验核心指标，可直接用于论文表格。 |
| `route_confusion_matrix.csv` | 意图分类混淆矩阵，用于绘制混淆矩阵图。 |
| `route_error_cases.csv` | 路由错误样本表，用于错误分析。 |
| `chart_prompt.md` | 生成路由实验图表时使用的 prompt。 |

## 运行命令

```powershell
venv\Scripts\python.exe data\experiments\exp_20260428_route_02\run_route_eval.py
```

## 评价指标

- 路由准确率：`actual_intent == expected_intent` 且 `actual_route == expected_route`。
- 意图分类准确率：只比较 `actual_intent` 与 `expected_intent`。
- 路径选择准确率：只比较 `actual_route` 与 `expected_route`。
- 失败率：路由节点执行异常样本比例。

## 实验结果摘要

| 指标 | 数值 |
|---|---:|
| 路由样本数 | 133 |
| 路由准确率 | 0.8346 |
| 意图分类准确率 | 0.8346 |
| 路径选择准确率 | 0.9774 |
| 路由节点失败率 | 0.0000 |
| 路由节点成功率 | 1.0000 |
| 错误样本数 | 22 |

## 混淆矩阵摘要

| 真实意图 | simple_fact | complex_reasoning | time_sensitive | ood | unknown |
|---|---:|---:|---:|---:|---:|
| simple_fact | 80 | 2 | 0 | 0 | 0 |
| complex_reasoning | 17 | 14 | 0 | 0 | 0 |
| time_sensitive | 2 | 0 | 17 | 1 | 0 |
| ood | 0 | 0 | 0 | 0 | 0 |

## 错误类型摘要

| 错误类型 | 数量 |
|---|---:|
| 意图错误 | 19 |
| 意图和路径均错误 | 3 |

主要错误集中在 `complex_reasoning` 被识别为 `simple_fact`，说明系统对“需要综合比较、条件判断、规则归纳”的复杂问题识别仍有改进空间；路径选择准确率较高，说明即使意图粒度存在混淆，大多数样本仍能进入正确检索路径。
