#!/usr/bin/env python
# coding: utf-8
"""
动态路由节点。
主分类聚焦 simple_fact / complex_reasoning / time_sensitive，
仅在明显无法归入三类时才使用 ood 作为辅助异常标签。
"""

import json
import re
from agent.state import AgentState, format_conversation_history
from agent.config.model_config import ModelConfig


VALID_INTENTS = {"simple_fact", "complex_reasoning", "time_sensitive", "ood"}
VALID_ROUTES = {"retrieve_local", "retrieve_web", "refuse"}
ROUTE_BY_INTENT = {
    "simple_fact": "retrieve_local",
    "complex_reasoning": "retrieve_local",
    "time_sensitive": "retrieve_web",
    "ood": "refuse",
}
SOCIAL_QUERIES = {
    "你好",
    "你好啊",
    "你好呀",
    "您好",
    "您好啊",
    "您好呀",
    "嗨",
    "嗨呀",
    "哈喽",
    "hello",
    "hi",
    "hey",
    "在吗",
    "在不在",
    "有人吗",
    "谢谢",
    "感谢",
    "多谢",
    "辛苦了",
    "再见",
    "拜拜",
    "早上好",
    "中午好",
    "晚上好",
}
FOLLOWUP_PRONOUNS = ("它", "这个", "该业务", "这个业务", "该流程", "这个流程", "该事项", "这个事项")
ROUTINE_TIME_TERMS = (
    "办理时间",
    "什么时候可以办",
    "什么时候能办",
    "什么时候可以办理",
    "什么时候办理",
    "何时办理",
    "几点办理",
    "窗口工作时间",
    "工作时间",
    "上班时间",
)
CONTEXT_DEPENDENT_PATTERNS = (
    "需要经过哪些部门",
    "需要哪些部门",
    "经过哪些部门",
    "需要什么材料",
    "需要哪些材料",
    "要带什么",
    "要多久",
    "多久",
    "多长时间",
)
CONTEXT_DEPENDENT_PREFIXES = ("需要", "要不要", "要带", "多久", "多长时间", "一般", "本学期", "本周", "今天", "现在", "目前")
REALTIME_TERMS = (
    "今天",
    "今日",
    "明天",
    "本周",
    "这周",
    "本星期",
    "本月",
    "本学期",
    "今年",
    "当前",
    "现在",
    "目前",
    "实时",
    "最新",
    "是否开放",
    "还开放",
    "还能办",
    "还能办理",
    "还能补办",
    "放假期间",
    "寒假",
    "暑假",
    "节假日",
)
GLOBAL_WEB_TERMS = (
    "国家新闻",
    "国内新闻",
    "国际新闻",
    "社会新闻",
    "新闻",
    "时政",
    "政策新闻",
    "国家政策",
)
SERVICE_SUFFIX_PATTERN = re.compile(
    r"(?:在哪里|在哪|到哪里|去哪|去哪里|怎么办|怎么做|如何办理|如何|"
    r"办理时间|什么时候.*|几点.*|需要经过.*|需要什么|需要哪些|"
    r"需要多久.*|需要多长时间.*|一般.*|要多久.*|多久.*|多长时间.*|材料|费用|流程|"
    r"是否开放|还能.*|可以.*|吗|呢|？|\?)"
)
VERB_OBJECT_PATTERN = re.compile(r"(补办|办理|申请|领取|更换|挂失|注销)([\u4e00-\u9fa5A-Za-z0-9]+)")


def intent_classify_node(state: AgentState) -> AgentState:
    """
    对用户问题进行动态路由。
    """
    question = state["user_question"]
    history = state.get("conversation_history", [])

    route_result = _route_with_llm(question, history)

    state["intent"] = route_result["intent"]
    state["route"] = route_result["route"]
    state["route_reason"] = route_result["reason"]
    state["query_rewrite"] = route_result["query_rewrite"]
    state["metadata"] = state.get("metadata", {})
    state["metadata"]["route_result"] = route_result
    state["trace"] = state.get("trace", [])
    state["trace"].append(
        {
            "stage": "router",
            "intent": state["intent"],
            "route": state["route"],
            "query_rewrite": state["query_rewrite"],
            "reason": state["route_reason"],
        }
    )

    print(f"  [Router] intent={state['intent']} route={state['route']}")
    print(f"  [Router] query={state['query_rewrite']}")
    return state


