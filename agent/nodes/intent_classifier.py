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
    "时政",
    "政策新闻",
    "国家政策",
)
GLOBAL_WEB_NEWS_TERMS = ("新闻",)
LOCAL_NEWS_EXCLUSION_TERMS = (
    "校园新闻",
    "校内新闻",
    "学校新闻",
    "山东大学新闻",
    "本科教学新闻",
    "教务新闻",
)
TIME_PREFIXES = ("今天", "今日", "明天", "本周", "这周", "本星期", "本月", "本学期", "今年", "当前", "现在", "目前", "最新")
NOW_STATUS_TERMS = ("是否", "能不能", "可以办", "能办", "还能", "还开放", "开放", "最新", "截止", "通知")
EXTRA_SLOT_TERMS = ("材料", "费用", "流程", "地点", "在哪", "哪里", "窗口", "条件")
ACTION_PREFIXES = ("办理", "申请", "补办", "查询", "领取", "更换", "挂失", "注销")
COMPLEX_LOCAL_PATTERNS = (
    "休学期满后什么时候申请复学",
    "哪些情况会被退学处理",
    "退学处理条件",
    "毕业论文抽检主要看什么",
    "毕业论文抽检主要看哪些方面",
    "哪些情况会影响学士学位授予",
    "哪些行为会影响学士学位授予",
    "影响学士学位授予",
    "保留学籍期间还交学费",
    "提前毕业还要继续交专业注册学费",
    "毕业论文有学术不端会怎样",
    "毕业论文学术不端后果",
    "课程教学大纲一般包括哪些内容",
    "课程教学大纲通常包括哪些内容",
    "实验课有哪些基本纪律和安全要求",
    "实验课上学生要遵守哪些基本规则",
    "文科实践创新行动方案强调什么培养路径",
    "文科实践创新行动方案强调哪些培养路径",
)
SERVICE_SUFFIX_PATTERN = re.compile(
    r"(?:在哪里|在哪|到哪里|去哪|去哪里|怎么办|怎么做|如何办理|如何|"
    r"办理时间|什么时候.*|几点.*|需要经过.*|需要什么|需要哪些|"
    r"需要多久.*|需要多长时间.*|一般.*|要多久.*|多久.*|多长时间.*|材料|费用|流程|"
    r"是否开放|还能.*|可以.*|吗|呢|？|\?)"
)
VERB_OBJECT_PATTERN = re.compile(r"(补办|办理|申请|领取|更换|挂失|注销)([\u4e00-\u9fa5A-Za-z0-9]+)")
PARALLEL_SERVICE_PATTERN = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9]+(?:和|与|及|、)[\u4e00-\u9fa5A-Za-z0-9]+")


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
            "decision_source": route_result.get("decision_source", ""),
            "rule_applied": route_result.get("rule_applied", False),
            "rule_name": route_result.get("rule_name", ""),
            "original_intent": route_result.get("original_intent", ""),
            "original_route": route_result.get("original_route", ""),
            "original_query_rewrite": route_result.get("original_query_rewrite", ""),
        }
    )

    print(f"  [Router] intent={state['intent']} route={state['route']}")
    print(f"  [Router] query={state['query_rewrite']}")
    return state


def _route_with_llm(question: str, history: list) -> dict:
    history_text = ""
    last_user_question = _last_user_question(history)
    precheck = _precheck_deterministic_route(question)
    if precheck:
        return precheck

    llm = ModelConfig.get_intent_llm()

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
- “现在”“目前”只有与是否开放、还能办理、最新通知、截止时间等动态状态语义共现时，才属于 time_sensitive；固定地点、固定材料、固定流程确认优先按本地知识库判断。
- “今天的国家新闻”“国内新闻”“国际新闻”“社会新闻”等通用新闻问题属于 time_sensitive，必须按当前问题联网检索，禁止继承上一轮校园业务名。
- “校园新闻”“山东大学新闻”“本科教学新闻”“教务新闻”等校内信息查询不要直接按通用新闻处理，应结合问题语义判断。
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


def _precheck_deterministic_route(question: str) -> dict | None:
    if _is_social_query(question):
        return _make_rule_result(
            intent="ood",
            route="refuse",
            reason="用户输入是社交问候或寒暄，不属于知识库检索问答请求。",
            query_rewrite=str(question or "").strip(),
            rule_name="social_query_precheck",
        )

    if _is_global_web_query(question):
        return _make_rule_result(
            intent="time_sensitive",
            route="retrieve_web",
            reason="用户询问通用新闻或外部实时信息，需要按当前问题联网检索。",
            query_rewrite=str(question or "").strip(),
            rule_name="global_web_query_precheck",
        )

    return None


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
    original = dict(result)
    if _is_social_query(question):
        return _make_rule_result(
            intent="ood",
            route="refuse",
            reason="用户输入是社交问候或寒暄，不属于知识库检索问答请求。",
            query_rewrite=question.strip(),
            rule_name="social_query_contract",
            original=original,
        )

    if _is_global_web_query(question):
        return _make_rule_result(
            intent="time_sensitive",
            route="retrieve_web",
            reason="用户询问通用新闻或外部实时信息，需要按当前问题联网检索。",
            query_rewrite=question.strip(),
            rule_name="global_web_query_contract",
            original=original,
        )

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
        query_rewrite = _rewrite_realtime_query(question, service_name, resolved_query)
        return _make_rule_result(
            intent="time_sensitive",
            route="retrieve_web",
            reason="用户问题包含明确实时状态语义，需要执行时效检索。",
            query_rewrite=query_rewrite,
            rule_name="explicit_realtime_service_query",
            original=original,
        )

    if service_name and routine_time:
        return _make_rule_result(
            intent="simple_fact",
            route="retrieve_local",
            reason="用户询问常规办理时间，属于本地知识库事实查询。",
            query_rewrite=_rewrite_routine_time_query(question, service_name, resolved_query),
            rule_name="routine_time_service_query",
            original=original,
        )

    if _should_promote_to_complex_local(question, resolved_query, result):
        return _make_rule_result(
            intent="complex_reasoning",
            route="retrieve_local",
            reason="用户问题涉及制度条件、后果或综合要求归纳，需要整合本地知识库片段回答。",
            query_rewrite=resolved_query or result["query_rewrite"],
            rule_name="complex_local_policy_query",
            original=original,
        )

    expected_route = ROUTE_BY_INTENT[result["intent"]]
    if result["route"] != expected_route:
        raise ValueError(
            f"intent 与 route 不一致：intent={result['intent']}, "
            f"route={result['route']}, expected={expected_route}"
        )
    return _with_decision_metadata(result)


