# AI Agent 的"碎碎念"怎么让普通用户看懂？我们设计了一套旁路解说架构

> 当 AI Agent 在后台疯狂调用工具、输出技术性思考时，你的用户看到的却是天书。本文介绍一种不侵入主流程的旁路解说者架构，让 Agent 的工作过程变得人人可读。

---

## 先说问题：Agent 的输出，用户根本看不懂

2025 年是 AI Agent 爆发的一年。Anthropic 的 Claude、Google 的 ADK、OpenAI 的 Agents SDK，各家都在推 Agent 框架。但有一个问题被严重低估了——**Agent 的中间输出，对普通用户是灾难**。

来看一个真实场景。你让 Agent "分析一下这份销售数据，找出增长最快的区域"，Agent 内部会经历这样的过程：

```
→ 调用 load_skill(skill_name="data-analysis")
→ thought: "I need to first load the skill instructions, then
   check if there are reference materials available. Step 1
   requires understanding the data structure before any
   cleaning procedures..."
→ 调用 load_skill_resource(resource_path="references/analysis-methods.md")
→ thought: "The methodology suggests statistical tests. Let me
   verify which ones are appropriate for this data shape..."
```

你作为开发者可能觉得这很正常。但想象一下，**如果把这段内容直接展示给业务用户**：

- `load_skill` 是什么？为什么需要"加载技能"？
- 全英文的思考过程，用户看得懂吗？
- `load_skill_resource` 又是干什么的？
- 用户只是想看分析结果，为什么要看这些？

**结论：Agent 的工作机制暴露得越原始，用户体验越差。**

---

## 现有方案的问题

有人会说："那就把所有中间过程隐藏起来，只展示最终结果不就行了？"

但这样会带来另一个问题——**等待体验极差**。一个复杂的数据分析任务可能要跑 30-60 秒，这期间用户盯着空白屏幕，不知道 Agent 在干什么、是卡住了还是在跑、进度到哪了。

**信息太少是黑箱，信息太多是天书。** 我们需要的是第三种方案——把技术语言翻译成人话。

---

## 我们的方案：旁路解说者架构

核心思路很简单，用一句话概括：

> **把 Agent 的输出分成三条独立的"管道"：正文走主通道，工具调用和思考过程走旁路，经过一个翻译层变成通俗中文后，再展示给用户。**

不侵入主 Agent 的执行逻辑，不修改工具返回内容，纯粹作为一个"同传翻译"挂载在旁边。这就是"旁路"的含义。

架构长这样：

```
用户提问
    │
    ▼
┌──────────────────────────────────┐
│          主 Agent                  │
│    (执行技能、调用工具、深度思考)   │
└────┬──────────┬──────────┬───────┘
     │          │          │
  ▼           ▼          ▼
正文回复    思考过程     工具调用
 (text)    (thought)    (tool)
  │          │          │
  │     ┌────▼────┐ ┌───▼───┐
  │     │ 旁路解说 │ │旁路解说│
  │     │ 翻译思考 │ │翻译工具│
  │     └────┬────┘ └───┬───┘
  ▼          ▼          ▼
最终答案    🧠思考卡片   📖工具卡片
直接展示   "正在按照    "正在加载
          方法论逐步    数据分析的
          推进分析"    专业指导"
```

三种输出各有各的通道，互不干扰：

| 输出类型 | SSE type | 展示方式 | 说明 |
|---------|----------|---------|------|
| **正文回复** | `text` | 主聊天区域，流式渲染 | Agent 给用户的最终答案，原样输出 |
| **思考过程** | `thought` | 折叠面板，翻译后展示摘要 | 原始英文推理被翻译为一句中文 |
| **工具调用** | `narrator_card` | 步骤时间线，彩色卡片 | 技术工具名 → 友好标签 + 图标 |

---

## 两个关键翻译层

### 翻译层一：工具名 → 友好标签

Agent 内部用的工具名都是 `load_skill`、`load_skill_resource` 这种技术命名。旁路解说模块维护了一张映射表：

