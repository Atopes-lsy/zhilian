# 知炼 EchoMind

知乎黑客松「知识炼金场：学习工具与知识生产」赛道项目。

知炼 EchoMind 是一个从 EchoMind 架构思想出发的新项目：把问答、经验帖、长文和讨论转化成学习路径、复习卡片、知识清单、思维导图和可追问的辅导体验。

本仓库从零实现，不改动原 EchoMind 项目。原项目只作为架构参考：多 Agent 编排、RAG 检索、Skills 注入、记忆压缩、trace 和评测。

## 当前阶段

G0 已确认，第一版本地 demo 已实现。

请先看：

- `.ai/g0-project-brief.md`
- `.ai/project-spec.json`
- `.ai/test-cases.json`
- `.ai/traceability.json`

## 推荐一句话

把知乎里的高质量回答，炼成一个能陪你学、帮你复习、还能反问你的学习工作台。

## 本地运行

后端：

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd apps\web
npm run dev
```

访问：

```text
http://127.0.0.1:5173/
```

## 当前功能

- 一键加载 3 篇合成知乎风格 demo 资料。
- Distiller Agent 把内容提炼成事实、概念、行动建议、观点、适用条件和风险提醒。
- Agent 协作面板展示 Distiller / Mapper / Tutor / Critic 的中间产物。
- 生成概览、核心概念、7 天学习路径、复习卡片、思维导图、实践任务和测验。
- 支持学习追问，并返回 Tutor / Mapper / Critic 路由、知识引用和 grounded trace。
- 后端 smoke test 和核心单测已通过。
