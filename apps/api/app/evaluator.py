from __future__ import annotations

import json
import os
import urllib.request

from .providers import get_llm_provider

_JUDGE_SYSTEM_PROMPT = (
    "你是凝炼质量评测员。给定原文和凝炼结果，从两个维度打分（0.0 到 1.0）："
    "faithfulness=凝炼是否忠实原文（无编造/无幻觉）；"
    "actionability=结论/步骤是否可执行。"
    '只输出 JSON：{"faithfulness":0.0到1.0,"actionability":0.0到1.0,"verdict":"一句话点评"}'
)


def evaluate_faithfulness(original: str, quotes: list[str]) -> float:
    """规则版忠实性：原文引用是否真的来自原文（防幻觉）。

    规则版蒸馏的 quote 是按句切分的原文，天然忠实；接入 LLM 蒸馏后，
    这一步就是防止 LLM 编造的护栏。
    """
    if not quotes:
        return 1.0
    matched = sum(1 for q in quotes if _core_in_original(q, original))
    return round(matched / len(quotes), 4)


def _core_in_original(quote: str, original: str) -> bool:
    core = quote.replace("……", "").replace("…", "").strip()
    if not core:
        return True
    return core[:10] in original


def judge_quality(original: str, takeaway: str, key_points: list) -> dict | None:
    """LLM-as-Judge：mock 返回 None，openai 真打「忠实性 + 可执行性」分。"""
    if get_llm_provider() != "openai":
        return None
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if not api_key:
        return None

    condensed_text = (
        "结论：" + takeaway + "\n"
        "要点：" + "；".join(k.quote for k in key_points)
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": f"原文：\n{original[:2000]}\n\n凝炼结果：\n{condensed_text[:2000]}"},
            ],
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        result = json.loads(_extract_json(text))
        return {
            "faithfulness": max(0.0, min(1.0, float(result.get("faithfulness", 0.5)))),
            "actionability": max(0.0, min(1.0, float(result.get("actionability", 0.5)))),
            "verdict": result.get("verdict", ""),
        }
    except Exception:
        return None


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return "{}"
