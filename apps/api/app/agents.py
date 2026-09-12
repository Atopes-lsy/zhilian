from __future__ import annotations

import hashlib
import math
import re

from .schemas import (
    AnswerInput,
    CondensedAnswer,
    CondenseResponse,
    Consensus,
    ConsensusItem,
    Counterexample,
    ExperienceCard,
    KeyPoint,
    QuestionInput,
)
from .providers import classify_content_type, condense_label
from .evaluator import evaluate_faithfulness, judge_quality

# ============ 信号关键词 ============

ACTION_WORDS = [
    "做", "先", "然后", "整理", "投递", "开始", "写", "练", "拆", "跑通", "搭建",
    "准备", "面试", "动手", "产出", "落地", "调用", "重做", "推动",
]
SEQUENCE_MARKERS = [
    "第一", "第二", "第三", "第四", "阶段", "步骤", "首先", "其次", "最后",
    "第一步", "第二步", "第1", "第2", "第3",
]
OPINION_WORDS = [
    "我认为", "本质", "关键", "不会", "会", "应该", "其实", "取代", "重新定义",
    "价值", "判断", "结论", "不是", "而是", "边界", "理解", "焦虑",
]
RISK_WORDS = [
    "别", "不要", "坑", "后悔", "翻车", "亏", "踩坑", "裸辞", "失败", "没用",
    "学不下去", "崩", "硬套", "瞎飞",
]
AD_WORDS = [
    "公众号", "加微信", "私信", "领取", "培训", "报名", "体验课", "带你飞",
    "赚钱", "老师微信", "点击卡片", "免费领取",
]

# 共识主题词 → 可读主张（只保留能形成真实共识/分歧的短语，避免短词误匹配）
TOPIC_CLAIMS = {
    "裸辞": "别裸辞",
    "作品集": "先做作品集",
    "算法": "懂多少算法",
    "数据回流": "重视数据回流",
    "卖点": "AI 是工具不是卖点",
}


# ============ 工具函数 ============


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def count_hits(text: str, words: list[str]) -> int:
    return sum(text.count(w) for w in words)


def shorten(text: str, limit: int = 18) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _condense_title(sentence: str) -> str:
    """从句子提炼简洁标题（规则版「AI 凝炼」：去发语词 + 取核心动作短语）。"""
    text = sentence.strip()
    # 去句首发语词（保留「别/不要」否定语义）
    for w in ("我的经验是", "我建议", "一定要", "最好的方式是", "后来", "所以", "就是", "其实"):
        if text.startswith(w):
            text = text[len(w):].lstrip("，,。：:；; ")
            break
    # 取动作/风险信号最强的分句
    clauses = [c.strip() for c in re.split(r"[，,；;]", text) if c.strip()]
    if clauses:
        text = max(clauses, key=lambda c: count_hits(c, ACTION_WORDS + RISK_WORDS))
    # 去动作引导词（先/然后/可以/应该/就是/是，但保留「别」）
    for w in ("然后", "先", "可以", "应该", "就是", "是"):
        if text.startswith(w):
            text = text[len(w):].lstrip()
            break
    return shorten(text, 16)


def _condense_short_title(sentence: str) -> str:
    """进度条超短标签（2-4 字）：优先 LLM，mock 回退规则版。"""
    label = condense_label(sentence)
    if label:
        return label
    title = _condense_title(sentence)
    for neg in ("千万别", "不要", "别"):
        if title.startswith(neg):
            core = title[len(neg):]
            for w in ("一开始", "太", "没", "在", "随便", "盲目", "硬", "乱"):
                if core.startswith(w):
                    core = core[len(w):]
                    break
            return shorten(neg + core, 4)
    return shorten(title, 4)


def is_negated(text: str, topic: str) -> bool:
    # 检查主题词在任何一处是否被否定（别/不要/千万别 在其前 8 字内）
    for m in re.finditer(re.escape(topic), text):
        prefix = text[max(0, m.start() - 8):m.start()]
        if any(w in prefix for w in ("别", "不要", "千万别")):
            return True
    return False


