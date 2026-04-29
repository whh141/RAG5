# 复杂推理能力实验图表生成 Prompt

请根据 `data/experiments/exp_20260428_complex_04/complex_summary_metrics.csv` 和 `complex_case_details.csv` 生成论文可用图表。

需要生成以下图表：

1. 复杂问答通过率对比柱状图：
   - 横轴：`direct_rag`、`agent_no_reflection`、`full_agent`
   - 纵轴：`answer_pass_rate`

2. 平均语义相似度对比柱状图：
   - 横轴：三种方法
   - 纵轴：`avg_semantic_similarity`

3. 引用存在率与推理链存在率分组柱状图：
   - 横轴：三种方法
   - 指标：`citation_rate`、`reasoning_chain_rate`

4. 完整 Agent-RAG 反思次数分布图：
   - 数据来源：`complex_case_details.csv`
   - 只取 `method == full_agent`
   - 横轴：`reflection_count`
   - 纵轴：样本数量

5. 失败样本相似度对比表：
   - 筛选 `answer_ok == false`
   - 展示 `id`、`question`、`method`、`semantic_similarity`、`error`

输出要求：

- 图片保存为 PNG。
- 同步导出 CSV 数据。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 图表适合本科毕业论文正文插入。
