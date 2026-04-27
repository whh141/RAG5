#!/usr/bin/env python
# coding: utf-8
"""
LangGraph 工作流定义
"""

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    question_decompose_node,
    route_after_decompose,
    intent_classify_node,
    planning_node,
    composite_execution_node,
    tool_execution_node,
    reflection_node,
    should_continue,
    synthesize_answer_node,
)
from agent.nodes.finalizer import finalize_answer_node


def build_agent_graph() -> StateGraph:
    """
    构建 Agent 工作流图
    
    流程:
    START → Decompose → Router/Composite → Retrieval/Refuse → Synthesize
          → Reflection → Finalize / Retry Planning → END

    设计原则:
    - 单个子问题只产生一条执行路径，不做失败后的路径切换。
    - 复合问题先拆成子问题，再对子问题逐个执行唯一链路。
    - 本地 RAG 问题不会在证据不足时转联网。
    - Reflection 只允许在当前路由内重试，不切换来源路径。
    """
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("question_decompose", question_decompose_node)
    workflow.add_node("intent_classify", intent_classify_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("tool_execution", tool_execution_node)
    workflow.add_node("composite_execution", composite_execution_node)
    workflow.add_node("synthesize", synthesize_answer_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("finalize", finalize_answer_node)
    
    # 设置入口点
    workflow.set_entry_point("question_decompose")
    
    # 定义边
    workflow.add_conditional_edges(
        "question_decompose",
        route_after_decompose,
        {
            "intent_classify": "intent_classify",
            "composite_execution": "composite_execution",
        },
    )
    workflow.add_edge("intent_classify", "planning")
    workflow.add_edge("planning", "tool_execution")
    workflow.add_edge("tool_execution", "synthesize")
    workflow.add_edge("composite_execution", "synthesize")
    workflow.add_edge("synthesize", "reflection")
    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "finalize": "finalize",
            "retry": "planning",
        },
    )
    workflow.add_edge("finalize", END)
    
    # 编译
    return workflow.compile()


def save_graph_visualization(graph, output_path: str = "./images/agent_workflow.png"):
    """
    保存工作流可视化图
    
    Args:
        graph: 编译后的 LangGraph
        output_path: 输出路径
    """
    from pathlib import Path
    
    print("\n" + "=" * 70)
    print(" 生成 Agent 工作流图")
    print("=" * 70)
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        png_data = graph.get_graph().draw_mermaid_png()
        with open(output_file, "wb") as f:
            f.write(png_data)
        print(f" 工作流图已保存: {output_file}")
        return True
    except Exception as e:
        print(f" 生成工作流图失败: {e}")
        print(f"   提示: 需要安装 pygraphviz 或 graphviz")
        return False
    finally:
        print("=" * 70)
