# 论文实验图表统一生成 Prompt

请根据 `data/experiments/` 下的实验结果文件，为本科毕业论文生成实验图表和表格。

## 数据来源

使用以下文件：

- `data/experiments/paper_figures_summary/paper_experiment_overview.csv`
- `data/experiments/paper_figures_summary/paper_key_metrics.csv`
- `data/experiments/paper_figures_summary/paper_figure_list.csv`
- `data/experiments/exp_20260428_e2e_01/summary_metrics.csv`
- `data/experiments/exp_20260428_route_02/route_confusion_matrix.csv`
- `data/experiments/exp_20260428_route_02/route_summary_metrics.csv`
- `data/experiments/exp_20260428_retrieval_03/retrieval_summary_metrics.csv`
- `data/experiments/exp_20260428_retrieval_03/retrieval_at_k_metrics.csv`
- `data/experiments/exp_20260428_complex_04/complex_summary_metrics.csv`
- `data/experiments/exp_20260428_ood_05/ood_summary_metrics.csv`
- `data/experiments/exp_20260428_efficiency_06/efficiency_summary_metrics.csv`
- `data/experiments/exp_20260428_efficiency_06/stage_time_summary.csv`
- `data/experiments/exp_20260428_error_07/error_type_summary.csv`

## 需要生成的图表

1. 端到端问答核心指标柱状图
   - 指标：QA 路由准确率、QA 引用存在率、QA 问答通过率、QA 平均语义相似度、QA 链路成功率。
   - 数据来源：`exp_20260428_e2e_01/summary_metrics.csv`。

2. 路由意图混淆矩阵热力图
   - 行：真实意图。
   - 列：预测意图。
   - 数据来源：`exp_20260428_route_02/route_confusion_matrix.csv`。

3. 检索策略语义覆盖率@K 折线图
   - 横轴：K = 1、3、5、8、10、20。
   - 纵轴：语义覆盖率@K。
   - 曲线：bm25_only、faiss_only、hybrid、hybrid_rerank。
   - 数据来源：`exp_20260428_retrieval_03/retrieval_at_k_metrics.csv`。
   - 图注必须注明：该指标是标准答案语义覆盖率，不等同于人工证据标注下的严格 Recall@K。

4. 检索策略语义 MRR 对比柱状图
   - 横轴：bm25_only、faiss_only、hybrid、hybrid_rerank。
   - 纵轴：semantic_mrr。
   - 数据来源：`exp_20260428_retrieval_03/retrieval_summary_metrics.csv`。

5. 复杂推理方法对比图
   - 横轴：direct_rag、agent_no_reflection、full_agent。
   - 指标：answer_pass_rate、avg_semantic_similarity、citation_rate、reasoning_chain_rate。
   - 数据来源：`exp_20260428_complex_04/complex_summary_metrics.csv`。

6. OOD 越界拒答指标柱状图
   - 指标：strict_refuse_accuracy、behavior_match_rate、ood_success_rate、ood_failure_rate。
   - 数据来源：`exp_20260428_ood_05/ood_summary_metrics.csv`。

7. 不同问题类型平均响应时间柱状图
   - 横轴：simple_fact、complex_reasoning、time_sensitive、ood。
   - 纵轴：avg_total_time_sec。
   - 数据来源：`exp_20260428_efficiency_06/efficiency_summary_metrics.csv`。

8. 各节点耗时占比柱状图
   - 横轴：stage。
   - 纵轴：time_share。
   - 数据来源：`exp_20260428_efficiency_06/stage_time_summary.csv`。

9. 错误类型分布柱状图
   - 横轴：error_type。
   - 纵轴：count。
   - 数据来源：`exp_20260428_error_07/error_type_summary.csv`。

## 输出要求

- 所有图片输出为 PNG。
- 所有图表使用中文标题、中文坐标轴、中文图例。
- 数值保留 4 位小数。
- 图表风格保持统一，适合本科毕业论文正文插入。
- 同步导出绘图所用的处理后 CSV。
- 对第 3 项检索图表，在图注中明确写明“语义覆盖率@K，不等同于严格 Recall@K”。

