#!/usr/bin/env python
# coding: utf-8
"""
时效信息检索工具。
仅由 route=retrieve_web 触发，不作为本地 RAG 的失败补救路径。
"""

import json
import re
from typing import Dict, List
import requests

from agent.config.model_config import ModelConfig


class TavilyTool:
    """
    实时网络搜索工具。
    """

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._init_search_tool()

    def _init_search_tool(self):
        if not ModelConfig.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY 未配置，无法执行时效检索")

        self.api_url = "https://api.tavily.com/search"
        self.session = requests.Session()
        self.session.trust_env = False
        print("Tavily 搜索工具已初始化")

    def search_query(self, query: str) -> Dict:
        results = self._search(query)
        if not results:
            raise ValueError("联网检索未返回结果")

        evidence_items = self._extract_web_evidence(results)
        claims = self._generate_claims(query, evidence_items)
        answer = self._compose_answer(claims)
        citations = self._verify_citations(answer, evidence_items)

        return {
            "answer": answer,
            "results": results,
            "evidence_items": evidence_items,
            "citations": citations,
            "claims": claims,
            "confidence": min(1.0, len(evidence_items) / 3),
            "source": "web_fresh",
            "query": query,
        }

    def _search(self, query: str) -> List[Dict]:
        payload = {
            "api_key": ModelConfig.TAVILY_API_KEY,
            "query": query,
            "max_results": self.max_results,
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "include_images": False,
        }
        response = self.session.post(self.api_url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Tavily API 返回不是 JSON object: {type(data).__name__}")
        results = data.get("results")
        if not isinstance(results, list):
            raise ValueError("Tavily API 返回缺少 results 数组")
        return results

    def _extract_web_evidence(self, results: List[Dict]) -> List[Dict]:
        evidence_items: list[dict] = []
        for index, result in enumerate(results[: self.max_results], start=1):
            if not isinstance(result, dict):
                raise ValueError(f"Tavily 返回结果不是对象: {result}")

            title = str(result.get("title", "")).strip()
            content = str(result.get("content", "")).strip()
            url = str(result.get("url", "")).strip()

            if not title or not content or not url:
                raise ValueError(f"Tavily 结果缺少 title/content/url: index={index}")

            evidence_items.append(
                {
                    "evidence_id": len(evidence_items) + 1,
                    "fact": content[:800],
                    "title": title,
                    "url": url,
                    "source_type": "web",
                }
            )

        if not evidence_items:
            raise ValueError("联网检索没有可用证据")

        return evidence_items

    def _generate_claims(self, query: str, evidence_items: List[Dict]) -> List[Dict]:
        llm = ModelConfig.get_llm(
            ModelConfig.SYNTHESIZE_MODEL,
            temperature=0.0,
            json_mode=True,
        )
        prompt = f"""你是校园问答系统的时效信息回答器。请严格基于联网证据抽取回答结论。

用户问题：{query}

联网证据 JSON：
{json.dumps(evidence_items, ensure_ascii=False)}

要求：
- 只输出 JSON，不要 Markdown，不要解释。
- 输出字段只能是 claims。
- claims 是数组，每个元素包含 text 和 evidence_ids。
- text 是中文结论文本，不要在 text 中写 [1] 这类引用编号。
- evidence_ids 必须是非空整数数组，且每个编号必须来自联网证据的 evidence_id。
- 如果联网证据不足以直接回答，也必须输出一条“联网证据不足以确认...”结论，并绑定导致该判断的 evidence_ids。
- 不得添加证据之外的信息。
- 如果证据互相冲突，明确说明冲突来源。
- 结论要简洁、可执行。

JSON schema：
{{
  "claims": [
    {{
      "text": "当前联网证据仅能确认学生证补办的常规办理安排，未直接确认本周开放状态",
      "evidence_ids": [1]
    }}
  ]
}}

直接输出 JSON："""
        response = llm.invoke(prompt)
        response_text = response.content.strip() if hasattr(response, "content") else str(response).strip()
        if not response_text:
            raise ValueError("联网结论生成为空")

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"联网结论不是严格 JSON：{response_text[:120]}") from exc

        return self._validate_claims(data, evidence_items)

    def _validate_claims(self, data: Dict, evidence_items: List[Dict]) -> List[Dict]:
        claims = data.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError("联网结论缺少非空 claims 数组")

        valid_ids = {item["evidence_id"] for item in evidence_items}
        validated: list[dict] = []
        for index, claim in enumerate(claims, start=1):
            if not isinstance(claim, dict):
                raise ValueError(f"联网结论 claims[{index}] 不是对象")

            text = str(claim.get("text", "")).strip()
            evidence_ids = claim.get("evidence_ids")
            if not text:
                raise ValueError(f"联网结论 claims[{index}] 缺少 text")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise ValueError(f"联网结论 claims[{index}] 缺少非空 evidence_ids")

            ids: list[int] = []
            for evidence_id in evidence_ids:
                if not isinstance(evidence_id, int):
                    raise ValueError(f"联网结论 claims[{index}] 存在非整数 evidence_id")
                if evidence_id not in valid_ids:
                    raise ValueError(f"联网结论 claims[{index}] 引用了不存在的证据编号: {evidence_id}")
                if evidence_id not in ids:
                    ids.append(evidence_id)

            validated.append({"text": text, "evidence_ids": ids})

        return validated

    def _compose_answer(self, claims: List[Dict]) -> str:
        lines: list[str] = []
        for claim in claims:
            text = str(claim["text"]).strip()
            text = re.sub(r"(?:\[|【)\d+(?:\]|】)", "", text).strip()
            citation_text = "".join(f"[{evidence_id}]" for evidence_id in claim["evidence_ids"])
            lines.append(f"{text} {citation_text}")

        answer = "\n".join(lines).strip()
        if not answer:
            raise ValueError("联网答案组装为空")
        return answer

    def _verify_citations(self, answer: str, evidence_items: List[Dict]) -> List[Dict]:
        citation_ids = {
            int(match)
            for match in re.findall(r"(?:\[|【)(\d+)(?:\]|】)", answer)
        }
        valid_ids = {item["evidence_id"] for item in evidence_items}
        if not citation_ids:
            raise ValueError("联网答案没有引用证据编号")
        invalid_ids = citation_ids - valid_ids
        if invalid_ids:
            raise ValueError(f"联网答案引用了不存在的证据编号: {sorted(invalid_ids)}")

        return [
            item for item in evidence_items
            if item["evidence_id"] in citation_ids
        ]
