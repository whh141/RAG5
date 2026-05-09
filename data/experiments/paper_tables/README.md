# paper_tables

## 作用

本目录保存所有已完成实验的论文表格版本，数据来源于 `data/experiments` 下各实验目录中的原始 `csv/json` 结果。

## 表格清单

| 文件 | 作用 |
|---|---|
| `all_tables.md` | 所有论文表格的 Markdown 汇总版，可直接复制到论文草稿。 |
| `table_01_experiment_overview.csv` | 实验路线总览表。 |
| `table_02_dataset_manifest.csv` | 数据集与知识库来源表。 |
| `table_03_environment_config.csv` | 实验环境与配置记录表。 |
| `table_04_e2e_qa_metrics.csv` | 端到端问答实验指标表。 |
| `table_05_route_metrics.csv` | 自主路由实验指标表。 |
| `table_06_route_confusion_matrix.csv` | 路由意图混淆矩阵表。 |
| `table_07_retrieval_ablation_summary.csv` | 检索消融实验汇总表。 |
| `table_08_retrieval_at_k.csv` | 检索覆盖率 K 值明细表。 |
| `table_09_complex_reasoning_ablation.csv` | 复杂推理消融实验表。 |
| `table_10_ood_metrics.csv` | 越界问题处理实验指标表。 |
| `table_11_efficiency_by_type.csv` | 不同问题类型效率实验表。 |
| `table_12_stage_time.csv` | 智能体阶段耗时分解表。 |
| `table_13_error_type_summary.csv` | 错误类型统计表。 |
| `table_14_error_source_summary.csv` | 错误来源统计表。 |
| `table_15_conversation_smoke_summary.csv` | 会话持久化自动测试汇总表。 |
| `table_16_conversation_smoke_details.csv` | 会话持久化自动测试逐项表。 |

## 使用说明

这些表格是论文写作版本，不覆盖原始实验结果。若后续重新运行实验，应先更新各实验目录中的原始结果，再同步更新本目录。

