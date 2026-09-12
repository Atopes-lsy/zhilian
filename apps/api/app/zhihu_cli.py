from __future__ import annotations

import json
import os
import subprocess
import time

from .schemas import AnswerInput, Comment

# ============ 缓存 / 限流 / 熔断（对应 EchoMind 的 tool_manager） ============

_cache: dict[str, tuple[float, list[AnswerInput]]] = {}  # key -> (过期时间戳, 结果)
_CACHE_TTL = 300.0  # 缓存 5 分钟
_CACHE_MAX = 64

_last_call_ts = 0.0
_MIN_INTERVAL = 1.0  # 两次请求最小间隔（秒），避免撞限流

_fail_count = 0
_FAIL_THRESHOLD = 3  # 连续失败 3 次熔断
_COOLDOWN = 30.0  # 熔断 30 秒
_circuit_open_until = 0.0


def get_cli_path() -> str:
    env = os.environ.get("ZHIHU_CLI_PATH")
    if env:
        return env
    local = os.environ.get("LOCALAPPDATA", "")
    return os.path.join(local, "ZhihuCLI", "current", "zhihu-cli.exe")


def run_cli(args: list[str], timeout: int = 30) -> dict:
    path = get_cli_path()
    try:
        result = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except FileNotFoundError:
        raise RuntimeError("zhihu-cli 未安装，请先运行 setup")
    if result.returncode != 0:
        raise RuntimeError(f"zhihu-cli 调用失败: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"zhihu-cli 返回非 JSON: {result.stdout[:200]}")


def _map_item(item: dict) -> AnswerInput | None:
    content = (item.get("ContentText") or "").strip()
    if not content:
        return None
    comments = [
        Comment(content=(c.get("Content") or "").strip(), voteup_count=0)
        for c in (item.get("CommentInfoList") or [])
        if (c.get("Content") or "").strip()
    ]
    return AnswerInput(
        answer_id=str(item.get("ContentID") or ""),
        author_name=item.get("AuthorName") or "匿名用户",
        author_tag=item.get("AuthorBadgeText") or "",
        author_role="",  # 搜索接口无身份标签，可信度由赞同数/内容推断
        voteup_count=int(item.get("VoteUpCount") or 0),
        content=content,
        comments=comments,
    )


def _map_answer_item(item: dict) -> AnswerInput | None:
    content = (item.get("Summary") or "").strip()
    if not content:
        return None
    return AnswerInput(
        answer_id=str(item.get("ContentToken") or item.get("Url") or ""),
        author_name="",
        author_tag="",
        author_role="",
        voteup_count=0,  # question answers 接口无赞同数
        content=content,
        comments=[],
    )


def search_by_question(query: str, count: int = 5) -> list[AnswerInput]:
    """用「问题推荐 + 问题回答」接口搜索知乎（search zhihu 限流时的替代）。"""
    rec = run_cli(["question", "recommend", "--query", query, "--count", "1"])
    items = (rec.get("Data") or {}).get("Items") or []
    if not items:
        return []
    url = items[0].get("Url", "")
    ans = run_cli(["question", "answers", "--question-url", url, "--limit", str(count)])
    answer_items = (ans.get("Data") or {}).get("Items") or []
    return [a for a in (_map_answer_item(i) for i in answer_items) if a is not None]


def search_zhihu(query: str, count: int = 5, use_cache: bool = True) -> list[AnswerInput]:
    """调用 zhihu-cli 搜索知乎，带缓存 / 限流 / 熔断。"""
    key = f"{query}|{count}"

    # 缓存命中
    if use_cache and key in _cache:
        expire_ts, cached = _cache[key]
        if time.time() < expire_ts:
            return cached
        _cache.pop(key, None)

    # 熔断中：直接走 question 接口回退
    if _circuit_is_open():
        return search_by_question(query, count)

    _throttle()
    try:
        answers = _search_raw(query, count)
    except RuntimeError:
        _record_failure()
        # search zhihu 限流/失败，回退 question 接口（question recommend + answers）
        return search_by_question(query, count)
    _record_success()

    if use_cache:
        _cache[key] = (time.time() + _CACHE_TTL, answers)
        _evict_if_needed()
    return answers


def _search_raw(query: str, count: int) -> list[AnswerInput]:
    data = run_cli(["search", "zhihu", "--query", query, "--count", str(count)])
    items = (data.get("Data") or {}).get("Items") or []
    return [a for a in (_map_item(i) for i in items) if a is not None]


def _throttle() -> None:
    global _last_call_ts
    elapsed = time.time() - _last_call_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_ts = time.time()


def _circuit_is_open() -> bool:
    return time.time() < _circuit_open_until


def _record_failure() -> None:
    global _fail_count, _circuit_open_until
    _fail_count += 1
    if _fail_count >= _FAIL_THRESHOLD:
        _circuit_open_until = time.time() + _COOLDOWN
        _fail_count = 0


def _record_success() -> None:
    global _fail_count
    _fail_count = 0


def _evict_if_needed() -> None:
    if len(_cache) > _CACHE_MAX:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)


def clear_cache() -> None:
    _cache.clear()
