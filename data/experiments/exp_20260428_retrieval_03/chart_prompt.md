# 检索与重排序消融实验图表生成 Prompt

请根据 `data/experiments/exp_20260428_retrieval_03/retrieval_summary_metrics.csv` 和 `retrieval_at_k_metrics.csv` 生成论文可用图表。

需要生成以下图表：

1. 检索策略语义覆盖率@5 柱状图：
   - 横轴：`bm25_only`、`faiss_only`、`hybrid`、`hybrid_rerank`
   - 纵轴：`semantic_coverage_at_k`
   - 只取 `k=5`

2. 检索策略语义覆盖率@K 折线图：
   - 横轴：K = 1、3、5、8、10、20
   - 纵轴：语义覆盖率@K
   - 每条线代表一种检索策略

3. 平均最佳语义相似度@K 折线图：
   - 横轴：K = 1、3、5、8、10、20
   - 纵轴：`avg_best_similarity_at_k`
   - 每条线代表一种检索策略

4. 语义命中 MRR 柱状图：
   - 数据来源：`retrieval_summary_metrics.csv`
   - 横轴为方法
   - 纵轴为 `semantic_mrr`

输出要求：

- 图片保存为 PNG。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 在图注中注明：该实验使用标准答案语义覆盖指标，不等同于人工标注下的严格 Recall@K。
