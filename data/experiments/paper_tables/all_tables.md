# 所有实验表格汇总

## 表 1 实验路线总览

| 序号 | 实验编号 | 实验名称 | 类型 | 目标 | 数据 | 主要指标 | 状态 |
|---:|---|---|---|---|---|---|---|
| 1 | exp_20260428_e2e_01 | 端到端问答效果实验 | 效果评估 | 验证完整问答链路的回答质量、路由正确性和引用完整性 | data/eval_qa.jsonl | QA 路由准确率、答案通过率、平均语义相似度、引用存在率、执行失败率 | completed |
| 2 | exp_20260428_route_02 | 自主路由实验 | 能力评估 | 验证智能体对问题意图和执行路径的自主判断能力 | data/route_labels.jsonl | 路由准确率、意图准确率、路径准确率、失败率 | completed |
| 3 | exp_20260428_retrieval_03 | 检索消融实验 | 消融实验 | 比较 BM25、FAISS、混合检索和重排序的语义覆盖能力 | data/eval_qa.jsonl 抽样 30 条 | 语义 MRR、Coverage@K、平均最佳相似度 | completed |
| 4 | exp_20260428_complex_04 | 复杂推理消融实验 | 消融实验 | 比较直接 RAG、无反思智能体和完整智能体在复杂问题上的表现 | data/eval_qa.jsonl 复杂问题抽样 15 条 | 答案通过率、平均语义相似度、引用率、推理链率、平均反思次数 | completed |
| 5 | exp_20260428_ood_05 | 越界问题实验 | 鲁棒性评估 | 验证系统对知识库外问题的拒答与行为匹配能力 | data/ood_questions.jsonl | 严格拒答准确率、行为匹配率、失败率、实际路由分布 | completed |
| 6 | exp_20260428_efficiency_06 | 效率实验 | 效率评估 | 统计不同类型问题和智能体阶段的耗时 | 抽样数据 | 平均耗时、P50、P95、阶段耗时占比 | completed |
| 7 | exp_20260428_error_07 | 错误分析实验 | 错误分析 | 汇总各实验失败样本并分类 | 各实验结果 | 错误类型计数、错误来源计数 | completed |
| 8 | exp_20260429_conversation_08 | 会话持久化与前端交互验证 | 功能回归测试 | 验证 SQLite 会话、会话 API、session_id 聊天协议和前端历史会话功能 | 临时 SQLite 与 fake runtime | 自动测试通过率、逐项功能通过情况 | completed |

## 表 2 数据集与知识库来源

| 数据路径 | 作用 | 样本数 | 计数状态 |
|---|---|---:|---|
| data/eval_qa.jsonl | 端到端问答评测集 | 148 | completed |
| data/route_labels.jsonl | 自主路由评测集 | 133 | completed |
| data/ood_questions.jsonl | 越界问题评测集 | 60 | completed |
| data/kb_docs/ | 本地 RAG 知识库文档目录 | - | not_applicable |
| data/faq_database.json | 结构化 FAQ 知识文件 | - | not_applicable |
| data/conversations.sqlite3 | 生产运行时会话数据库 | - | runtime_generated |

## 表 3 实验环境与配置记录

| 项目 | 值 | 说明 |
|---|---|---|
| run_id | exp_20260428_e2e_01 | 环境快照来源实验 |
| created_at | 2026-04-28 | 实验创建日期 |
| timezone | Asia/Shanghai | 实验时区 |
| cwd | d:\VS_projects\RAG6\Agent-RAG | 项目工作目录 |
| git_head | 405f7696322ef82ab88bd20fee39d8d0a27ad544 | 实验时记录的 Git HEAD |
| python_executable | D:\VS_projects\RAG6\Agent-RAG\venv\Scripts\python.exe | 虚拟环境 Python |
| experiment_execution_status | completed | 端到端实验已完成 |
| model_config_snapshot | not_completed_due_to_shell_approval_timeout | 模型配置快照未完整生成，论文中不应记录未确认参数 |

## 表 4 端到端问答实验指标

