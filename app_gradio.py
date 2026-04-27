#!/usr/bin/env python
# coding: utf-8
"""
    RAG 问答系统 - Gradio 6 交互界面
兼容 Gradio 6.x 的 Web 演示界面
"""

import time
import os
from typing import Any, Dict, Generator, List, Tuple

_LOCAL_NO_PROXY = "127.0.0.1,localhost,::1"
os.environ["NO_PROXY"] = (
    f"{os.environ.get('NO_PROXY', '')},{_LOCAL_NO_PROXY}"
    if os.environ.get("NO_PROXY")
    else _LOCAL_NO_PROXY
)
os.environ["no_proxy"] = (
    f"{os.environ.get('no_proxy', '')},{_LOCAL_NO_PROXY}"
    if os.environ.get("no_proxy")
    else _LOCAL_NO_PROXY
)

import gradio as gr

# Agent 系统导入
#from pdf_parse import DataProcess
from faiss_retriever import FaissRetriever
from bm25_retriever import BM25
from rerank_model import reRankLLM
from llm_model import get_llm_model
from config import LLM_BACKEND

from agent.config.model_config import ModelConfig
from agent.tools import RAGTool, TavilyTool
from agent.graph import build_agent_graph
from agent.state import AgentState
from agent.nodes.tool_executor import set_tools

from pdf_parse import load_knowledge_documents
# ============================================================
# 全局变量：存储已初始化的组件
# ============================================================
agent_graph = None


def initialize_system():
    """初始化 RAG 问答系统（只执行一次）"""
    global agent_graph

    if agent_graph is not None:
        return "系统已初始化"

    print("=" * 70)
    print("初始化 RAG 问答系统...")
    print("=" * 70)

    base = "."

    # 1. 加载 PDF 数据
    print("\n[1/6]  解析 PDF 文档...")
    #dp = DataProcess(pdf_path=base + "/data/train_a.pdf")
    #dp.ParseBlock(max_seq=1024)
    #dp.ParseBlock(max_seq=512)
    #dp.ParseAllPage(max_seq=256)
    #dp.ParseAllPage(max_seq=512)
    #dp.ParseOnePageWithRule(max_seq=256)
    #dp.ParseOnePageWithRule(max_seq=512)
    #data = dp.data
    #print(f"   共解析 {len(data)} 个文档块")


    pdf_dir = base + "/data/kb_docs"
    documents = load_knowledge_documents(
        kb_dir=pdf_dir,
        faq_path=base + "/data/faq_database.json",
    )
    print(f"data load ok, total chunks: {len(documents)}")

    # 2. 初始化 FAISS
    print("\n[2/6]  初始化 FAISS 检索器...")
    faiss_retriever = FaissRetriever(documents=documents)
    print("   FAISS 检索器已就绪")

    # 3. 初始化 BM25
    print("\n[3/6]  初始化 BM25 检索器...")
    bm25_retriever = BM25(documents)
    print("   BM25 检索器已就绪")

    # 4. 初始化 LLM
    print(f"\n[4/6]  初始化 LLM ({LLM_BACKEND})...")
    qwen7 = base + "/pre_train_model/Qwen-7B-Chat"
    llm = get_llm_model(model_path=qwen7, backend=LLM_BACKEND)
    print(f"   LLM 后端 {LLM_BACKEND} 已就绪")

    # 5. 初始化 Rerank
    print("\n[5/6]  初始化重排序模型...")
    rerank = reRankLLM()
    print("   重排序模型已就绪")

    # 6. 初始化 Agent 工具和图
    print("\n[6/6]   初始化 RAG 主链路...")

    rag_tool = RAGTool(
        faiss_retriever=faiss_retriever,
        bm25_retriever=bm25_retriever,
        rerank_model=rerank,
        llm=llm,
    )
    tavily_tool = TavilyTool(max_results=5) if ModelConfig.TAVILY_API_KEY else None

    set_tools(rag_tool, tavily_tool)
    agent_graph = build_agent_graph()

    print("\n" + "=" * 70)
    print(" 系统初始化完成！")
    print("=" * 70)

    return " 系统初始化成功！可以开始对话了。"


