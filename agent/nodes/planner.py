#!/usr/bin/env python
# coding: utf-8
"""
规划节点。
路由器已经给出唯一执行路径，本节点将其固化为执行计划。
在 Reflection 重试时，仅允许在当前路由内改写检索问题，不切换路径。
"""

from agent.config.model_config import ModelConfig
from agent.state import AgentState, format_conversation_history


ROUTE_TO_PLAN = {
    "retrieve_local": ["local_rag"],
    "retrieve_web": ["web_fresh"],
    "refuse": ["refuse"],
}


def planning_node(state: AgentState) -> AgentState:
    route = state["route"]
    if route not in ROUTE_TO_PLAN:
        raise ValueError(f"未知路由：{route}")

    reflection_count = int(state.get("reflection_count", 0))
    improvement_actions = list(state.get("improvement_actions", []))
    if reflection_count > 0 and improvement_actions:
        query_rewrite = _rewrite_query_for_retry(
            question=state["user_question"],
            current_query=state.get("query_rewrite", "") or state["user_question"],
            history=state.get("conversation_history", []),
            route=route,
            improvement_actions=improvement_actions,
        )
    else:
        query_rewrite = state.get("query_rewrite", "") or state["user_question"]

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
            "query_rewrite": query_rewrite,
        }
    )

    if reflection_count > 0 and improvement_actions:
        print(f"  [Plan] Reflection 重试第 {reflection_count} 轮")
        print(f"  [Plan] 改进建议: {', '.join(improvement_actions[:2])}")
        print(f"  [Plan] 重写检索问题: {query_rewrite}")
    print(f"  [Plan] 唯一执行路径: {plan}")
    return state


def _rewrite_query_for_retry(
    question: str,
    current_query: str,
    history: list[dict],
    route: str,
    improvement_actions: list[str],
) -> str:
    if route == "refuse":
        return current_query or question

    try:
        llm = ModelConfig.get_planner_llm()
        history_text = format_conversation_history(history, max_turns=3) or "无"
        prompt = f"""你是校园问答系统的检索重写助手。当前系统已经确定路由，不允许切换路径。

用户原问题：{question}
当前检索问题：{current_query}
当前路由：{route}
最近对话历史：
{history_text}
Reflection 改进建议：
{improvement_actions}

改写要求：
1. 只能输出一个检索问题，不要解释。
2. 保持当前路由语义不变：retrieve_local 只面向本地校园知识库；retrieve_web 只面向联网检索。
3. 只做必要的实体补全、关键词收紧或问题聚焦，不要改变业务名词。
4. 不要把“学生证”改成“校园卡”，不要把“成绩复核”改成“成绩申诉”。
5. 如果当前检索问题已经足够好，原样返回。
6. 输出必须简洁，长度不超过原问题的 4 倍。

现在请直接输出重写后的检索问题："""
        response = llm.invoke(prompt)
        rewritten = response.content.strip() if hasattr(response, "content") else str(response).strip()
        if not rewritten or len(rewritten) < 2:
            return current_query or question
        if len(rewritten) > max(len(question), len(current_query)) * 4:
            return current_query or question
        invalid_patterns = ("改写", "解释", "原因", "输出", "原样返回")
        if any(pattern in rewritten for pattern in invalid_patterns):
            return current_query or question
        return rewritten
    except Exception as exc:
        print(f"  [Warning] Reflection 重写失败: {exc}")
        return current_query or question
