# 端到端问答实验图表生成 Prompt

请根据 `data/experiments/exp_20260428_e2e_01/eval_report_full.json` 生成论文可用图表和 CSV 表格。

需要生成以下图表：

1. 端到端问答核心指标柱状图：
   - `qa.answer_pass_rate`
   - `qa.avg_semantic_similarity`
   - `qa.citation_rate`
   - `qa.route_accuracy`
   - `1 - qa.failure_rate`

2. 语义相似度分布直方图：
   - 数据来源：`qa.details[*].semantic_similarity`
   - 忽略 `null` 值
   - 横轴为语义相似度区间，纵轴为样本数量

3. 按期望路径分组的问答通过率柱状图：
   - 数据来源：`qa.details[*].expected_route` 和 `qa.details[*].answer_ok`
   - 横轴为 `expected_route`
   - 纵轴为通过率

4. 失败原因分布柱状图：
   - 数据来源：`qa.failure_reasons`
   - 横轴为失败类型
   - 纵轴为样本数量

输出要求：

- 图片保存为 PNG。
- 同步导出 CSV 数据。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 图表适合本科毕业论文正文插入。
