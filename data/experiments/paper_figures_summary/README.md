# paper_figures_summary

## 作用

本目录用于汇总本科毕设实验章节所需的总表、图表清单和统一绘图 prompt。

## 已完成实验

| 编号 | 实验目录 | 实验名称 | 主要作用 |
|---|---|---|---|
| 1 | `exp_20260428_e2e_01` | 端到端问答效果实验 | 验证完整 Agent-RAG 问答质量。 |
| 2 | `exp_20260428_route_02` | 自主路由实验 | 验证意图识别和路径选择能力。 |
| 3 | `exp_20260428_retrieval_03` | 检索与重排序消融实验 | 比较 BM25、FAISS、Hybrid、Hybrid+Rerank。 |
| 4 | `exp_20260428_complex_04` | 复杂推理能力实验 | 比较普通 RAG、无反思 Agent-RAG、完整 Agent-RAG。 |
| 5 | `exp_20260428_ood_05` | OOD 越界拒答实验 | 验证边界控制和拒答能力。 |
| 6 | `exp_20260428_efficiency_06` | 系统效率实验 | 统计总耗时、节点耗时和反思次数。 |
| 7 | `exp_20260428_error_07` | 错误分析实验 | 汇总失败样本和错误类型。 |

## 本目录文件说明

| 文件 | 作用 |
|---|---|
| `paper_experiment_overview.csv` | 论文实验总览表。 |
| `paper_key_metrics.csv` | 所有实验核心指标汇总。 |
| `paper_figure_list.csv` | 推荐插入论文的图表清单。 |
| `paper_plot_prompt.md` | 统一图表生成 prompt。 |
| `paper_experiment_section_outline.md` | 论文实验章节写作提纲。 |

## 写作建议

论文中不要把第 3 个实验的“语义覆盖率@K”写成严格 Recall@K。当前 QA 数据没有人工证据标注，因此检索消融实验只能说明检索结果与标准答案的语义覆盖情况。若后续补充 `support_doc_id` 或人工标注 `human_support_label`，才能计算严格 Recall@K 和 MRR。

OOD 实验结果不理想，但具有论文价值：它清楚揭示了系统边界控制不足，是后续优化方向的重要依据。

