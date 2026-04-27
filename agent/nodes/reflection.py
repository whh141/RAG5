#!/usr/bin/env python
# coding: utf-8
"""
Reflection 节点。
评估当前答案质量，并在必要时触发同路由重试。
"""

import json
import re
from typing import Literal

from agent.config.model_config import ModelConfig
from agent.state import AgentState


MAX_REFLECTION_ROUNDS = 3
PASS_SCORE = 7.0


def reflection_node(state: AgentState) -> AgentState:
    """
    使用 LLM 评估答案质量，并在必要时生成改进建议。
    """
    reflection_count = int(state.get("reflection_count", 0)) + 1
    state["reflection_count"] = reflection_count

    evaluation_result = _evaluate_with_llm(
        question=state["user_question"],
        draft_answer=state.get("draft_answer", ""),
        answer_source=state.get("answer_source", ""),
        confidence=float(state.get("confidence", 0.0)),
        context=state,
    )

    quality_score = float(evaluation_result["score"])
    notes = [str(note) for note in evaluation_result.get("notes", []) if str(note).strip()]
    improvement_suggestions = [
        str(item) for item in evaluation_result.get("improvements", [])
        if str(item).strip()
    ]

    state["quality_score"] = quality_score
    state["reflection_notes"] = state.get("reflection_notes", []) + notes
    state["improvement_actions"] = improvement_suggestions if quality_score < PASS_SCORE else []
    state["trace"] = state.get("trace", [])
    state["trace"].append(
        {
            "stage": "reflection",
            "reflection_count": reflection_count,
            "quality_score": quality_score,
            "notes": notes,
            "improvement_actions": state["improvement_actions"],
        }
    )

    print(f"  [Reflection] 轮次: {reflection_count}/{MAX_REFLECTION_ROUNDS}")
    print(f"  [Reflection] 质量分数: {quality_score:.1f}/10")
    if notes:
        print(f"  [Reflection] 评估意见: {', '.join(notes[:2])}")
    if state["improvement_actions"]:
        print(f"  [Reflection] 改进建议: {', '.join(state['improvement_actions'][:2])}")

    return state


def should_continue(state: AgentState) -> Literal["finalize", "retry"]:
    """
    决定是否继续 Reflection。
    """
    answer_source = state.get("answer_source", "")
    route = state.get("route", "")
    quality_score = float(state.get("quality_score", 0.0))
    reflection_count = int(state.get("reflection_count", 0))

    if answer_source in {"refuse", "composite"} or route == "composite":
        print(f"  [Decision] 当前来源 {answer_source or route} 不进入重试，直接结束")
        return "finalize"

    if quality_score >= PASS_SCORE:
        print(f"  [Decision] 质量达标 ({quality_score:.1f}/10)，结束 Reflection")
        return "finalize"

    if reflection_count >= MAX_REFLECTION_ROUNDS:
        print(f"  [Decision] 达到最大重试次数 ({MAX_REFLECTION_ROUNDS}/{MAX_REFLECTION_ROUNDS})，强制结束")
        return "finalize"

    print(f"  [Decision] 质量不足 ({quality_score:.1f}/10)，进入下一轮重试")
    improvement_actions = state.get("improvement_actions", [])
    if improvement_actions:
        print(f"  [Improvement] 改进措施: {', '.join(improvement_actions[:2])}")
    return "retry"


