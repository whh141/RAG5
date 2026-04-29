# 会话持久化功能测试图表生成 Prompt

请根据 `data/experiments/exp_20260429_conversation_08/conversation_smoke_results.csv`、`conversation_test_metrics.csv` 和 `manual_test_checklist.csv` 生成论文或报告可用图表。

需要生成以下内容：

1. 自动 smoke test 通过情况表：
   - 数据来源：`conversation_smoke_results.csv`
   - 展示 `test_item`、`status`、`elapsed_ms`、`note`

2. 功能测试类别覆盖表：
   - 数据来源：`conversation_test_metrics.csv`
   - 按 `category` 分组统计指标数量

3. 自动测试结果柱状图：
   - 横轴：`status`
   - 纵轴：测试项数量

4. 手工验证清单表：
   - 数据来源：`manual_test_checklist.csv`
   - 展示待手工确认的刷新、重启、缓存、布局等项目

输出要求：

- 图片保存为 PNG。
- 同步导出处理后的 CSV。
- 中文标题、中文坐标轴。
- 数值保留 4 位小数。
- 明确注明：该实验是系统功能测试，不是 RAG 问答效果实验。
