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