def _route_with_llm(question: str, history: list) -> dict:
    llm = ModelConfig.get_intent_llm()

    history_text = ""
    last_user_question = _last_user_question(history)
    if history:
        history_text = (
            "\n\n对话历史:\n"
            f"{format_conversation_history(history, max_turns=3)}"
        )

    prompt = f"""你是校园 RAG 问答系统的动态路由器。请根据用户问题输出唯一执行路径。

系统主分类只有三类：
1. simple_fact：能从校园知识库中直接查到的事实型问题，例如地点、电话、材料、费用、学分、字数、次数、常规办理时间。
2. complex_reasoning：需要整合多个校园知识片段的制度解释、条件判断、流程归纳、对比分析问题。
3. time_sensitive：涉及今天、本周、本学期、今年、当前开放状态、最新通知、最新新闻等需要联网获取动态信息的问题。

辅助异常标签：
4. ood：只有当问题明显无法归入上述三类，且与当前问答任务无关时才允许使用。

可选 route：
1. retrieve_local：simple_fact 和 complex_reasoning 必须使用。
2. retrieve_web：time_sensitive 必须使用。
3. refuse：ood 必须使用。

硬性规则：
- 只输出 JSON，不要 Markdown，不要解释。
- 主路由判断优先围绕 simple_fact / complex_reasoning / time_sensitive 三类展开。
- 只有在问题明显无法归入三类时，才允许输出 ood。
- route 必须与 intent 对应：simple_fact/complex_reasoning -> retrieve_local，time_sensitive -> retrieve_web，ood -> refuse。
- query_rewrite 必须是独立、明确、适合检索的问题。
- query_rewrite 禁止为空；如果当前问题已经明确，必须原样复制当前用户问题。
- “办理时间是什么”“什么时候可以办理”“几点办理”“窗口工作时间”等常规办事时间问题属于 simple_fact，走 retrieve_local。
- 只有出现“今天”“本周”“这周”“本学期”“今年”“当前”“现在是否开放”“最新通知”“放假期间”等需要实时状态的信息，才属于 time_sensitive。
- “今天的国家新闻”“国内新闻”“国际新闻”“社会新闻”等通用新闻问题属于 time_sensitive，必须按当前问题联网检索，禁止继承上一轮校园业务名。
- 多轮追问里的“它”“这个业务”“该流程”必须优先继承上一轮用户问题中的业务名。
- 最近一轮用户问题是：{last_user_question or "无"}。
- 如果当前问题包含“它”“这个”“该业务”等代词，query_rewrite 必须从“最近一轮用户问题”继承业务名，禁止从助手回答中提取窗口号、楼宇、校区、办公室作为业务名。
- query_rewrite 必须保留业务名，例如“学生证补办办理时间”，不要改写成“B01业务办理时间”“明德楼业务办理时间”等窗口或地点名称。
- 不要把“学生证”改成“校园卡”，不要把“成绩复核”改成“成绩申诉”。
- 优先保证三分类动态路由稳定；不要把常规校园知识问题误判为 ood。{history_text}

用户问题：{question}

JSON schema：
{{
  "intent": "simple_fact | complex_reasoning | time_sensitive | ood",
  "route": "retrieve_local | retrieve_web | refuse",
  "reason": "一句话说明路由依据",
  "query_rewrite": "非空的独立检索问题"
}}

示例：
对话历史：
用户：学生证补办在哪里办？
助手：济南校区在中心校区明德楼B座1楼师生服务大厅B01窗口。
用户问题：它什么时候可以办？
输出：
{{"intent":"simple_fact","route":"retrieve_local","reason":"询问学生证补办的常规办理时间，属于本地知识库事实查询。","query_rewrite":"学生证补办办理时间"}}

用户问题：本周还能补办学生证吗？
输出：
{{"intent":"time_sensitive","route":"retrieve_web","reason":"询问学生证补办在本周是否开放，属于需要动态状态确认的时效信息问题。","query_rewrite":"本周学生证补办业务是否开放"}}

用户问题：成绩复核和缓考申请在条件与流程上有什么区别？
输出：
{{"intent":"complex_reasoning","route":"retrieve_local","reason":"需要综合多个校园制度片段进行条件和流程对比，属于复杂推理型问题。","query_rewrite":"成绩复核和缓考申请的条件与流程区别"}}
"""

    response = llm.invoke(prompt)
    response_text = response.content if hasattr(response, "content") else str(response)
    result = _parse_strict_json(response_text)
    result = _normalize_route_fields(result)
    return _apply_route_contract(result, question, last_user_question)


