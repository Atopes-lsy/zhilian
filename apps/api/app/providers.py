from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

VALID_TYPES = ("how_to", "opinion", "pitfall", "low_value")


def _load_env() -> None:
    """加载项目根目录 .env（若存在），不覆盖已设置的环境变量。"""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()

_CLASSIFY_SYSTEM_PROMPT = (
    "你是知乎内容分类器。把给定内容分为四类："
    "how_to=操作指南（教怎么做，有步骤/动作序列）；"
    "opinion=观点分析（表达判断/立场/结论）；"
    "pitfall=避坑经验（讲踩坑/教训/别做什么）；"
    "low_value=低价值（软广/抖机灵/无干货）。"
    '只输出 JSON，格式：{"content_type":"...","confidence":0.0到1.0,"reasoning":"一句话理由"}'
)


def get_llm_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "mock").strip().lower()


def classify_content_type(content: str) -> dict | None:
    """LLM 路分类：按 LLM_PROVIDER 分发。

    mock / 未知 provider / 调用失败都返回 None（三路投票走 Pattern 回退）。
    """
    provider = get_llm_provider()
    if provider == "openai":
        return _openai_classify(content)
    return None


_LABEL_SYSTEM_PROMPT = (
    "你是超短标签生成器。给定一个动作或避坑句子，生成 2-4 字的中文超短标签，"
    "抓住核心动作或核心名词（如「作品集」「别裸辞」「投递」）。"
    "只输出标签本身，不要解释、不要标点、不要引号。"
)


def condense_label(sentence: str) -> str | None:
    """LLM 路生成超短标签（2-4 字）。mock / 未知 / 失败返回 None（回退规则版）。"""
    if get_llm_provider() != "openai":
        return None
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "deepseek-chat").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if not api_key:
        return None

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _LABEL_SYSTEM_PROMPT},
                {"role": "user", "content": sentence[:200]},
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
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        label = text.strip().strip('"\'「」『』 ')
        return label[:6] if label else None
    except Exception:
        return None


def _openai_classify(content: str) -> dict | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if not api_key:
        return None

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": content[:2000]},
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
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        result = json.loads(_extract_json(text))
        content_type = result.get("content_type", "how_to")
        if content_type not in VALID_TYPES:
            content_type = "how_to"
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        return {"content_type": content_type, "confidence": confidence, "reasoning": result.get("reasoning", "")}
    except Exception:
        # 网络/鉴权/解析失败都不抛，返回 None 走回退
        return None


def _extract_json(text: str) -> str:
    """从模型输出里提取第一个 {...} JSON 块。"""
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return "{}"