def _make_rule_result(
    intent: str,
    route: str,
    reason: str,
    query_rewrite: str,
    rule_name: str,
    original: dict | None = None,
) -> dict:
    result = {
        "intent": intent,
        "route": route,
        "reason": reason,
        "query_rewrite": query_rewrite,
        "decision_source": "rule_precheck" if original is None else "llm_with_rule_adjustment",
        "rule_applied": True,
        "rule_name": rule_name,
        "rule_reason": reason,
        "original_intent": original.get("intent", "") if original else "",
        "original_route": original.get("route", "") if original else "",
        "original_query_rewrite": original.get("query_rewrite", "") if original else "",
    }
    expected_route = ROUTE_BY_INTENT[result["intent"]]
    if result["route"] != expected_route:
        raise ValueError(
            f"规则路由结果不一致：intent={result['intent']}, "
            f"route={result['route']}, expected={expected_route}"
        )
    return result


def _with_decision_metadata(result: dict) -> dict:
    result = dict(result)
    result.setdefault("decision_source", "llm")
    result.setdefault("rule_applied", False)
    result.setdefault("rule_name", "")
    result.setdefault("rule_reason", "")
    result.setdefault("original_intent", "")
    result.setdefault("original_route", "")
    result.setdefault("original_query_rewrite", "")
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
    text = str(question or "").strip()
    if not text:
        return False
    if "现在" in text or "目前" in text:
        return any(term in text for term in NOW_STATUS_TERMS)
    return any(term in text for term in REALTIME_TERMS if term not in {"现在", "目前"})


def _has_routine_time_intent(question: str) -> bool:
    return any(term in question for term in ROUTINE_TIME_TERMS)


def _is_global_web_query(question: str) -> bool:
    text = str(question or "").strip()
    if any(term in text for term in LOCAL_NEWS_EXCLUSION_TERMS):
        return False
    if any(term in text for term in GLOBAL_WEB_TERMS):
        return True
    return any(term in text for term in GLOBAL_WEB_NEWS_TERMS)


def _is_social_query(question: str) -> bool:
    text = str(question or "").strip().lower()
    if not text:
        return False
    normalized = re.sub(r"[\s，。！？!?,、；;：:\"'“”‘’（）()【】\[\]<>《》]+", "", text)
    return normalized in SOCIAL_QUERIES


def _rewrite_realtime_query(question: str, service_name: str, model_query: str = "") -> str:
    if _query_keeps_service(model_query, service_name):
        return model_query.strip()
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


def _rewrite_routine_time_query(question: str, service_name: str, model_query: str = "") -> str:
    text = str(question or "").strip()
    if any(term in text for term in EXTRA_SLOT_TERMS) and _query_keeps_service(model_query, service_name):
        return model_query.strip()
    return f"{service_name}办理时间"


def _query_keeps_service(query: str, service_name: str) -> bool:
    query = str(query or "").strip()
    service_name = str(service_name or "").strip()
    return bool(query and service_name and service_name in query)


def _should_promote_to_complex_local(question: str, resolved_query: str, result: dict) -> bool:
    if result.get("intent") != "simple_fact" or result.get("route") != "retrieve_local":
        return False
    text = f"{question} {resolved_query}".replace("？", "").replace("?", "")
    return any(pattern in text for pattern in COMPLEX_LOCAL_PATTERNS)


def _extract_business_name(question: str) -> str:
    text = _clean_question_text(question)
    if not text:
        return ""
    if _is_context_dependent_question(text):
        return ""

    service = SERVICE_SUFFIX_PATTERN.split(text, maxsplit=1)[0]
    service = service.strip(" ，。！？?；;：:")
    service = _normalize_service_name(_remove_time_prefix(service))
    if _has_parallel_service(service):
        return ""
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
    for prefix in TIME_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _normalize_service_name(text: str) -> str:
    service = text.strip(" ，。！？?；;：:")
    service = _strip_action_prefix(service)
    for marker in ("的时间和材料", "时间和材料", "的时间和", "时间和", "的材料", "材料"):
        if service.endswith(marker):
            service = service[: -len(marker)]
    for suffix in ("办理流程", "申请流程"):
        if service.endswith(suffix):
            service = service[: -len(suffix)]
    if service.endswith("手续办理"):
        service = service[:-2]
    return _strip_action_prefix(service.strip(" ，。！？?；;：:"))


def _strip_action_prefix(text: str) -> str:
    service = str(text or "").strip()
    changed = True
    while changed:
        changed = False
        for prefix in ACTION_PREFIXES:
            if service.startswith(prefix) and len(service) > len(prefix) + 1:
                service = service[len(prefix):]
                changed = True
                break
    return service


def _has_parallel_service(text: str) -> bool:
    return bool(PARALLEL_SERVICE_PATTERN.fullmatch(str(text or "").strip()))


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
