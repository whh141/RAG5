#!/usr/bin/env python
# coding: utf-8
"""
复合问题拆解节点。
把同一条用户消息中的多个问题拆成有序子问题，后续按子问题逐个路由执行。
"""

import re

from agent.state import AgentState


QUESTION_END_PATTERN = re.compile(r"(?<=[？?])")
LIST_PREFIX_PATTERN = re.compile(r"^\s*(?:[-*•]|\d+[\.、)]|[一二三四五六七八九十]+[、.])\s*")


def question_decompose_node(state: AgentState) -> AgentState:
    question = state["user_question"]
    sub_questions = _split_questions(question)

    state["sub_questions"] = sub_questions
    state["is_composite"] = len(sub_questions) > 1
    state["sub_results"] = []
    state["trace"] = state.get("trace", [])
    state["trace"].append(
        {
            "stage": "question_decompose",
            "is_composite": state["is_composite"],
            "sub_question_count": len(sub_questions),
            "sub_questions": sub_questions,
        }
    )

    if state["is_composite"]:
        print(f"  [Decompose] 复合问题数量: {len(sub_questions)}")
    else:
        print("  [Decompose] 单问题")
    return state


def route_after_decompose(state: AgentState) -> str:
    return "composite_execution" if state.get("is_composite", False) else "intent_classify"


def _split_questions(question: str) -> list[str]:
    normalized = str(question or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    raw_parts: list[str] = []
    for line in normalized.split("\n"):
        line = _clean_part(line)
        if not line:
            continue
        raw_parts.extend(_split_line(line))

    sub_questions = [_clean_part(part) for part in raw_parts]
    return [part for part in sub_questions if part]


def _split_line(line: str) -> list[str]:
    pieces = [part.strip() for part in QUESTION_END_PATTERN.split(line) if part.strip()]
    if len(pieces) > 1:
        return pieces
    return [line]


def _clean_part(text: str) -> str:
    cleaned = LIST_PREFIX_PATTERN.sub("", text.strip())
    return cleaned.strip(" \t")