def _extract_text_content(content: Any) -> str:
    """
    将 Gradio 6 Chatbot 的 content 统一提取为纯文本，供 Agent 历史使用。
    支持：
    - str
    - OpenAI 风格 content blocks: [{"type": "text", "text": "..."}]
    - 其他类型转字符串
    """
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        parts.append(str(text))
                elif "content" in block:
                    text = block.get("content", "")
                    if text:
                        parts.append(str(text))
            elif block is not None:
                parts.append(str(block))
        return "\n".join(part for part in parts if part)

    return str(content)


def _normalize_chat_history(history: List[Dict[str, Any]] | None) -> List[Dict[str, str]]:
    """
    将 Gradio Chatbot 历史转换为 Agent 所需格式：
    [{"role": "user"|"assistant", "content": "..."}]
    """
    normalized: List[Dict[str, str]] = []

    for item in history or []:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue

        content = _extract_text_content(item.get("content"))
        if content:
            normalized.append({"role": role, "content": content})

    return normalized


def _format_trace_status(result: Dict[str, Any]) -> str:
    trace = result.get("trace", [])
    citations = result.get("citations", [])
    evidence_items = result.get("evidence_items", [])
    route_reason = result.get("route_reason", "")
    query_rewrite = result.get("query_rewrite", "")

    lines = []
    if route_reason:
        lines.append(f"-  路由依据: {route_reason}")
    if query_rewrite:
        lines.append(f"-  检索问题: {query_rewrite}")

    stage_names = [item.get("stage", "") for item in trace if item.get("stage")]
    if stage_names:
        lines.append(f"-  链路阶段: {' → '.join(stage_names)}")

    local_stage = next((item for item in trace if item.get("stage") == "local_rag"), None)
    if local_stage:
        lines.append(
            "-  本地检索: "
            f"召回 {local_stage.get('retrieved_count', 0)}，"
            f"重排 {local_stage.get('reranked_count', 0)}，"
            f"证据 {local_stage.get('evidence_count', 0)}"
        )

    web_stage = next((item for item in trace if item.get("stage") == "web_fresh"), None)
    if web_stage:
        lines.append(
            "-  时效检索: "
            f"结果 {web_stage.get('result_count', 0)}，"
            f"证据 {web_stage.get('evidence_count', 0)}"
        )

    composite_stage = next((item for item in trace if item.get("stage") == "composite_execution"), None)
    if composite_stage:
        lines.append(f"-  复合执行: 子问题 {composite_stage.get('sub_question_count', 0)} 个")
        for route_item in composite_stage.get("routes", []):
            lines.append(
                f"  - {route_item.get('index')}. "
                f"{route_item.get('route')} / {route_item.get('query_rewrite')}"
            )

    if evidence_items:
        lines.append("\n**证据摘要**")
        for item in evidence_items[:3]:
            fact = str(item.get("fact", "")).replace("\n", " ")
            if len(fact) > 90:
                fact = fact[:90] + "..."
            lines.append(f"- [{item.get('evidence_id')}] {fact}")

    if citations:
        lines.append("\n**引用来源**")
        for citation in citations[:5]:
            evidence_id = citation.get("evidence_id")
            title = citation.get("title") or "未命名来源"
            page = citation.get("page")
            url = citation.get("url")
            location = url if url else citation.get("source_file", "")
            if page is not None:
                location = f"{location} 第 {page} 页"
            lines.append(f"- [{evidence_id}] {title}: {location}")

    return "\n".join(lines)