# ============ Agent 1：ContentTypeDetector（三路融合） ============
# 架构对齐 EchoMind 的「三路融合意图识别」：
#   LLM（70%）语义 + Embedding（20%）相似度 + Pattern（10%）关键词，加权投票。
# 当前 LLM / Embedding 未接 provider（返回 None 走回退），Pattern 路已落地。


def _pattern_classify(content: str) -> dict:
    """Pattern 路：关键词打分（同步零延迟，软广/风险强信号）。"""
    action = count_hits(content, ACTION_WORDS) + 2 * count_hits(content, SEQUENCE_MARKERS)
    opinion = count_hits(content, OPINION_WORDS)
    risk = count_hits(content, RISK_WORDS)
    ad = count_hits(content, AD_WORDS)
    signals = {"actionability": action, "opinion_density": opinion, "risk_density": risk, "ad_signal": ad}

    if ad >= 2:
        return {"content_type": "low_value", "confidence": 0.9, "signals": signals}
    if risk >= action and risk >= opinion and risk > 0:
        return {"content_type": "pitfall", "confidence": min(0.9, 0.4 + 0.08 * risk), "signals": signals}
    if opinion > action and opinion > risk:
        return {"content_type": "opinion", "confidence": min(0.9, 0.4 + 0.05 * opinion), "signals": signals}
    if action > 0:
        return {"content_type": "how_to", "confidence": min(0.9, 0.4 + 0.03 * action), "signals": signals}
    return {"content_type": "how_to", "confidence": 0.3, "signals": signals}


def _llm_classify(content: str) -> dict | None:
    """LLM 路：语义理解。按 LLM_PROVIDER 分发，mock 返回 None（走 Pattern 回退），openai 真调模型。"""
    return classify_content_type(content)


# 类型模板（各类型的代表性词汇，用于 Embedding 路相似度）
_TYPE_TEMPLATES = {
    "how_to": "先做然后整理投递开始准备面试动手搭建跑通落地调用重做推动产出步骤",
    "opinion": "我认为本质关键判断结论不会应该其实取代重新定义价值理解边界焦虑",
    "pitfall": "别不要坑后悔翻车踩坑裸辞失败没用崩硬套瞎飞亏教训",
    "low_value": "公众号加微信培训报名领取体验课老师点击卡片免费赚钱",
}


def _stable_hash(text: str, dim: int) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % dim