def _evaluate_with_llm(
    question: str,
    draft_answer: str,
    answer_source: str,
    confidence: float,
    context: AgentState,
) -> dict:
    """
    使用 LLM 评估答案质量并生成改进建议。
    """
    try:
        llm = ModelConfig.get_reflection_llm()
        confidence_str = f"{confidence:.2f}"
        route = context.get("route", "")
        query_rewrite = context.get("query_rewrite", "")
        citation_count = len(context.get("citations", []))
        evidence_count = len(context.get("evidence_items", []))
        reasoning_steps = context.get("reasoning_steps", [])
        prompt = f"""你是校园问答系统的答案质检助手。请评估下面这条回答是否真正回答了用户问题。

用户问题：{question}
检索问题：{query_rewrite}
当前路由：{route}
草稿答案：{draft_answer}
答案来源：{answer_source}
检索置信度：{confidence_str}
证据条数：{evidence_count}
引用条数：{citation_count}
结构化推理链：
{json.dumps(reasoning_steps, ensure_ascii=False) if reasoning_steps else "无"}

评估维度：
1. 相关性：是否直接回答用户问题
2. 准确性：是否与当前路由和证据来源一致，是否存在臆测
3. 完整性：是否覆盖地点、时间、材料、费用、流程等关键要素
4. 可用性：回答是否清楚、可执行
5. 推理一致性：如果是 complex_reasoning，推理链是否完整且与最终答案一致

评分规则：
- 分数范围只能是 0 到 10。
- 如果答案和用户问题明显不匹配，分数不高于 5 分。
- 如果答案缺少关键要素或表述模糊，应该降低分数。
- 对 `local_rag`，改进建议应优先围绕本地检索问题改写，不要建议切换到联网检索。
- 对 `web_fresh`，改进建议应优先围绕联网搜索词收紧、官方来源优先、来源表达清晰。
- 如果当前答案是对越界问题的正确拒答，通常应给 8 分以上，且 improvements 返回空数组。
- 如果分数大于等于 7，improvements 必须返回空数组。

请严格输出 JSON：
{{
  "score": 7.5,
  "notes": ["评价1", "评价2"],
  "improvements": ["建议1", "建议2"]
}}"""
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            raise ValueError("Reflection 未返回 JSON object")

        result = json.loads(json_match.group())
        score = max(0.0, min(10.0, float(result.get("score", 5.0))))
        notes = result.get("notes", ["已完成评估"])
        improvements = result.get("improvements", [])
        if not isinstance(notes, list):
            notes = [str(notes)]
        if not isinstance(improvements, list):
            improvements = [str(improvements)]

        return {
            "score": score,
            "notes": notes,
            "improvements": improvements if score < PASS_SCORE else [],
        }
    except Exception as exc:
        print(f"  [Warning] Reflection 评估失败，使用规则回退: {exc}")
        return _fallback_evaluation(
            answer=draft_answer,
            source=answer_source,
            confidence=confidence,
            context=context,
        )


def _fallback_evaluation(
    answer: str,
    source: str,
    confidence: float,
    context: AgentState,
) -> dict:
    """
    当 LLM 评估失败时使用的规则回退。
    """
    route = context.get("route", "")
    citations = context.get("citations", [])
    reasoning_steps = context.get("reasoning_steps", [])
    notes: list[str] = []
    improvements: list[str] = []

    if source == "local_rag":
        base_score = 7.0 + confidence * 2.0
        if confidence >= 0.75:
            notes.append("本地检索置信度较高")
        else:
            notes.append("本地检索置信度一般")
            improvements.append("明确业务名称后重试检索")
        if len(citations) < 2:
            improvements.append("补充办理时间、地点或材料等关键检索词")
    elif source == "web_fresh":
        base_score = 6.4 + min(len(citations), 3) * 0.4
        notes.append("答案来自联网检索，需要关注来源可靠性")
        if len(citations) < 2:
            improvements.append("收紧联网检索关键词")
            improvements.append("优先选择学校或官方来源")
    elif source == "refuse" and route == "refuse":
        base_score = 8.5
        notes.append("当前问题已按越界规则正确拒答")
    elif source == "composite":
        base_score = 7.2 if answer.strip() else 3.5
        notes.append("复合问题已完成子问题合成")
    else:
        base_score = 4.0
        notes.append("未形成稳定可用答案")
        if route == "retrieve_local":
            improvements.append("明确业务名称后重试检索")
        elif route == "retrieve_web":
            improvements.append("收紧联网检索关键词")

    if len(answer.strip()) < 20 and source not in {"refuse", "composite"}:
        base_score -= 1.5
        notes.append("答案较短，信息不足")
        if route == "retrieve_local":
            improvements.append("补充更完整的关键信息")
        elif route == "retrieve_web":
            improvements.append("补充可验证的来源信息")

    if "证据不足" in answer or "无法基于当前知识库回答" in answer:
        base_score = min(base_score, 5.0)
        notes.append("答案显示当前证据不足")
        if route == "retrieve_local":
            improvements.append("换一种本地检索表述")

    if context.get("intent") == "complex_reasoning":
        if not reasoning_steps:
            base_score = min(base_score, 5.5)
            notes.append("复杂推理问题缺少结构化推理链")
            improvements.append("补充分步推理并绑定证据")
        else:
            notes.append("复杂推理问题已生成结构化推理链")

    quality_score = max(0.0, min(10.0, base_score))
    deduped_improvements = list(dict.fromkeys(improvements))
    return {
        "score": quality_score,
        "notes": notes,
        "improvements": deduped_improvements if quality_score < PASS_SCORE else [],
    }