def chat_with_agent(
    message: str,
    history: List[Dict[str, Any]] | None,
    session_id: str = "default",
) -> Generator[Tuple[str, str], None, None]:
    """
    与 Agent 对话的核心函数

    Args:
        message: 用户输入
        history: Gradio 6 聊天历史 [{"role": "...", "content": "..."}]
        session_id: 会话 ID（预留）

    Yields:
        (部分回复, 状态信息) 元组
    """
    _ = session_id

    if agent_graph is None:
        yield ("系统尚未初始化，请稍候...", " 系统未就绪")
        initialize_system()
        yield ("系统初始化完成！请重新发送您的问题。", " 系统已就绪")
        return

    conversation_history = _normalize_chat_history(history)

    initial_state: AgentState = {
        "user_question": message,
        "conversation_history": conversation_history,
        "sub_questions": [],
        "is_composite": False,
        "intent": "",
        "route": "",
        "route_reason": "",
        "query_rewrite": "",
        "plan": [],
        "rag_result": {},
        "tavily_result": None,
        "evidence_items": [],
        "citations": [],
        "draft_answer": "",
        "reasoning_steps": [],
        "reflection_count": 0,
        "quality_score": 0.0,
        "reflection_notes": [],
        "improvement_actions": [],
        "final_answer": "",
        "answer_source": "",
        "confidence": 0.0,
        "need_human": False,
        "metadata": {},
        "trace": [],
        "sub_results": [],
    }

    yield ("正在处理您的问题...", " 开始处理")

    try:
        start_time = time.time()
        result = agent_graph.invoke(initial_state)
        elapsed_time = time.time() - start_time

        final_answer = result.get("final_answer", "") or "抱歉，我暂时没有生成有效回复。"
        answer_source = result.get("answer_source", "unknown")
        confidence = result.get("confidence", 0.0)
        intent = result.get("intent", "unknown")
        route = result.get("route", "unknown")
        citations = result.get("citations", [])

        status_info = f"""
 **处理完成**
-  耗时: {elapsed_time:.2f}秒
-  意图: `{intent}`
-  路由: `{route}`
-  来源: `{answer_source}`"""

        if answer_source in ["local_rag", "refuse"]:
            status_info += f"\n-  置信度: {confidence:.2f}"
        elif answer_source == "web_fresh":
            status_info += f"\n-  时效检索置信度: {confidence:.2f}"

        status_info += f"""
-  引用数: {len(citations)}
"""
        trace_status = _format_trace_status(result)
        if trace_status:
            status_info += "\n" + trace_status + "\n"

        if result.get("need_human", False):
            status_info += "\n **建议咨询对应办事部门或老师**"

        current_answer = ""
        words = final_answer.split()

        if not words:
            yield (final_answer, status_info)
            return

        for i, word in enumerate(words):
            current_answer += word + " "
            if i % 3 == 0 or i == len(words) - 1:
                yield (current_answer.strip(), status_info)
                time.sleep(0.05)

        yield (final_answer, status_info)

    except Exception as e:
        error_msg = f" 处理出错: {str(e)}"
        yield (f"抱歉，处理您的问题时出现错误：{str(e)}", error_msg)
        import traceback

        traceback.print_exc()


