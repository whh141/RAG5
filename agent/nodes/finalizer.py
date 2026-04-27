#!/usr/bin/env python
# coding: utf-8
"""
最终化节点
输出带引用来源的最终答案
"""

from agent.state import AgentState


def finalize_answer_node(state: AgentState) -> AgentState:
    """
    最终化节点
    
    将 draft_answer 和引用来源合成为 final_answer。
    """
    draft_answer = state["draft_answer"].strip()
    citations = state.get("citations", [])

    if citations:
        state["final_answer"] = f"{draft_answer}\n\n参考来源：\n{_format_citations(citations)}"
    else:
        state["final_answer"] = draft_answer

    state["trace"] = state.get("trace", [])
    state["trace"].append(
        {
            "stage": "finalize",
            "answer_source": state.get("answer_source", "unknown"),
            "citation_count": len(citations),
            "final_answer_length": len(state["final_answer"]),
        }
    )
    
    print("  [Finalize] 最终答案已生成")
    print(f"  [Finalize] 来源: {state.get('answer_source', 'unknown')}")
    print(f"  [Finalize] 引用数: {len(citations)}")
    
    return state


def _format_citations(citations: list[dict]) -> str:
    lines = []
    seen = set()

    for citation in citations:
        evidence_id = citation.get("evidence_id")
        title = citation.get("title") or "未命名来源"
        source_file = citation.get("source_file")
        source_type = citation.get("source_type", "")
        page = citation.get("page")
        chunk_id = citation.get("chunk_id")
        url = citation.get("url")

        if url:
            key = (evidence_id, url)
            location = url
        else:
            key = (evidence_id, source_file, page, chunk_id)
            location_parts = []
            if source_file:
                location_parts.append(str(source_file))
            if page is not None:
                location_parts.append(f"第 {page} 页")
            if chunk_id is not None:
                location_parts.append(f"片段 {chunk_id}")
            location = "，".join(location_parts) if location_parts else source_type

        if key in seen:
            continue
        seen.add(key)

        prefix = f"[{evidence_id}]" if evidence_id is not None else f"[{len(lines) + 1}]"
        lines.append(f"{prefix} {title}：{location}")

    return "\n".join(lines)
