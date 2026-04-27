#!/usr/bin/env python
# coding: utf-8
"""
工具执行节点。
按规划执行唯一工具路径。
"""

import copy
import re

from agent.state import AgentState
from agent.nodes.intent_classifier import _route_with_llm
from agent.nodes.planner import ROUTE_TO_PLAN


rag_tool = None
tavily_tool = None


def set_tools(rag, tavily):
    """设置全局工具实例。"""
    global rag_tool, tavily_tool
    rag_tool = rag
    tavily_tool = tavily


def tool_execution_node(state: AgentState) -> AgentState:
    plan = state["plan"]
    query = state["query_rewrite"]
    intent = state["intent"]

    execution = _execute_plan(plan=plan, query=query, intent=intent)

    state["rag_result"] = {}
    state["tavily_result"] = None
    state["evidence_items"] = []
    state["citations"] = []
    state["reasoning_steps"] = []
    state["answer_source"] = execution["answer_source"]
    state["confidence"] = execution["confidence"]

    if execution["answer_source"] == "local_rag":
        state["rag_result"] = execution["raw_result"]
        state["reasoning_steps"] = execution.get("reasoning_steps", []) or []
    elif execution["answer_source"] == "web_fresh":
        state["tavily_result"] = execution["raw_result"]

    state["evidence_items"] = execution["evidence_items"]
    state["citations"] = execution["citations"]
    state["trace"].append(execution["trace"])
    return state


def composite_execution_node(state: AgentState) -> AgentState:
    sub_questions = state.get("sub_questions", [])
    if len(sub_questions) < 2:
        raise ValueError("复合执行节点需要至少两个子问题")

    working_history = list(state.get("conversation_history", []))
    sub_results: list[dict] = []
    all_evidence: list[dict] = []
    all_citations: list[dict] = []
    citation_offset = 0

    for index, sub_question in enumerate(sub_questions, start=1):
        try:
            route_result = _route_with_llm(sub_question, working_history)
            plan = ROUTE_TO_PLAN[route_result["route"]]
            print(
                f"  [Composite] 子问题 {index}: "
                f"{route_result['intent']} {route_result['route']} {route_result['query_rewrite']}"
            )

            execution = _execute_plan(
                plan=plan,
                query=route_result["query_rewrite"],
                intent=route_result["intent"],
            )
            execution = _renumber_execution_references(execution, citation_offset)
            citation_offset += len(execution["citations"])

            sub_result = {
                "index": index,
                "question": sub_question,
                "intent": route_result["intent"],
                "route": route_result["route"],
                "route_reason": route_result["reason"],
                "query_rewrite": route_result["query_rewrite"],
                "plan": plan,
                "status": "success",
                "error": None,
                "answer_source": execution["answer_source"],
                "answer": execution["answer"],
                "confidence": execution["confidence"],
                "evidence_items": execution["evidence_items"],
                "reasoning_steps": execution.get("reasoning_steps", []) if execution["answer_source"] == "local_rag" else [],
                "citations": execution["citations"],
                "trace": execution["trace"],
            }
            sub_results.append(sub_result)
            all_evidence.extend(execution["evidence_items"])
            all_citations.extend(execution["citations"])

            working_history.append({"role": "user", "content": route_result["query_rewrite"]})
            working_history.append({"role": "assistant", "content": execution["answer"]})
        except Exception as exc:
            print(f"  [Composite] 子问题 {index} 执行失败: {exc}")
            sub_results.append(
                {
                    "index": index,
                    "question": sub_question,
                    "intent": route_result["intent"] if "route_result" in locals() else "",
                    "route": route_result["route"] if "route_result" in locals() else "",
                    "route_reason": route_result["reason"] if "route_result" in locals() else "",
                    "query_rewrite": route_result["query_rewrite"] if "route_result" in locals() else sub_question,
                    "plan": plan if "plan" in locals() else [],
                    "status": "error",
                    "error": str(exc),
                    "answer_source": route_result["route"] if "route_result" in locals() else "error",
                    "answer": f"该子问题执行失败：{str(exc)}",
                    "confidence": 0.0,
                    "evidence_items": [],
                    "reasoning_steps": [],
                    "citations": [],
                    "trace": {
                        "stage": "composite_sub_error",
                        "error": str(exc),
                    },
                }
            )
        finally:
            route_result = None
            plan = None

    state["intent"] = "composite"
    state["route"] = "composite"
    state["route_reason"] = "用户一次输入包含多个子问题，系统按子问题独立路由执行。"
    state["query_rewrite"] = "；".join(item["query_rewrite"] for item in sub_results)
    state["plan"] = ["composite"]
    state["sub_results"] = sub_results
    state["reasoning_steps"] = []
    state["evidence_items"] = all_evidence
    state["citations"] = all_citations
    state["answer_source"] = "composite"
    state["confidence"] = _average_confidence(sub_results)
    state["trace"].append(
        {
            "stage": "composite_execution",
            "sub_question_count": len(sub_results),
            "routes": [
                {
                    "index": item["index"],
                    "status": item.get("status", "success"),
                    "intent": item["intent"],
                    "route": item["route"],
                    "query_rewrite": item["query_rewrite"],
                    "answer_source": item["answer_source"],
                }
                for item in sub_results
            ],
            "error_count": sum(1 for item in sub_results if item.get("status") == "error"),
            "citation_count": len(all_citations),
        }
    )
    return state


