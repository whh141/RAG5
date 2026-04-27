# 数据包说明

## 包含文件
- `faq_database.json`：FAQ 标准库，高频、标准答案型问题。
- `gold.json`：兼容当前 Agent-RAG 批量测试脚本的参考答案。
- `test_question.json`：兼容当前 Agent-RAG 测试脚本的问题文件。
- `eval_qa.jsonl`：问答基准评测集。
- `eval_multiturn.jsonl`：多轮追问评测集，重点验证指代消解和上下文继承。
- `eval_composite.jsonl`：复合问题评测集，重点验证子问题拆解与合成回答。
- `route_labels.jsonl`：路由标注集，覆盖 simple_fact / time_sensitive / complex_reasoning。
- `ood_questions.jsonl`：越界问题集，用于验证拒答路线。
- `sources_manifest.json`：数据来源说明。

## 文件结构
```text
data/
├── faq_database.json
├── gold.json
├── test_question.json
├── eval_qa.jsonl
├── eval_multiturn.jsonl
├── eval_composite.jsonl
├── route_labels.jsonl
├── ood_questions.jsonl
└── sources_manifest.json
```

## 新增数据集字段约定

### `eval_multiturn.jsonl`
- `id`：样本编号
- `history`：多轮历史，格式为 `[{role, content}]`
- `question`：当前轮用户追问
- `ground_truth`：当前轮标准答案
- `intent_label`：当前轮期望意图
- `expected_route`：当前轮期望路由
- `expected_query_rewrite`：结合历史后应形成的检索问题
- `scenario`：场景标签

### `eval_composite.jsonl`
- `id`：样本编号
- `question`：原始复合问题
- `sub_questions`：期望拆解出的子问题列表
- `ground_truth`：按子问题顺序组织的标准答案
- `intent_label`：固定为 `composite`
- `expected_route`：固定为 `composite`
- `expected_sub_routes`：每个子问题的期望路由
- `scenario`：场景标签

## 继续扩展为校园问答时要补什么
- 学生手册
- 本科生学籍管理规定
- 奖学金评定办法
- 图书馆借阅规则
- 校历 / 选课通知
- 宿舍管理规定
- 毕业论文 / 毕业设计管理办法
