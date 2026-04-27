# 数据扩充计划（第一轮）

## 目标

在不引入新知识源文件的前提下，先扩充现有评测数据集规模，提高实验统计稳定性，并优先补齐当前明显偏少的 `time_sensitive` 与 `ood` 样本。

## 原则

1. 只基于当前知识域扩充，不引入主域外的“伪知识”。
2. `route_labels.jsonl` 的标签必须与现有路由契约一致：
   - `simple_fact` / `complex_reasoning` -> `retrieve_local`
   - `time_sensitive` -> `retrieve_web`
3. `eval_qa.jsonl` 只新增可由当前知识库稳定支撑的问答，不在本轮新增依赖实时网页结果的标准答案。
4. `ood_questions.jsonl` 优先补充“明显越界”和“校园相关但不属于本科教学服务主域”的问题。
5. 本轮只做高置信扩充，不新增未核验的知识库文件。

## 本轮执行范围

1. 扩充 `route_labels.jsonl`
   - 补充通识核心课、毕业论文、学位管理、教学管理、实验教学、实践教学等问题
   - 重点增加 `time_sensitive` 路由样本
2. 扩充 `eval_qa.jsonl`
   - 补充与现有 FAQ 和知识文档强对应的稳定问答
   - 增加一定比例的复杂推理问题
3. 扩充 `ood_questions.jsonl`
   - 补充开放域、医疗、金融、考试、生活服务、校园生活但非教学服务等越界问题

## 已执行

1. 第一轮：扩充 `route_labels.jsonl`、`eval_qa.jsonl`、`ood_questions.jsonl`
2. 第二轮：扩充 FAQ 标准库
3. 第三轮：新增 `eval_multiturn.jsonl` 与 `eval_composite.jsonl`

## 后续轮次

1. 第四轮：扩充 FAQ 到更高覆盖规模
2. 第五轮：补充新知识文件并同步扩充 QA / route 数据
3. 第六轮：为多轮与复合问题新增专门评测脚本