def _parse_strict_json(response_text: str) -> dict:
    text = response_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"路由器未输出严格 JSON：{text[:120]}") from exc


def _normalize_route_fields(result: dict) -> dict:
    required = {"intent", "route", "reason", "query_rewrite"}
    missing = required - set(result)
    if missing:
        raise ValueError(f"路由器 JSON 缺少字段：{sorted(missing)}")

    intent = str(result["intent"]).strip()
    route = str(result["route"]).strip()
    query_rewrite = str(result["query_rewrite"]).strip()
    reason = str(result["reason"]).strip()

    if intent not in VALID_INTENTS:
        raise ValueError(f"非法 intent：{intent}")
    if route not in VALID_ROUTES:
        raise ValueError(f"非法 route：{route}")
    if not query_rewrite:
        raise ValueError("query_rewrite 不能为空")
    if not reason:
        raise ValueError("reason 不能为空")

    return {
        "intent": intent,
        "route": route,
        "reason": reason,
        "query_rewrite": query_rewrite,
    }


def _apply_route_contract(result: dict, question: str, last_user_question: str) -> dict:
    if _is_social_query(question):
        return {
            "intent": "ood",
            "route": "refuse",
            "reason": "用户输入是社交问候或寒暄，不属于知识库检索问答请求。",
            "query_rewrite": question.strip(),
        }

    if _is_global_web_query(question):
        return {
            "intent": "time_sensitive",
            "route": "retrieve_web",
            "reason": "用户询问通用新闻或外部实时信息，需要按当前问题联网检索。",
            "query_rewrite": question.strip(),
        }

    resolved_query = _resolve_followup_query(
        question=question,
        last_user_question=last_user_question,
        model_query_rewrite=result["query_rewrite"],
    )
    explicit_realtime = _has_explicit_realtime(question)
    routine_time = _has_routine_time_intent(question) or _has_routine_time_intent(resolved_query)
    question_service = _extract_business_name(question)
    history_service = _extract_business_name(last_user_question)
    resolved_service = _extract_business_name(resolved_query)
    if history_service and (not question_service or _is_context_dependent_question(question)):
        service_name = history_service
    else:
        service_name = question_service or resolved_service or history_service

    if service_name and explicit_realtime:
        query_rewrite = _rewrite_realtime_query(question, service_name)
        return {
            "intent": "time_sensitive",
            "route": "retrieve_web",
            "reason": "用户问题包含明确实时状态词，需要执行时效检索。",
            "query_rewrite": query_rewrite,
        }

    if service_name and routine_time:
        return {
            "intent": "simple_fact",
            "route": "retrieve_local",
            "reason": "用户询问常规办理时间，属于本地知识库事实查询。",
            "query_rewrite": f"{service_name}办理时间",
        }

    expected_route = ROUTE_BY_INTENT[result["intent"]]
    if result["route"] != expected_route:
        raise ValueError(
            f"intent 与 route 不一致：intent={result['intent']}, "
            f"route={result['route']}, expected={expected_route}"
        )
    return result


def _last_user_question(history: list) -> str:
    for message in reversed(history or []):
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return ""


