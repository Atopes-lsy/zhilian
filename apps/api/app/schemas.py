from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============ 输入 ============


class Comment(BaseModel):
    author: str = ""
    content: str = ""
    voteup_count: int = 0


class AnswerInput(BaseModel):
    answer_id: str
    author_name: str = ""
    author_tag: str = ""  # 如「大厂 AI 产品经理」
    # 可信度分层信号：亲历者 > 从业者 > 转述者 > 无
    author_role: Literal["亲历者", "从业者", "转述者", ""] = ""
    voteup_count: int = 0
    content: str = Field(min_length=1)
    comments: list[Comment] = Field(default_factory=list)


class QuestionInput(BaseModel):
    question_id: str = ""
    title: str = ""
    tags: list[str] = Field(default_factory=list)


class CondenseRequest(BaseModel):
    question: QuestionInput
    answers: list[AnswerInput]
    user_profile: dict[str, Any] = Field(default_factory=dict)


class LiveCondenseRequest(BaseModel):
    query: str = Field(min_length=1)
    count: int = Field(default=5, ge=1, le=20)


# ============ 输出 ============

ContentType = Literal["how_to", "opinion", "pitfall", "low_value"]
AnswerState = Literal["auto_condense", "skip", "fold"]
Credibility = Literal["亲历者", "从业者", "转述者", "无"]


class ExperienceCard(BaseModel):
    """经验结构化（AI 提炼）"""

    background: str = ""
    method: str = ""
    result: str = ""
    risk: str = ""


class KeyPoint(BaseModel):
    """要点（步骤 + 避坑 合并）"""

    title: str
    short_label: str = ""  # 进度条超短标签（2-4 字）
    quote: str  # 用于「原文 ↗」跳转定位（不展示）
    source_id: str


class Counterexample(BaseModel):
    """评论反例"""

    source: str = "评论区"
    content: str = ""
    voteup_count: int = 0


class CondensedAnswer(BaseModel):
    answer_id: str
    state: AnswerState
    content_type: ContentType
    char_count: int
    density: float  # 干货率 0~1
    credibility: Credibility
    author_name: str = ""  # 作者名（前端展示）
    author_tag: str = ""  # 作者标签
    voteup_count: int = 0  # 赞同数
    content_excerpt: str = ""  # 原文摘要（skip/fold 态用于前端展示）
    original_content: str = ""  # 原文全文（auto_condense 态用于「展开原文」）
    # 凝炼结果（仅 auto_condense 态有内容）
    takeaway: str = ""  # 一句话结论（AI 提炼）
    experience_card: ExperienceCard | None = None  # AI 提炼
    key_points: list[KeyPoint] = Field(default_factory=list)  # 要点（步骤+避坑合并）
    counterexamples: list[Counterexample] = Field(default_factory=list)
    suit: str = ""  # 适合谁
    trace: dict[str, Any] = Field(default_factory=dict)  # 算法依据


class ConsensusItem(BaseModel):
    claim: str
    sources: list[str]  # answer_ids


class Consensus(BaseModel):
    agreements: list[ConsensusItem] = Field(default_factory=list)
    disagreements: list[ConsensusItem] = Field(default_factory=list)


class CondenseResponse(BaseModel):
    question: QuestionInput
    consensus: Consensus
    answers: list[CondensedAnswer]
    trace: dict[str, Any] = Field(default_factory=dict)
