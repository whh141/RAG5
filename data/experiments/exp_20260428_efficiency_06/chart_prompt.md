# 系统效率实验图表生成 Prompt

请根据 `data/experiments/exp_20260428_efficiency_06/efficiency_summary_metrics.csv`、`efficiency_case_details.csv` 和 `stage_time_summary.csv` 生成论文可用图表。

需要生成以下图表：

1. 不同问题类型平均响应时间柱状图：
   - 横轴：`sample_type`
   - 纵轴：`avg_total_time_sec`

2. 不同问题类型 P50/P95 响应时间分组柱状图：
   - 横轴：`sample_type`
   - 指标：`p50_total_time_sec`、`p95_total_time_sec`

3. 各节点平均耗时柱状图：
   - 横轴：`stage`
   - 纵轴：`avg_time_sec`

4. 各节点耗时占比饼图或柱状图：
   - 数据来源：`stage_time_summary.csv`
   - 使用 `time_share`

5. 完整 Agent-RAG 反思次数分布图：
   - 数据来源：`efficiency_case_details.csv`
   - 横轴：`reflection_count`
   - 纵轴：样本数量

输出要求：

- 图片保存为 PNG。
- 同步导出 CSV 数据。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 图表适合本科毕业论文正文插入。
