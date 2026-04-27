# 校园 RAG 问答系统

本项目实现面向校园教学服务场景的 RAG 问答系统。主链路聚焦问答可靠性：动态路由、混合检索、重排序、证据抽取、答案生成、引用校验和评测闭环。

## 主链路

```text
用户问题
  -> Router
  -> Planner
  -> local_rag / web_fresh
  -> Evidence Extract
  -> Answer Generate
  -> Citation Verify
  -> Finalize
```

核心约束：

- `data/faq_database.json` 会作为可更新知识材料并入 RAG 知识库。
- 系统主分类聚焦 `simple_fact`、`complex_reasoning`、`time_sensitive` 三类动态路由。
- `simple_fact` 和 `complex_reasoning` 走本地 RAG。
- `time_sensitive` 走时效检索。
- 本地证据不足、模型输出结构错误、引用校验失败都会暴露为错误，不切换到其他路径。

## 技术栈

- LangGraph：工作流编排
- FAISS：向量召回
- BM25：关键词召回
- BGE Reranker / API Reranker：重排序
- Gradio：演示界面
- Tavily：时效检索

## 数据

```text
data/
├── kb_docs/                 # PDF / DOCX 知识库文件
├── faq_database.json        # 作为知识文档并入 RAG
├── eval_qa.jsonl            # 问答评测集
├── route_labels.jsonl       # 路由评测集
├── ood_questions.jsonl      # 越界问题评测集
└── sources_manifest.json
```

知识库加载会为每个 chunk 写入 `doc_id`、`title`、`source_file`、`source_type`、`page`、`chunk_id` 等元数据，最终答案引用这些元数据。

## 运行

```bash
python app_gradio.py
```

批量运行：

```bash
python run_agent.py
```

统一评测：

```bash
python eval_all.py --output-json data/eval_report.json
```

## 环境变量

主要配置项：

```text
LLM_BACKEND=ollama|openai|vllm
AGENT_LLM_BACKEND=ollama|openai
EMBEDDING_BACKEND=local|api|ollama
RERANK_BACKEND=local|api
TAVILY_API_KEY=...
```

如果执行 `time_sensitive` 路由，必须配置 `TAVILY_API_KEY`。
