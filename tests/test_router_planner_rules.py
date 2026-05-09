#!/usr/bin/env python
# coding: utf-8

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.nodes.intent_classifier import (  # noqa: E402
    _apply_route_contract,
    _extract_business_name,
    _has_explicit_realtime,
    _is_global_web_query,
    _precheck_deterministic_route,
)
from agent.nodes.planner import (  # noqa: E402
    _format_recent_user_questions,
    _has_route_change_suggestion,
    _is_meta_text,
    _parse_rewrite_output,
    _validate_rewrite_query,
    planning_node,
)


class RouterRuleTests(unittest.TestCase):
    def test_social_query_precheck_refuses_without_llm(self):
        result = _precheck_deterministic_route("你好")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "ood")
        self.assertEqual(result["route"], "refuse")
        self.assertEqual(result["decision_source"], "rule_precheck")

    def test_global_news_and_campus_news_are_distinguished(self):
        self.assertTrue(_is_global_web_query("今天的国际新闻是什么？"))
        self.assertFalse(_is_global_web_query("校园新闻在哪里看？"))

    def test_now_location_confirmation_is_not_forced_to_realtime(self):
        self.assertFalse(_has_explicit_realtime("现在学生证补办还是去明德楼吗？"))
        base = {
            "intent": "simple_fact",
            "route": "retrieve_local",
            "reason": "model",
            "query_rewrite": "现在学生证补办还是去明德楼吗",
        }
        result = _apply_route_contract(dict(base), "现在学生证补办还是去明德楼吗？", "")
        self.assertEqual(result["intent"], "simple_fact")
        self.assertEqual(result["route"], "retrieve_local")
        self.assertEqual(result["decision_source"], "llm")

    def test_realtime_service_query_is_forced_to_web(self):
        self.assertTrue(_has_explicit_realtime("本周还能补办学生证吗？"))

    def test_business_name_cleanup_and_parallel_service(self):
        self.assertEqual(_extract_business_name("请问办理学生证需要什么材料"), "学生证")
        self.assertEqual(_extract_business_name("学生证和校园卡在哪办？"), "")

    def test_complex_policy_query_promotes_only_intent_not_route(self):
        base = {
            "intent": "simple_fact",
            "route": "retrieve_local",
            "reason": "model",
            "query_rewrite": "毕业论文抽检主要看什么",
        }
        result = _apply_route_contract(dict(base), "毕业论文抽检主要看什么？", "")
        self.assertEqual(result["intent"], "complex_reasoning")
        self.assertEqual(result["route"], "retrieve_local")
        self.assertEqual(result["rule_name"], "complex_local_policy_query")


class PlannerRuleTests(unittest.TestCase):
    def test_rewrite_json_output_is_parsed(self):
        raw = json.dumps({"query_rewrite": "学生证补办办理时间"}, ensure_ascii=False)
        self.assertEqual(_parse_rewrite_output(raw), "学生证补办办理时间")

    def test_valid_query_with_explain_word_is_not_rejected(self):
        reason = _validate_rewrite_query("解释一下成绩复核流程", "解释一下成绩复核流程", "成绩复核流程")
        self.assertEqual(reason, "")

    def test_meta_text_is_rejected(self):
        self.assertTrue(_is_meta_text("改写后的问题：学生证补办材料"))

    def test_route_change_suggestion_is_detected(self):
        self.assertTrue(_has_route_change_suggestion(["建议改为联网检索"]))

    def test_planner_history_uses_only_user_messages(self):
        history = [
            {"role": "user", "content": "学生证补办在哪里办？"},
            {"role": "assistant", "content": "明德楼B座"},
        ]
        formatted = _format_recent_user_questions(history)
        self.assertIn("学生证补办在哪里办？", formatted)
        self.assertNotIn("明德楼", formatted)

    def test_planning_without_reflection_does_not_rewrite(self):
        state = {
            "user_question": "学生证补办在哪里办？",
            "conversation_history": [],
            "route": "retrieve_local",
            "query_rewrite": "学生证补办地点",
            "reflection_count": 0,
            "improvement_actions": [],
            "trace": [],
        }
        result = planning_node(state)
        trace = result["trace"][-1]
        self.assertEqual(result["plan"], ["local_rag"])
        self.assertFalse(trace["rewrite_attempted"])
        self.assertEqual(trace["rewrite_reason"], "not_attempted")


if __name__ == "__main__":
    unittest.main()