```python
TOOL_LABELS = {
    "load_skill": {
        "label": "加载技能指导",
        "icon": "📖",
        "detail": "读取该技能的详细分步指导，了解正确的执行方法",
    },
    "load_skill_resource": {
        "label": "加载参考资料",
        "icon": "📚",
        "detail": "查阅深度参考文档，确保分析质量和准确性",
    },
    "list_skills": {
        "label": "查看可用技能",
        "icon": "📋",
        "detail": "检查当前有哪些专业技能可以用来处理这个任务",
    },
}
```

对于没预先定义的工具名，还有**子串模式匹配**兜底，比如所有包含 `search` 的工具自动翻译为"搜索信息" 🔍，所有包含 `analyze` 的工具翻译为"分析数据" 📊。

最差情况——工具名变成标题大小写的可读文本（`run_command` → `Run Command`），配上 🔧 图标。

### 翻译层二：思考过程 → 一句中文

Agent 的思考（thought）往往是这样的：

```
"I need to first load the data analysis skill instructions,
then check if there are reference materials available.
Step 1 requires understanding the data structure before
any cleaning procedures. Let me verify which statistical
methods are appropriate..."
```

我们用**正则模式匹配**把它翻译成：

| 匹配到 | 就翻译为 |
|--------|---------|
| `need to check/verify`、`需要验证` | "正在验证信息，确保后续步骤的准确性" |
| `step 1`、`第一步` | "按照结构化方法论，逐步推进分析" |
| `first load`、`首先获取` | "先从收集必要的信息开始" |
| `summarize`、`总结` | "将多方面的信息整合成清晰的结论" |
| `edge case`、`边界情况` | "排查边缘情况和特殊情况，确保分析的鲁棒性" |
| `conclusion`、`结论` | "基于前面的分析得出最终结论" |

限制每次最多生成 3 张思考卡片，避免信息刷屏。

---

## 怎么实现的？三个回调钩子就够了

旁路解说的整个实现基于 Google ADK 框架的三个回调，挂载在 Agent 上：

```python
root_agent = Agent(
    model=LiteLlm(model="deepseek/deepseek-v4-pro"),
    name="skill_explain_agent",
    instruction="...",
    tools=[skill_toolset],
    before_tool_callback=before_tool_callback,   # 工具执行前
    after_tool_callback=after_tool_callback,     # 工具执行后
    after_model_callback=after_model_callback,   # LLM 每次响应后
)
```

三个回调各司其职：

| 回调 | 触发时机 | 做什么 |
|------|---------|--------|
| `before_tool_callback` | 工具执行前 | 生成 `status: "running"` 卡片 — "即将加载技能指导" |
| `after_tool_callback` | 工具执行后 | 生成 `status: "done"` 卡片 — "加载完成，返回 45 行数据" |
| `after_model_callback` | LLM 每次响应后 | 扫描思考内容，匹配翻译模式，生成 `status: "info"` 卡片 |

卡片存储在 session state 的 `_narrator_cards` 键下，完全独立于正文回复。**缓存失败不会阻塞主 Agent，错误被静默捕获。**

---

## 前端怎么展示？SSE 三通道流式推送

服务端用 FastAPI + SSE 把三种输出实时推送给前端：

**正文回复（逐字流式）：**

```json
{"type": "text", "text": "根据数据分析的结果..."}
```

**思考过程（附带翻译）：**

```json
{
  "type": "thought",
  "raw": "I need to first load the skill instructions...",
  "narrated": "先从收集必要的信息开始"
}
```

**解说卡片（实时增量推送，每张卡片独立事件）：**

```json
{
  "type": "narrator_card",
  "card": {
    "phase": "before_tool",
    "icon": "📖",
    "label": "加载技能指导",
    "detail": "读取该技能的详细分步指导，了解正确的执行方法",
    "status": "running"
  },
  "card_index": 0
}
```

```json
{
  "type": "narrator_card",
  "card": {
    "phase": "after_tool",
    "icon": "📖",
    "label": "加载技能指导 - 完成",
    "detail": "返回 45 行 (2340 字符)",
    "status": "done"
  },
  "card_index": 1
}
```

