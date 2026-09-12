from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agents import condense_question
from .demo_data import DEMO_ANSWERS, DEMO_QUESTION
from .schemas import CondenseRequest, CondenseResponse, LiveCondenseRequest, QuestionInput
from .zhihu_cli import search_zhihu

app = FastAPI(title="知炼 EchoMind API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本地 demo 允许任意来源（含 file:// 打开的 HTML）
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "provider": "rule_based_mock", "version": "0.2.0"}


@app.post("/api/condense", response_model=CondenseResponse)
def condense(request: CondenseRequest) -> CondenseResponse:
    """对一个问题下的多条回答做凝炼：类型识别 + 干货率 + 三态分发 + 共识合并。"""
    return condense_question(request.question, request.answers)


@app.post("/api/demo/condense", response_model=CondenseResponse)
def condense_demo() -> CondenseResponse:
    """一键用内置的「如何转行 AI 产品经理」样例跑通凝炼管线。"""
    return condense_question(DEMO_QUESTION, DEMO_ANSWERS)


@app.post("/api/condense/live", response_model=CondenseResponse)
def condense_live(request: LiveCondenseRequest) -> CondenseResponse:
    """用 zhihu-cli 搜真实知乎内容，映射成回答后喂给凝炼管线。"""
    try:
        answers = search_zhihu(request.query, request.count)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    question = QuestionInput(question_id="live", title=request.query, tags=[])
    return condense_question(question, answers)
