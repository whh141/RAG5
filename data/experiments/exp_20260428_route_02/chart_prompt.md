# 自主路由实验图表生成 Prompt

请根据 `data/experiments/exp_20260428_route_02/route_report.json`、`route_summary_metrics.csv` 和 `route_confusion_matrix.csv` 生成论文可用图表。

需要生成以下图表：

1. 路由核心指标柱状图：
   - 路由准确率
   - 意图分类准确率
   - 路径选择准确率
   - 链路成功率

2. 意图分类混淆矩阵热力图：
   - 数据来源：`route_confusion_matrix.csv`
   - 行为真实意图，列为预测意图
   - 类别包括 `simple_fact`、`complex_reasoning`、`time_sensitive`、`ood`

3. 各真实意图类别的路由准确率柱状图：
   - 数据来源：`route_report.json` 中 `details`
   - 按 `expected_intent` 分组
   - 统计 `ok=true` 的比例

4. 路由错误类型柱状图：
   - 数据来源：`route_error_cases.csv`
   - 按“意图错误”“路径错误”“意图和路径均错误”“执行异常”分类

输出要求：

- 图片保存为 PNG。
- 同步导出 CSV 数据。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 图表适合本科毕业论文正文插入。
