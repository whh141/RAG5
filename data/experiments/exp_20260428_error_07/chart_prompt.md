# 错误分析实验图表生成 Prompt

请根据 `data/experiments/exp_20260428_error_07/error_cases.csv`、`error_type_summary.csv` 和 `error_source_summary.csv` 生成论文可用图表。

需要生成以下图表：

1. 错误类型分布柱状图：
   - 数据来源：`error_type_summary.csv`
   - 横轴：`error_type`
   - 纵轴：`count`

2. 错误来源实验分布柱状图：
   - 数据来源：`error_source_summary.csv`
   - 横轴：`source_experiment`
   - 纵轴：`count`

3. 错误类型 × 来源实验堆叠柱状图：
   - 数据来源：`error_cases.csv`
   - 横轴：`source_experiment`
   - 堆叠项：`error_type`
   - 纵轴：样本数量

4. 典型失败案例表：
   - 从 `error_cases.csv` 中按错误类型各选 1-2 条
   - 展示 `source_experiment`、`id`、`question`、`error_type`、`reason`

输出要求：

- 图片保存为 PNG。
- 同步导出 CSV 数据。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 图表适合本科毕业论文正文插入。
