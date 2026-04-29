#!/usr/bin/env python
# coding: utf-8
"""
答案合成节点。
RAG 和联网工具已经完成证据抽取、答案生成与引用校验；本节点只汇总结果。
"""

from agent.state import AgentState


def synthesize_answer_node(state: AgentState) -> AgentState:
    answer_source = state.get("answer_source", "")

    if answer_source == "local_rag":
        draft_answer = state["rag_result"]["answer"]
    elif answer_source == "web_fresh":
        draft_answer = state["tavily_result"]["answer"]
    elif answer_source == "composite":
        draft_answer = _synthesize_composite_answer(state.get("sub_results", []))
    elif answer_source == "refuse":
        draft_answer = state.get("metadata", {}).get("refuse_answer", "").strip() or (
            "该问题不属于当前校园教学服务知识库的回答范围，"
            "系统不会基于无关知识生成答案。"
        )
    else:
        raise ValueError(f"未知答案来源：{answer_source}")

    state["draft_answer"] = draft_answer
    state["need_human"] = False
    state["trace"].append(
        {
            "stage": "synthesize",
            "answer_source": answer_source,
            "answer_length": len(draft_answer),
        }
    )

    print(f"  [Synthesize] 来源: {answer_source}")
    print(f"  [Synthesize] 答案长度: {len(draft_answer)}")
    return state


def _synthesize_composite_answer(sub_results: list[dict]) -> str:
    if not sub_results:
        raise ValueError("复合问题缺少子问题执行结果")

    sections: list[str] = []
    for item in sub_results:
        index = item["index"]
        question = item["question"]
        answer = str(item["answer"]).strip()
        status = item.get("status", "success")
        if not answer:
            if status == "error":
                error = str(item.get("error", "")).strip() or "未知错误"
                answer = f"该子问题执行失败：{error}"
            else:
                raise ValueError(f"复合问题第 {index} 个子问题答案为空")
        sections.append(f"{index}. {question}\n{answer}")

    return "\n\n".join(sections)
