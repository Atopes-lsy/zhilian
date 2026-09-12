# G0 Project Brief

## Working Name

知炼 EchoMind

备选名：

- 知炼
- Zhiliang
- Knowledge Alchemy
- EchoMind Learn

推荐对外名：知炼 EchoMind。它保留 EchoMind 的延续性，也直接贴合「知识炼金场」。

## Product Thesis

知乎内容的价值不是只有「答案」，还有经验结构、推理路径、观点差异、行动步骤和适用边界。知炼 EchoMind 的产品目标是把这些隐性结构显性化，让用户从「看过」变成「学会、记住、能复述、能应用」。

## Target User

MVP 推荐只打一个场景：职业入门。

默认用户画像：

- 大学生、转行者、应届生。
- 面对一个陌生领域，例如 AI 应用开发、产品经理、运营、法学考研。
- 手里有很多知乎回答，但不知道学习顺序、重点和练习方式。

为什么推荐职业入门：

- 知乎内容优势强，经验帖和路径帖多。
- 评委容易理解痛点。
- Demo 容易做出「从碎片内容到学习路径」的转化感。
- 比校园刷题更少依赖题库和版权内容。

## Demo Scenario

推荐主题：AI 应用开发入门。

3 分钟演示：

1. 导入 3 篇脱敏知乎样例内容。
2. 用户选择目标：7 天做出一个黑客松 Demo。
3. 系统生成学习地图：先修概念、学习路径、复习卡片、实践任务、检查题。
4. 用户追问：我只有晚上 2 小时，第一天具体做什么？
5. Tutor Agent 给学习安排，Mapper Agent 补结构，Critic Agent 标注依据和不确定点。
6. 右侧显示知识引用、trace、耗时、grounded 状态和质量评分。

## MVP Contract

MVP-01 Content Workspace

用户可以导入或加载脱敏知乎样例内容，系统完成切片、索引和检索。

验收：

- 支持 Markdown 和 JSON 样例。
- 导入后资料数量增加。
- 搜索「AI 应用开发」「黑客松 Demo」「项目路径」能命中相关片段。

MVP-02 Alchemy Generator

用户输入主题、目标、基础和时间，系统生成结构化学习资产。

验收：

- 输出包含 overview、concepts、learning_path、flashcards、mindmap、practice_tasks、quiz。
- 每类资产能在前端独立展示。
- 输出中展示引用来源或证据片段。

MVP-03 Learning Chat

用户围绕资料追问，AI 用学习者能理解的方式辅导，并保留证据链。

验收：

- 支持改难度、压缩时间、举例解释、生成练习。
- 知识库命中时展示 used_sources。
- 证据不足时明确提示不确定。

MVP-04 Demo Console

一个评委可操作的前端工作台，完整展示从内容到学习资产再到追问的流程。

验收：

- 首页就是工作台。
- 主流程 3 分钟内完成。
- 桌面和移动端无明显文字遮挡、横向滚动和主按钮不可见问题。

## Out Of Scope

- 不接真实知乎账号。
- 不自动爬取知乎。
- 不存储真实用户隐私。
- 不训练或微调模型。
- 不做完整多人系统。
- 不做支付、邮件、消息发送等外部动作。
- 不公开部署，除非进入 G5 上线审批。

## Architecture Defaults

推荐从零实现一个轻量 monorepo：

```text
zhilian-echomind/
  apps/web/        Vite + Vue or React learning workspace
  apps/api/        FastAPI or Node API
  packages/core/   prompt templates, schemas, agent routing
  data/samples/    synthetic and de-identified demo content
  .ai/             specs, tests, traceability, reports
```

当前默认建议：

- Frontend：Vite + Vue，贴近原 EchoMind 前端，迁移思路成本低。
- Backend：FastAPI，适合快速做 RAG、schema、mock provider 和评测。
- Storage：本地 JSON + SQLite，可后续替换向量库。
- Retrieval：BM25/simple embedding mock first，后续接向量检索。
- LLM Provider：先设计 provider interface，G1 再确认 OpenAI official API、DeepSeek 或 mock mode。
- Demo Data：只使用合成或脱敏样例。

## Agent Design

MVP 三个 Agent：

Tutor Agent

- 把内容讲清楚。
- 按用户水平解释概念。
- 生成例子、类比和练习。

Mapper Agent

- 把碎片回答变成结构。
- 输出学习路径、概念树、先修关系、行动清单。

Critic Agent

- 做观点对照和证据检查。
- 标出来源片段、冲突观点、不确定点。
- 防止模型把经验帖说成绝对事实。

## Token Budget Rules

- 原文只入库，不塞进聊天。
- 每轮最多检索 Top 5。
- 用户画像压缩到 200 字以内。
- 学习资产按 schema 输出，避免自由长文。
- Agent prompt 放在固定模板文件里，不在聊天中重复。
- 人工反馈用 ID 格式，例如 `G0: approve`。

## Human Decisions Needed

请你后续用短格式确认：

```text
G0: approve
场景: 职业入门
主题: AI 应用开发入门
前端: Vue
后端: FastAPI
模型: 先 mock，后接 OpenAI 官方 API
上线: 先本地 demo
```

如果你想改，也可以只回复变化项：

```text
场景: 校园学习
主题: 法学考研
前端: React
模型: DeepSeek
```

## Risks And Smallest Proof

模型输出不稳定：

- 先固定 JSON schema。
- 加 schema validation 和 fallback。

资料版权和隐私：

- Demo 只放合成或脱敏文本。
- 原文来源字段只做备注，不展示真实个人信息。

RAG 命中不准：

- G1 先用 3 篇样例测试检索。
- 每个学习资产保留 source_ids。

前端演示不够强：

- 首页即工作台。
- 使用一键 demo 数据和预设目标。
- 保留 trace 面板展示 EchoMind 继承价值。

时间不够：

- 先做 local demo。
- OpenAI provider、向量库、公开部署都放 G1/G5 后确认。
