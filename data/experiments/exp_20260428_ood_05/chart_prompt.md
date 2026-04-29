# OOD 越界拒答实验图表生成 Prompt

请根据 `data/experiments/exp_20260428_ood_05/ood_summary_metrics.csv` 和 `ood_case_details.csv` 生成论文可用图表。

需要生成以下图表：

1. OOD 核心指标柱状图：
   - 严格拒答准确率
   - 行为匹配率
   - 链路成功率

2. OOD 实际路由分布柱状图：
   - 横轴：`actual_route`
   - 纵轴：样本数量

3. OOD 行为失败类型柱状图：
   - 数据来源：`ood_error_cases.csv`
   - 按错误类型统计数量

4. OOD 典型错误案例表：
   - 展示 `id`、`question`、`expected_behavior`、`actual_route`、`error_type`

输出要求：

- 图片保存为 PNG。
- 同步导出 CSV 数据。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 图表适合本科毕业论文正文插入。