def _execute_plan(plan: list[str], query: str, intent: str) -> dict:
    if plan == ["local_rag"]:
        if rag_tool is None:
            raise RuntimeError("RAG 工具未初始化")
        print("  [Tool] 执行本地 RAG")
        rag_result = rag_tool.answer(query=query, intent=intent)
        return {
            "answer_source": "local_rag",
            "answer": rag_result["answer"],
            "raw_result": rag_result,
            "evidence_items": rag_result["evidence_items"],
            "reasoning_steps": rag_result.get("reasoning_steps", []) or [],
            "citations": rag_result["citations"],
            "confidence": rag_result["confidence"],
            "trace": {
                "stage": "local_rag",
                "retrieved_count": rag_result["retrieved_count"],
                "reranked_count": rag_result["reranked_count"],
                "evidence_count": len(rag_result["evidence_items"]),
                "reasoning_step_count": len(rag_result.get("reasoning_steps", []) or []),
                "citations": rag_result["citations"],
            },
        }

    if plan == ["web_fresh"]:
        if tavily_tool is None:
            raise RuntimeError("联网搜索工具未初始化")
        print("  [Tool] 执行时效检索")
        tavily_result = tavily_tool.search_query(query)
        return {
            "answer_source": "web_fresh",
            "answer": tavily_result["answer"],
            "raw_result": tavily_result,
            "evidence_items": tavily_result["evidence_items"],
            "citations": tavily_result["citations"],
            "confidence": tavily_result["confidence"],
            "trace": {
                "stage": "web_fresh",
                "result_count": len(tavily_result["results"]),
                "evidence_count": len(tavily_result["evidence_items"]),
                "citations": tavily_result["citations"],
            },
        }

    if plan == ["refuse"]:
        print("  [Tool] 执行越界拒答")
        answer = "该问题不属于当前校园教学服务知识库的回答范围，系统不会基于无关知识生成答案。"
        return {
            "answer_source": "refuse",
            "answer": answer,
            "raw_result": {},
            "evidence_items": [],
            "citations": [],
            "confidence": 1.0,
            "trace": {
                "stage": "refuse",
                "reason": "",
            },
        }

    raise ValueError(f"非法执行计划：{plan}")


def _renumber_execution_references(execution: dict, offset: int) -> dict:
    if offset == 0 or not execution["citations"]:
        return execution

    id_map = {
        citation["evidence_id"]: offset + index
        for index, citation in enumerate(execution["citations"], start=1)
    }
    copied = copy.deepcopy(execution)
    copied["answer"] = _rewrite_answer_citations(copied["answer"], id_map)
    copied["citations"] = _renumber_items(copied["citations"], id_map)
    copied["evidence_items"] = _renumber_items(copied["evidence_items"], id_map)
    copied["reasoning_steps"] = _renumber_reasoning_steps(copied.get("reasoning_steps", []), id_map)
    if "raw_result" in copied and isinstance(copied["raw_result"], dict):
        copied["raw_result"]["reasoning_steps"] = copied["reasoning_steps"]
    copied["trace"]["citations"] = copied["citations"]
    return copied


def _rewrite_answer_citations(answer: str, id_map: dict[int, int]) -> str:
    def replace(match: re.Match) -> str:
        old_id = int(match.group(1))
        if old_id not in id_map:
            raise ValueError(f"答案引用了不在最终引用中的证据编号: {old_id}")
        return f"[{id_map[old_id]}]"

    return re.sub(r"(?:\[|【)(\d+)(?:\]|】)", replace, answer)


def _renumber_items(items: list[dict], id_map: dict[int, int]) -> list[dict]:
    renumbered: list[dict] = []
    for item in items:
        copied_item = copy.deepcopy(item)
        evidence_id = copied_item.get("evidence_id")
        if evidence_id in id_map:
            copied_item["evidence_id"] = id_map[evidence_id]
            renumbered.append(copied_item)
    return renumbered


def _renumber_reasoning_steps(steps: list[dict], id_map: dict[int, int]) -> list[dict]:
    renumbered: list[dict] = []
    for step in steps or []:
        copied_step = copy.deepcopy(step)
        evidence_ids = copied_step.get("evidence_ids", [])
        if isinstance(evidence_ids, list):
            copied_step["evidence_ids"] = [id_map.get(evidence_id, evidence_id) for evidence_id in evidence_ids]
        renumbered.append(copied_step)
    return renumbered


def _average_confidence(sub_results: list[dict]) -> float:
    successful = [
        item for item in sub_results
        if item.get("status", "success") == "success"
    ]
    if not successful:
        return 0.0
    return sum(float(item.get("confidence", 0.0)) for item in successful) / len(successful)
