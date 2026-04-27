#!/usr/bin/env python
# coding: utf-8
"""
Agent 状态定义。
主链路以 RAG 问答为核心：严格路由、唯一执行路径、证据抽取、引用校验。
"""

from typing import TypedDict, List, Dict, Optional, Any


class AgentState(TypedDict):
    """
    Agent 工作流状态。
    """
    # === 输入 ===
    user_question: str              # 用户原始问题
    conversation_history: List[Dict]  # 对话历史: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    sub_questions: List[str]        # 复合问题拆解后的子问题
    is_composite: bool              # 当前输入是否包含多个子问题
    
    # === 意图路由与规划 ===
    intent: str                     # simple_fact, complex_reasoning, time_sensitive, ood
    route: str                      # retrieve_local, retrieve_web, refuse
    route_reason: str               # 路由原因
    query_rewrite: str              # 查询重写后的问题
    plan: List[str]                 # 唯一执行路径
    
    # === 工具调用结果 ===
    rag_result: Dict[str, Any]      # RAG 检索结果
    tavily_result: Optional[Dict]   # 网络搜索结果
    evidence_items: List[Dict[str, Any]]  # 结构化证据事实
    citations: List[Dict[str, Any]]       # 最终引用
    
    # === 答案生成 ===
    draft_answer: str               # 草稿答案
    reasoning_steps: List[Dict[str, Any]]  # 复杂推理问题的结构化推理链

    # === Reflection 反思 ===
    reflection_count: int           # 反思轮数
    quality_score: float            # 答案质量分数 (0-10)
    reflection_notes: List[str]     # 反思意见
    improvement_actions: List[str]  # 改进建议
    
    # === 输出 ===
    final_answer: str               # 最终答案
    answer_source: str              # 答案来源: local_rag, web_fresh, refuse
    confidence: float               # 置信度
    need_human: bool                # 是否需要转人工
    
    # === 元数据 ===
    metadata: Dict[str, Any]        # 其他元信息
    trace: List[Dict[str, Any]]     # 全链路可视化轨迹
    sub_results: List[Dict[str, Any]]  # 复合问题每个子问题的执行结果


def format_conversation_history(history: List[Dict], max_turns: int = 5) -> str:
    """
    格式化对话历史为文本形式
    
    Args:
        history: 对话历史列表
        max_turns: 最多保留的对话轮数
    
    Returns:
        格式化后的对话历史文本
    """
    if not history:
        return ""
    
    # 只保留最近 N 轮对话
    recent_history = history[-(max_turns * 2):]  # 每轮包含 user + assistant
    
    formatted = []
    for msg in recent_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        if role == "user":
            formatted.append(f"用户: {content}")
        elif role == "assistant":
            formatted.append(f"助手: {content}")
    
    return "\n".join(formatted)