**流结束信号：**

```json
{"type": "done", "card_count": 7, "thought_count": 3}
```

React 前端根据 `type` 字段渲染：

- `text` → Markdown 渲染到主聊天区
- `thought` → `<details>` 折叠面板（摘要显示翻译后的中文，展开看原文）
- `narrator_card` → 彩色边框卡片（橙色=执行中，绿色=完成，紫色=思考）
- `done` → 结束标记

最终用户看到效果是这样的：

```
┌───────────────────────────────────────────────┐
│  主聊天区                                      │
│                                                │
│  根据对销售数据的完整分析，以下是关键发现：      │
│  1. 华东地区营收同比增长 23%...                 │
│  2. 产品 B 的客户满意度最高（4.7/5.0）...       │
│                                                │
├───────────────┬────────────────────────────────┤
│  解说面板      │                                │
│                │                                │
│  📖 加载技能指导 │ ← 用户在等的过程中，           │
│  ✓ 完成         │   能看到 Agent 在做什么        │
│                │                                │
│  🧠 思考过程    │                                │
│  先从收集必要   │                                │
│  的信息开始     │                                │
│                │                                │
│  📚 加载参考资料 │                                │
│  ✓ 完成         │                                │
└───────────────┴────────────────────────────────┘
```

---

## 技术栈一览

| 层 | 技术 |
|----|------|
| Agent 框架 | Google ADK >= 1.0.0（回调、技能、Runner） |
| 大模型 | DeepSeek V4 Pro（通过 LiteLLM 适配器） |
| 后端 | Python + FastAPI + Uvicorn（SSE 流式推送） |
| 前端 | React 18 + Vite 5 + react-markdown |
| 技能管理 | SkillToolset（从 Markdown 目录自动加载技能） |

---

## 四个设计原则，值得反复强调

做这个项目时我们设了四条红线，每条都很重要：

1. **解说粒度在工具调用边界触发** — 不是每个 token 都翻译。Agent 内部流式输出几百个 token，但你不需要给每个 token 都生成卡片。"工具开始执行"和"工具执行完毕"才是用户关心的时间点。

2. **只翻译过程，绝不触碰最终输出** — 正文回复原样推送，该是什么就是什么。旁路解说只负责"过程可见性"。

3. **独立通道，完全隔离** — 卡片存在 `_narrator_cards` 里，正文存在 `parts[].text` 里，两个数据结构完全不交叉。前端各取各的，互不干扰。

4. **永不阻塞** — 翻译失败会产生日志，但不会抛异常、不会影响主流程。旁路就是旁路，不能变成瓶颈。

---

## 怎么跑起来？

三步：

```bash
# 1. 装依赖
uv sync

# 2. 配 API Key
echo 'DEEPSEEK_API_KEY=your-key' > .env

# 3. 分别启动后端和前端
python server.py &          # 后端 → localhost:8000
cd frontend && npm run dev  # 前端 → localhost:3000
```

或者用 CLI 直接玩：

```bash
python client.py                          # 交互模式
python client.py --skill data-analysis    # 数据分析演示
python client.py "分析客户流失数据"        # 自定义查询
```

---

## 总结

这个项目的核心贡献不是模型、不是算法，而是一个**架构模式**——把 AI Agent 的内部工作过程，从"技术人员的调试信息"变成"普通用户的过程进度"。

关键洞察就三个：

- **把输出分层**：正文、思考、工具调用各走各的通道
- **在旁路翻译**：翻译层不碰主流程，挂了也不影响 Agent
- **按节奏推送**：工具调用边界触发，不是每个 token 都解说

代码不到 500 行 Python + 200 行 React，但解决了 Agent 产品化中一个非常实际的 UX 问题。

如果你是做 AI Agent 产品的，强烈建议把这个模式纳入你的输出层设计。

---

*项目地址：`adk-samples/python/agents/skill-process-explain-agents`*
*基于 Google ADK 框架构建 | DeepSeek 模型驱动*