def create_gradio_interface():
    """创建 Gradio 6 界面"""

    custom_css = """
    .status-box {
        background-color: #f0f8ff;
        border-left: 4px solid #4a90e2;
        padding: 15px;
        border-radius: 5px;
        font-family: 'Monaco', 'Courier New', monospace;
        font-size: 13px;
    }
    .chatbot {
        height: 600px;
    }
    """

    # 注意：Gradio 6 中 theme / css 应在 launch() 里传入
    with gr.Blocks(title="校园 RAG 问答演示") as demo:
        gr.Markdown(
            """
        #  校园 RAG 问答演示

        基于 **LangGraph + RAG** 的校园问答系统，具备以下能力：
        -  **多轮对话**：理解上下文，支持指代消解
        -  **混合检索**：FAISS + BM25 + Rerank
        -  **证据抽取**：答案必须基于可追溯证据
        -  **时效检索**：仅在 time_sensitive 路由中联网
        -  **动态路由**：simple_fact / complex_reasoning / time_sensitive

        ---
        """
        )

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    label="对话历史",
                    height=600,
                    elem_classes=["chatbot"],
                )

                with gr.Row():
                    msg = gr.Textbox(
                        label="输入消息",
                        placeholder="输入您的问题，例如：学生证补办在哪里办？",
                        lines=2,
                        scale=4,
                    )
                    submit_btn = gr.Button("发送", variant="primary", scale=1)

                with gr.Row():
                    clear_btn = gr.Button("清空对话", size="sm")
                    retry_btn = gr.Button("重试上一问", size="sm")

            with gr.Column(scale=1):
                status_box = gr.Markdown(
                    """
                    ### 系统状态

                    等待用户输入...
                    """,
                    elem_classes=["status-box"],
                )

                gr.Markdown(
                    """
                ---
                ### 使用提示

                **本地知识库问答：**
                - 学生证补办在哪里办？
                - 学分制怎么收费？
                - 成绩复核流程是什么？
                - 学籍异动有哪些办理要求？

                **时效问题：**
                - 本学期什么时候开始退补选？
                - 本周还能补办学生证吗？

                **多轮追问：**
                - 它什么时候可以办？
                - 还需要什么材料？
                """
                )

        gr.Markdown(
            """
        ---
        <center>
        <small>
        Powered by LangGraph + RAG |
        后端: {backend} |
        2025
        </small>
        </center>
        """.format(backend=LLM_BACKEND)
        )

        def respond(message: str, chat_history: List[Dict[str, Any]] | None):
            """处理用户输入（Gradio 6 messages 格式）"""
            message = (message or "").strip()
            chat_history = list(chat_history or [])

            if not message:
                yield chat_history, "请输入消息。"
                return

            working_history = chat_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": ""},
            ]

            yield working_history, "已发送，正在处理..."

            for partial_answer, status in chat_with_agent(message, chat_history):
                working_history[-1] = {"role": "assistant", "content": partial_answer}
                yield working_history, status

        msg.submit(
            respond,
            inputs=[msg, chatbot],
            outputs=[chatbot, status_box],
        ).then(
            lambda: "",
            outputs=[msg],
        )

        submit_btn.click(
            respond,
            inputs=[msg, chatbot],
            outputs=[chatbot, status_box],
        ).then(
            lambda: "",
            outputs=[msg],
        )

        clear_btn.click(
            lambda: ([], "对话已清空。"),
            outputs=[chatbot, status_box],
        )

        def retry_last(chat_history: List[Dict[str, Any]] | None):
            """重试最后一轮用户消息"""
            chat_history = list(chat_history or [])

            if not chat_history:
                return chat_history, "没有可重试的消息。"

            last_user_index = None
            for idx in range(len(chat_history) - 1, -1, -1):
                item = chat_history[idx]
                if isinstance(item, dict) and item.get("role") == "user":
                    last_user_index = idx
                    break

            if last_user_index is None:
                return chat_history, "没有找到可重试的用户消息。"

            last_user_msg = _extract_text_content(chat_history[last_user_index].get("content"))
            if not last_user_msg:
                return chat_history, "最后一条用户消息为空，无法重试。"

            base_history = chat_history[:last_user_index]
            working_history = base_history + [
                {"role": "user", "content": last_user_msg},
                {"role": "assistant", "content": ""},
            ]

            yield working_history, "正在重试最后一条消息..."

            for partial_answer, status in chat_with_agent(last_user_msg, base_history):
                working_history[-1] = {"role": "assistant", "content": partial_answer}
                yield working_history, status

        retry_btn.click(
            retry_last,
            inputs=[chatbot],
            outputs=[chatbot, status_box],
        )

    return demo, custom_css


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("启动校园 RAG 问答 Gradio 界面...")
    print("=" * 70 + "\n")

    initialize_system()

    demo, custom_css = create_gradio_interface()

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        show_error=True,
        quiet=False,
        theme=gr.themes.Soft(),
        css=custom_css,
        ssr_mode=False,
    )
