# exp_20260428_ood_05

## 作用

本目录用于保存本科毕设实验的第 5 组实验数据：OOD 越界拒答实验。

## 实验目标

验证系统面对校园教学服务知识库范围外的问题时，是否能够正确拒答或按样本期望进入时效检索路径，避免基于无关知识生成答案。

## 输入数据

- `data/ood_questions.jsonl`：越界问题评测集。

## 输出文件说明

| 文件 | 作用 |
|---|---|
| `README.md` | 说明本次实验目的、输入、输出和结果摘要。 |
| `run_ood_eval.py` | 本实验独立执行脚本。 |
| `ood_report.json` | OOD 完整评测结果。 |
| `ood_summary_metrics.csv` | OOD 核心指标，可用于论文表格。 |
| `ood_case_details.csv` | 每条 OOD 样本的实际路由、答案和行为是否匹配。 |
| `ood_error_cases.csv` | OOD 行为失败或执行异常样本表。 |
| `chart_prompt.md` | 生成 OOD 实验图表时使用的 prompt。 |

## 运行命令

```powershell
venv\Scripts\python.exe data\experiments\exp_20260428_ood_05\run_ood_eval.py
```

## 指标说明

- 严格拒答准确率：`actual_route == refuse` 的比例。
- 行为匹配率：如果样本期望为 `reject_or_web`，则 `refuse` 或 `retrieve_web` 均视为行为匹配。
- 失败率：图执行异常的样本比例。
- 路由分布：统计实际进入 `refuse`、`retrieve_web`、`retrieve_local` 等路径的数量。

## 实验结果摘要

| 指标 | 数值 |
|---|---:|
| OOD 样本数 | 60 |
| 严格拒答准确率 | 0.4000 |
| 行为匹配率 | 0.5333 |
| OOD 链路失败率 | 0.4667 |
| OOD 链路成功率 | 0.5333 |
| 实际拒答样本数 | 24 |
| 实际进入时效检索样本数 | 8 |
| 无实际路由样本数 | 28 |

## 错误类型摘要

| 错误类型 | 数量 |
|---|---:|
| 执行异常 | 28 |

## 结果解释

本次 OOD 实验暴露出明显边界控制问题：60 条越界样本中，仅 24 条被严格拒答，8 条进入时效检索，28 条执行失败。失败样本主要表现为问题被路由到本地 RAG 后，本地知识库无法抽取可用证据并抛出异常，因此报告中 `actual_route` 记录为 `unknown`。

这说明当前系统在部分通用知识、考试报名、生活服务、金融社保等问题上容易误判为 `simple_fact/retrieve_local`，而不是在路由阶段识别为 `ood/refuse` 或 `time_sensitive/retrieve_web`。论文中应将该结果作为系统边界与后续优化方向，而不是只报告成功样本。