def _n_gram_vector(text: str, dim: int = 256) -> list[float]:
    """本地字符 bigram 哈希向量（256 维，L2 归一化，无外部依赖）。"""
    clean = re.sub(r"\s+", "", text)
    vec = [0.0] * dim
    for i in range(len(clean) - 1):
        vec[_stable_hash(clean[i : i + 2], dim)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _embedding_classify(content: str) -> dict | None:
    """Embedding 路：内容与类型模板的 n-gram 哈希向量相似度（对齐 EchoMind _local_embedding）。"""
    content_vec = _n_gram_vector(content)
    best_type, best_score = "how_to", 0.0
    scores: dict[str, float] = {}
    for t, template in _TYPE_TEMPLATES.items():
        sim = _cosine(content_vec, _n_gram_vector(template))
        scores[t] = round(sim, 4)
        if sim > best_score:
            best_type, best_score = t, sim
    # 相似度过低说明不匹配任何模板，返回 None（走 Pattern 回退）
    if best_score < 0.03:
        return None
    return {"content_type": best_type, "confidence": round(best_score, 4), "signals": scores}


def _vote(llm: dict | None, emb: dict | None, pat: dict) -> dict:
    """三路加权投票：失败回退 + 软广纠偏 + 阈值降级。"""
    source_scores = {
        "llm": (llm or {}).get("confidence"),
        "embedding": (emb or {}).get("confidence"),
        "pattern": pat.get("confidence"),
    }
    routes = []
    if llm and not llm.get("failed"):
        routes.append((llm, 0.7))
    if emb and not emb.get("failed"):
        routes.append((emb, 0.2))
    if pat and not pat.get("failed"):
        routes.append((pat, 0.1))

    if not routes:
        return {"content_type": "how_to", "confidence": 0.0, "source_scores": source_scores}

    # 权重归一化，使置信度可解释为 0~1
    total_weight = sum(w for _, w in routes)
    scores: dict[str, float] = {}
    for result, w in routes:
        ct = result["content_type"]
        scores[ct] = scores.get(ct, 0) + (w / total_weight) * result["confidence"]
    best_ct = max(scores, key=scores.get)
    best_score = scores[best_ct]

    # Pattern 细粒度纠偏：软广强信号优先于 LLM 语义（LLM 易被营销话术骗）
    if pat and pat["content_type"] == "low_value" and best_ct != "low_value":
        best_ct = "low_value"
        best_score = max(best_score, 0.8)

    # 阈值降级：低置信不硬猜，保守默认 how_to（由 state 层决定 skip）
    if best_score < 0.5:
        best_ct = "how_to"

    return {"content_type": best_ct, "confidence": round(best_score, 4), "source_scores": source_scores}


def detect_content_type(content: str) -> tuple[str, dict]:
    """三路融合类型识别：LLM + Embedding + Pattern，加权投票。"""
    pat = _pattern_classify(content)
    llm = _llm_classify(content)
    emb = _embedding_classify(content)
    result = _vote(llm, emb, pat)

    info = dict(pat.get("signals", {}))  # 四信号
    info["confidence"] = result["confidence"]
    info["source_scores"] = result["source_scores"]
    return result["content_type"], info


# ============ Agent 2：DensityScorer ============


def score_density(content: str) -> float:
    sentences = split_sentences(content)
    if not sentences:
        return 0.0
    signal_words = ACTION_WORDS + OPINION_WORDS + RISK_WORDS
    dry = sum(1 for s in sentences if count_hits(s, signal_words) > 0)
    return round(dry / len(sentences), 4)


# ============ Agent 3：CredibilityTagger ============


def tag_credibility(author_role: str) -> str:
    return author_role if author_role in ("亲历者", "从业者", "转述者") else "无"


# ============ StateRouter：三态判定 ============


def decide_state(content_type: str, density: float, char_count: int, author_role: str, voteup: int) -> str:
    if content_type == "low_value":
        return "fold"
    # 价值 = 干货率；高赞/可信身份是加分项（question answers 接口无赞同数，缺失时降级为只看干货率）
    value_high = density >= 0.12
    # 产品规范为「800 字以上」，demo/搜索摘要较短，阈值暂设 450
    if char_count >= 450 and value_high:
        return "auto_condense"
    return "skip"


# ============ Agent 4：Distiller ============


def _is_action(sentence: str) -> bool:
    return count_hits(sentence, SEQUENCE_MARKERS) > 0 or count_hits(sentence, ACTION_WORDS) >= 2


def _is_risk(sentence: str) -> bool:
    return count_hits(sentence, RISK_WORDS) > 0


def _is_step(sentence: str) -> bool:
    """强动作句：序列词 或 ≥4 个动作词（比 _is_action 更严，过滤叙述句）。"""
    return count_hits(sentence, SEQUENCE_MARKERS) > 0 or count_hits(sentence, ACTION_WORDS) >= 4


def _is_pitfall(sentence: str) -> bool:
    """负向建议句：别 / 不要 / 千万别（而非「我踩了坑」的叙述）。"""
    return any(w in sentence for w in ("别", "不要", "千万别"))


def _pick_takeaway(sentences: list[str]) -> str:
    best, best_score = "", -1
    for s in sentences:
        score = count_hits(s, ACTION_WORDS + OPINION_WORDS)
        if score > best_score and len(s) >= 8:
            best, best_score = s, score
    return best or (sentences[0] if sentences else "")


def _build_experience_card(sentences: list[str]) -> ExperienceCard:
    background = next((s for s in sentences if count_hits(s, ["背景", "本科", "毕业", "之前", "以前", "我是", "做过"]) > 0), "")
    method = next((s for s in sentences if _is_action(s)), "")
    result = next((s for s in sentences if count_hits(s, ["结果", "成功", "拿到", "offer", "转化率", "明显"]) > 0), "")
    risk = next((s for s in sentences if _is_risk(s)), "")
    return ExperienceCard(background=background, method=method, result=result, risk=risk)


def distill(content: str, answer_id: str) -> tuple[str, ExperienceCard, list[KeyPoint]]:
    sentences = split_sentences(content)
    takeaway = _pick_takeaway(sentences)
    card = _build_experience_card(sentences)
    key_points: list[KeyPoint] = []
    for i, s in enumerate(sentences):
        # 步骤 + 避坑 合并为「要点」
        if _is_pitfall(s) or _is_step(s):
            key_points.append(
                KeyPoint(title=_condense_title(s), short_label=_condense_short_title(s), quote=shorten(s, 28), source_id=f"{answer_id}_s{i}")
            )
    return takeaway, card, key_points


# ============ Agent 5：CommentSynthesizer ============


def synthesize_comments(comments) -> list[Counterexample]:
    counter_signals = ["但是", "不过", "不适用", "翻车", "失败", "挂", "不对", "不成立", "还是", "其实"]
    return [
        Counterexample(source="评论区", content=c.content, voteup_count=c.voteup_count)
        for c in comments
        if count_hits(c.content, counter_signals) > 0
    ]


# ============ Agent 6：ConsensusMerger ============


def merge_consensus(raw_answers: list[AnswerInput]) -> Consensus:
    stance: dict[str, dict[str, bool]] = {}
    for a in raw_answers:
        if detect_content_type(a.content)[0] == "low_value":
            continue
        for topic in TOPIC_CLAIMS:
            if topic not in a.content:
                continue
            stance.setdefault(topic, {})[a.answer_id] = is_negated(a.content, topic)

    agreements: list[ConsensusItem] = []
    disagreements: list[ConsensusItem] = []
    for topic, sources in stance.items():
        if len(sources) < 2:
            continue
        item = ConsensusItem(claim=TOPIC_CLAIMS[topic], sources=sorted(sources))
        if len(set(sources.values())) == 1:
            agreements.append(item)
        else:
            disagreements.append(item)
    return Consensus(agreements=agreements, disagreements=disagreements)


# ============ 适合谁 ============


def build_suit(answer: AnswerInput) -> str:
    if answer.author_role == "亲历者":
        return "有产品/项目经验、目标偏落地的人"
    if answer.author_role == "从业者":
        return "想了解行业趋势、做判断的人"
    return ""


# ============ 编排 ============


def condense_answer(answer: AnswerInput) -> CondensedAnswer:
    content = answer.content
    char_count = len(content)
    density = score_density(content)
    content_type, signals = detect_content_type(content)
    credibility = tag_credibility(answer.author_role)
    state = decide_state(content_type, density, char_count, answer.author_role, answer.voteup_count)

    result = CondensedAnswer(
        answer_id=answer.answer_id,
        state=state,
        content_type=content_type,
        char_count=char_count,
        density=density,
        credibility=credibility,
        author_name=answer.author_name,
        author_tag=answer.author_tag,
        voteup_count=answer.voteup_count,
        content_excerpt=content[:120],
        trace={"signals": signals, "char_count": char_count, "density": density, "voteup": answer.voteup_count},
    )

    if state == "fold":
        return result

    # 评论反例：所有高价值回答都显性化
    result.counterexamples = synthesize_comments(answer.comments)

    if state == "auto_condense":
        takeaway, card, key_points = distill(content, answer.answer_id)
        result.takeaway = takeaway
        result.experience_card = card
        result.key_points = key_points
        result.original_content = content
        result.suit = build_suit(answer)
        # 评测：忠实性（规则护栏）+ LLM-as-Judge（可选）
        quotes = [k.quote for k in key_points]
        result.trace["faithfulness"] = evaluate_faithfulness(content, quotes)
        result.trace["judge"] = judge_quality(content, takeaway, key_points)

    return result


def condense_question(question: QuestionInput, answers: list[AnswerInput]) -> CondenseResponse:
    condensed = [condense_answer(a) for a in answers]
    consensus = merge_consensus(answers)
    return CondenseResponse(
        question=question,
        consensus=consensus,
        answers=condensed,
        trace={"provider": "rule_based_mock", "answer_count": len(answers)},
    )