| 指标 | 数值 | 说明 |
|---|---:|---|
| qa_total | 148 | 端到端问答评测样本数 |
| qa_route_accuracy | 0.9662 | QA 样本中实际路由与期望路由一致的比例 |
| qa_citation_rate | 0.9865 | 最终答案存在引用或拒答路径的比例 |
| qa_answer_pass_rate | 0.9527 | 语义相似度达到阈值的答案比例 |
| qa_avg_semantic_similarity | 0.8798 | 成功评测样本的平均语义相似度 |
| qa_failure_rate | 0.0135 | QA 链路执行失败比例 |
| qa_failed | 2 | QA 执行异常样本数 |
| qa_answer_failed | 7 | 答案未通过样本数 |
| qa_route_failed | 5 | 路由不一致样本数 |
| qa_citation_failed | 2 | 引用缺失样本数 |

## 表 5 自主路由实验指标

| 指标 | 数值 | 说明 |
|---|---:|---|
| route_total | 133 | 路由评测样本数 |
| route_accuracy | 0.8346 | 意图和路径同时正确的比例 |
| intent_accuracy | 0.8346 | 仅意图分类正确的比例 |
| path_accuracy | 0.9774 | 仅执行路径选择正确的比例 |
| route_failure_rate | 0.0000 | 路由节点执行失败比例 |
| route_success_rate | 1.0000 | 路由节点成功执行比例 |

## 表 6 路由意图混淆矩阵

| 真实意图 | 预测 simple_fact | 预测 complex_reasoning | 预测 time_sensitive | 预测 ood | 预测 unknown |
|---|---:|---:|---:|---:|---:|
| simple_fact | 80 | 2 | 0 | 0 | 0 |
| complex_reasoning | 17 | 14 | 0 | 0 | 0 |
| time_sensitive | 2 | 0 | 17 | 1 | 0 |
| ood | 0 | 0 | 0 | 0 | 0 |

## 表 7 检索消融实验汇总

| 方法 | 样本数 | 阈值 | 语义 MRR | Coverage@1 | Coverage@3 | Coverage@5 | Coverage@8 | Coverage@10 | Coverage@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25_only | 30 | 0.72 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| faiss_only | 30 | 0.72 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| hybrid | 30 | 0.72 | 0.977778 | 0.966667 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| hybrid_rerank | 30 | 0.72 | 0.983333 | 0.966667 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |

说明：该实验未包含严格 `support_doc_id/source_file`，因此指标应表述为语义覆盖率，不应写成严格 Recall@K。

## 表 8 检索覆盖率 K 值明细

| 方法 | K | Semantic Coverage@K | Avg Best Similarity@K |
|---|---:|---:|---:|
| bm25_only | 1 | 1.000000 | 0.950665 |
| bm25_only | 3 | 1.000000 | 0.962038 |
| bm25_only | 5 | 1.000000 | 0.962038 |
| bm25_only | 8 | 1.000000 | 0.962038 |
| bm25_only | 10 | 1.000000 | 0.962038 |
| bm25_only | 20 | 1.000000 | 0.962038 |
| faiss_only | 1 | 1.000000 | 0.958900 |
| faiss_only | 3 | 1.000000 | 0.962038 |
| faiss_only | 5 | 1.000000 | 0.962038 |
| faiss_only | 8 | 1.000000 | 0.962038 |
| faiss_only | 10 | 1.000000 | 0.962038 |
| faiss_only | 20 | 1.000000 | 0.962038 |
| hybrid | 1 | 0.966667 | 0.936380 |
| hybrid | 3 | 1.000000 | 0.953978 |
| hybrid | 5 | 1.000000 | 0.962038 |
| hybrid | 8 | 1.000000 | 0.962038 |
| hybrid | 10 | 1.000000 | 0.962038 |
| hybrid | 20 | 1.000000 | 0.962038 |
| hybrid_rerank | 1 | 0.966667 | 0.948474 |
| hybrid_rerank | 3 | 1.000000 | 0.962038 |
| hybrid_rerank | 5 | 1.000000 | 0.962038 |
| hybrid_rerank | 8 | 1.000000 | 0.962038 |
| hybrid_rerank | 10 | 1.000000 | 0.962038 |
| hybrid_rerank | 20 | 1.000000 | 0.962038 |

## 表 9 复杂推理消融实验

