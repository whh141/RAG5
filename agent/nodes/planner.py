#!/usr/bin/env python
# coding: utf-8
"""
规划节点。
路由器已经给出唯一执行路径，本节点将其固化为执行计划。
在 Reflection 重试时，仅允许在当前路由内改写检索问题，不切换路径。
"""

import json
import re

from agent.config.model_config import ModelConfig
from agent.state import AgentState


ROUTE_TO_PLAN = {
    "retrieve_local": ["local_rag"],
    "retrieve_web": ["web_fresh"],
    "refuse": ["refuse"],
}
ROUTE_CHANGE_SUGGESTION_TERMS = (
    "切换路由",
    "重新路由",
    "联网检索",
    "改为联网",
    "更适合联网",
    "retrieve_web",
    "web_fresh",
    "换到联网",
)
META_TEXT_PREFIXES = (
    "改写后的问题",
    "改写后问题",
    "可以改写为",
    "建议改写为",
    "输出",
    "结果",
)


def planning_node(state: AgentState) -> AgentState:
    route = state["route"]
    if route not in ROUTE_TO_PLAN:
        raise ValueError(f"未知路由：{route}")

    reflection_count = int(state.get("reflection_count", 0))
    improvement_actions = list(state.get("improvement_actions", []))
    input_query_rewrite = state.get("query_rewrite", "") or state["user_question"]
    rewrite_result = {
        "query": input_query_rewrite,
        "attempted": False,
        "success": False,
        "reason": "not_attempted",
        "raw_output": "",
    }
    route_change_suggestion_ignored = _has_route_change_suggestion(improvement_actions)
    if reflection_count > 0 and improvement_actions:
        rewrite_result = _rewrite_query_for_retry(
            question=state["user_question"],
            current_query=input_query_rewrite,
            history=state.get("conversation_history", []),
            route=route,
            improvement_actions=improvement_actions,
        )
        query_rewrite = rewrite_result["query"]
    else:
        query_rewrite = input_query_rewrite

    plan = ROUTE_TO_PLAN[route]
    state["plan"] = plan
    state["query_rewrite"] = query_rewrite
    state["trace"] = state.get("trace", [])
    state["trace"].append(
        {
            "stage": "planner",
            "route": route,
            "plan": plan,
            "reflection_count": reflection_count,
            "input_query_rewrite": input_query_rewrite,
            "query_rewrite": query_rewrite,
            "rewrite_attempted": rewrite_result["attempted"],
            "rewrite_success": rewrite_result["success"],
            "rewrite_reason": rewrite_result["reason"],
            "route_change_suggestion_ignored": route_change_suggestion_ignored,
        }
    )

    if reflection_count > 0 and improvement_actions:
        print(f"  [Plan] Reflection 重试第 {reflection_count} 轮")
        print(f"  [Plan] 改进建议: {', '.join(improvement_actions[:2])}")
        print(f"  [Plan] 重写检索问题: {query_rewrite}")
        print(f"  [Plan] 重写状态: {rewrite_result['reason']}")
        if route_change_suggestion_ignored:
            print("  [Plan] 检测到跨路由建议，已按唯一执行路径约束忽略")
    print(f"  [Plan] 唯一执行路径: {plan}")
    return state


def _rewrite_query_for_retry(
    question: str,
    current_query: str,
    history: list[dict],
    route: str,
    improvement_actions: list[str],
) -> dict:
    if route == "refuse":
        return _rewrite_result(
            query=current_query or question,
            attempted=False,
            success=False,
            reason="refuse_route_no_rewrite",
        )

    try:
        llm = ModelConfig.get_planner_llm()
        history_text = _format_recent_user_questions(history, max_turns=3)
        prompt = f"""你是校园问答系统的检索重写助手。当前系统已经确定路由，不允许切换路径。

用户原问题：{question}
当前检索问题：{current_query}
当前路由：{route}
最近用户问题历史：
{history_text}
Reflection 改进建议：
{improvement_actions}

改写要求：
1. 只输出 JSON object，不要 Markdown，不要解释。
2. 保持当前路由语义不变：retrieve_local 只面向本地校园知识库；retrieve_web 只面向联网检索。
3. 只做必要的实体补全、关键词收紧或问题聚焦，不要改变业务名词。
4. 不要把“学生证”改成“校园卡”，不要把“成绩复核”改成“成绩申诉”。
5. 如果当前检索问题已经足够好，原样返回。
6. 不要接受或执行“切换路由”“改为联网检索”等跨路由建议。
7. query_rewrite 必须简洁，不能输出解释性文字。

JSON schema：
{{
  "query_rewrite": "重写后的检索问题"
}}

现在请直接输出 JSON："""
        response = llm.invoke(prompt)
        raw_output = response.content.strip() if hasattr(response, "content") else str(response).strip()
        try:
            parsed = _parse_rewrite_output(raw_output)
        except ValueError as exc:
            return _rewrite_result(
                query=current_query or question,
                attempted=True,
                success=False,
                reason=str(exc),
                raw_output=raw_output,
            )
        validation_error = _validate_rewrite_query(parsed, question, current_query)
        if validation_error:
            return _rewrite_result(
                query=current_query or question,
                attempted=True,
                success=False,
                reason=validation_error,
                raw_output=raw_output,
            )
        return _rewrite_result(
            query=parsed,
            attempted=True,
            success=True,
            reason="llm_rewrite_valid",
            raw_output=raw_output,
        )
    except Exception as exc:
        print(f"  [Warning] Reflection 重写失败: {exc}")
        return _rewrite_result(
            query=current_query or question,
            attempted=True,
            success=False,
            reason=f"llm_error:{type(exc).__name__}",
        )


def _rewrite_result(
    query: str,
    attempted: bool,
    success: bool,
    reason: str,
    raw_output: str = "",
) -> dict:
    return {
        "query": query,
        "attempted": attempted,
        "success": success,
        "reason": reason,
        "raw_output": raw_output,
    }


def _parse_rewrite_output(raw_output: str) -> str:
    text = str(raw_output or "").strip()
    if not text:
        raise ValueError("empty_output")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc

    if not isinstance(data, dict):
        raise ValueError("json_not_object")
    query = str(data.get("query_rewrite", "")).strip()
    if not query:
        raise ValueError("empty_query_rewrite")
    return query


def _validate_rewrite_query(query: str, question: str, current_query: str) -> str:
    if len(query) < 2:
        return "too_short"
    max_allowed = min(200, max(80, max(len(question), len(current_query)) * 4))
    if len(query) > max_allowed:
        return "too_long"
    if _is_meta_text(query):
        return "meta_text"
    return ""


def _is_meta_text(query: str) -> bool:
    text = str(query or "").strip()
    if "```" in text:
        return True
    normalized = re.sub(r"^[\s\"'“”‘’：:]+", "", text)
    return any(normalized.startswith(prefix) for prefix in META_TEXT_PREFIXES)


def _has_route_change_suggestion(improvement_actions: list[str]) -> bool:
    joined = " ".join(str(item) for item in improvement_actions)
    return any(term in joined for term in ROUTE_CHANGE_SUGGESTION_TERMS)


def _format_recent_user_questions(history: list[dict], max_turns: int = 3) -> str:
    questions: list[str] = []
    for message in reversed(history or []):
        if message.get("role") != "user":
            continue
        content = str(message.get("content", "")).strip()
        if content:
            questions.append(content)
        if len(questions) >= max_turns:
            break

    if not questions:
        return "无"
    return "\n".join(f"用户: {content}" for content in reversed(questions))