def _resolve_followup_query(question: str, last_user_question: str, model_query_rewrite: str) -> str:
    if _is_global_web_query(question):
        return question.strip()

    if not _is_followup_question(question):
        return model_query_rewrite.strip() or question.strip()

    service_name = _extract_business_name(last_user_question)
    if not service_name:
        return model_query_rewrite.strip() or question.strip()

    if _has_explicit_realtime(question):
        return _rewrite_realtime_query(question, service_name)
    if _has_routine_time_intent(question):
        return f"{service_name}办理时间"

    normalized = question.strip()
    for pronoun in FOLLOWUP_PRONOUNS:
        normalized = normalized.replace(pronoun, service_name)
    return normalized


def _is_followup_question(question: str) -> bool:
    return any(term in question for term in FOLLOWUP_PRONOUNS)


def _has_explicit_realtime(question: str) -> bool:
    return any(term in question for term in REALTIME_TERMS)


def _has_routine_time_intent(question: str) -> bool:
    return any(term in question for term in ROUTINE_TIME_TERMS)


def _is_global_web_query(question: str) -> bool:
    text = str(question or "").strip()
    return any(term in text for term in GLOBAL_WEB_TERMS)


def _is_social_query(question: str) -> bool:
    text = str(question or "").strip().lower()
    if not text:
        return False
    normalized = re.sub(r"[\s，。！？!?,、；;：:\"'“”‘’（）()【】\[\]<>《》]+", "", text)
    return normalized in SOCIAL_QUERIES


def _rewrite_realtime_query(question: str, service_name: str) -> str:
    if "今天" in question or "今日" in question:
        return f"今天{service_name}业务是否开放"
    if "本周" in question or "这周" in question or "本星期" in question:
        return f"本周{service_name}业务是否开放"
    if "本月" in question:
        return f"本月{service_name}业务是否开放"
    if "本学期" in question:
        return f"本学期{service_name}业务是否开放"
    if "今年" in question:
        return f"今年{service_name}业务是否开放"
    return f"{service_name}业务当前是否开放"


def _extract_business_name(question: str) -> str:
    text = _clean_question_text(question)
    if not text:
        return ""
    if _is_context_dependent_question(text):
        return ""

    service = SERVICE_SUFFIX_PATTERN.split(text, maxsplit=1)[0]
    service = service.strip(" ，。！？?；;：:")
    service = _normalize_service_name(_remove_time_prefix(service))
    if len(service) >= 2:
        return service

    normalized = _normalize_verb_object_service(text)
    if normalized:
        return normalized
    return ""


def _normalize_verb_object_service(text: str) -> str:
    match = VERB_OBJECT_PATTERN.search(text)
    if not match:
        return ""

    action = match.group(1)
    obj = match.group(2)
    obj = SERVICE_SUFFIX_PATTERN.split(obj, maxsplit=1)[0]
    obj = obj.strip(" ，。！？?；;：:")
    obj = _remove_time_prefix(obj)
    if len(obj) < 2:
        return ""
    return f"{obj}{action}"


def _remove_time_prefix(text: str) -> str:
    for prefix in ("今天", "今日", "本周", "这周", "本星期", "本月", "本学期", "今年", "当前", "现在", "目前", "最新"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _normalize_service_name(text: str) -> str:
    service = text.strip(" ，。！？?；;：:")
    for marker in ("的时间和材料", "时间和材料", "的时间和", "时间和", "的材料", "材料"):
        if service.endswith(marker):
            service = service[: -len(marker)]
    for suffix in ("办理流程", "申请流程"):
        if service.endswith(suffix):
            service = service[: -len(suffix)]
    if service.endswith("手续办理"):
        service = service[:-2]
    return service


def _clean_question_text(question: str) -> str:
    text = str(question or "").strip()
    text = re.sub(r"^(请问|咨询一下|我想问一下|想问一下)", "", text)
    text = text.replace("业务", "")
    return text.strip()


def _is_context_dependent_question(question: str) -> bool:
    text = str(question or "").strip()
    if _is_followup_question(text):
        return True
    if any(text.startswith(prefix) for prefix in CONTEXT_DEPENDENT_PREFIXES):
        return True
    return any(text.startswith(pattern) for pattern in CONTEXT_DEPENDENT_PATTERNS)