| 方法 | 样本数 | 失败数 | 答案通过率 | 平均语义相似度 | 引用率 | 推理链率 | 路由准确率 | 平均反思次数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| direct_rag | 15 | 0 | 1.0000 | 0.855133 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| agent_no_reflection | 15 | 0 | 1.0000 | 0.881061 | 1.0000 | 0.4000 | 1.0000 | 0.0000 |
| full_agent | 15 | 0 | 1.0000 | 0.874864 | 1.0000 | 0.3333 | 1.0000 | 1.0000 |

## 表 10 越界问题处理实验

| 指标 | 数值 | 说明 |
|---|---:|---|
| ood_total | 60 | OOD 评测样本数 |
| strict_refuse_accuracy | 0.4000 | actual_route == refuse 的比例 |
| behavior_match_rate | 0.5333 | 符合 expected_behavior 的比例 |
| ood_failure_rate | 0.4667 | OOD 链路执行失败比例 |
| ood_success_rate | 0.5333 | OOD 链路成功执行比例 |
| route_refuse_count | 24 | 实际拒答样本数 |
| route_retrieve_web_count | 8 | 实际进入时效检索样本数 |
| route_retrieve_local_count | 0 | 实际误入本地检索样本数 |
| route_unknown_count | 28 | 无实际路由样本数 |

## 表 11 不同问题类型效率实验

| 问题类型 | 样本数 | 失败数 | 平均耗时/s | P50/s | P95/s | 平均反思次数 |
|---|---:|---:|---:|---:|---:|---:|
| simple_fact | 3 | 0 | 21.859902 | 19.820891 | 26.438260 | 1.000000 |
| complex_reasoning | 3 | 0 | 20.632333 | 20.426123 | 21.427576 | 1.000000 |
| time_sensitive | 3 | 0 | 29.636142 | 24.195232 | 42.700731 | 3.000000 |
| ood | 3 | 1 | 7.534465 | 6.458557 | 12.487360 | 0.666667 |

## 表 12 智能体阶段耗时分解

| 阶段 | 总耗时/s | 平均耗时/s | 耗时占比 |
|---|---:|---:|---:|
| question_decompose | 0.000229 | 0.000019 | 0.000001 |
| intent_classify | 20.926947 | 1.743912 | 0.087589 |
| planning | 6.318585 | 0.526549 | 0.026446 |
| tool_execution | 174.365066 | 14.530422 | 0.729796 |
| composite_execution | 0.000000 | 0.000000 | 0.000000 |
| synthesize | 0.000244 | 0.000020 | 0.000001 |
| reflection | 37.311910 | 3.109326 | 0.156167 |
| finalize | 0.000105 | 0.000009 | 0.000000 |

## 表 13 错误类型统计

| 错误类型 | 数量 |
|---|---:|
| OOD 执行异常 | 28 |
| 意图错误 | 19 |
| 答案未通过 | 7 |
| QA 路由错误 | 5 |
| 意图和路径均错误 | 3 |
| 执行异常 | 2 |
| 引用缺失 | 2 |
| 效率实验执行异常 | 1 |

## 表 14 错误来源统计

| 来源实验 | 数量 |
|---|---:|
| ood | 28 |
| route | 22 |
| e2e_qa | 16 |
| efficiency | 1 |

## 表 15 会话持久化自动测试汇总

| 实验 | 用例数 | 通过 | 失败 | 通过率 | 是否写入生产数据库 |
|---|---:|---:|---:|---:|---|
| conversation_persistence_smoke | 14 | 14 | 0 | 1.0000 | false |

## 表 16 会话持久化自动测试逐项结果

| 测试项 | 状态 | 耗时/ms |
|---|---|---:|
| 初始会话列表为空 | PASS | 11.955 |
| 创建会话 | PASS | 15.955 |
| 空会话详情可读取 | PASS | 6.683 |
| 第一轮聊天写入成功 | PASS | 16.257 |
| 第一轮聊天无历史输入 | PASS | 0.002 |
| 第二轮聊天写入成功 | PASS | 13.633 |
| 第二轮自动读取上一轮历史 | PASS | 0.001 |
| 消息顺序为 user/assistant/user/assistant | PASS | 8.345 |
| 首条用户消息自动生成标题 | PASS | 5.441 |
| 重命名会话成功 | PASS | 14.896 |
| 空消息返回 422 | PASS | 6.313 |
| 无效 session 返回 404 | PASS | 5.212 |
| 删除会话成功 | PASS | 17.310 |
| 删除后详情返回 404 | PASS | 22.806 |

