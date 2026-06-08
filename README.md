# 技能过程解说 Agent

基于 Google ADK 构建的智能体，执行长时间运行的技能任务（数据分析、研究综合），并通过**旁路解说者架构**将 Agent 的工具调用、思考过程与正文回复分离，以不同类型的输出推送给前端，让普通用户也能看懂 AI 在"幕后"做了什么。

---

## 核心问题

当 Agent 执行复杂的多步骤技能时，会产生大量**普通用户看不懂**的中间过程：

```
❌ 用户不应该看到这些：
   → 调用 load_skill(skill_name="data-analysis")
   → thought: "I need to first load the skill instructions, then..."
   → 调用 load_skill_resource(resource_path="references/analysis-methods.md")
   → thought: "Step 3 requires statistical modeling, let me consider..."
   → run_command(cmd="python analyze.py --input data.csv")
```

这些技术细节对用户毫无意义，甚至会造成困惑。本项目通过**旁路解说 Agent** 将这些内容翻译成普通用户能理解的解说卡片。

---

## 解决方案：分层输出架构

我们将 Agent 产生的所有内容按类型分成 **三个独立通道**，分别输出给前端：

```
用户提问
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                    主 Agent                           │
│         （执行技能、调用工具、深度思考）                  │
└──────────┬──────────────┬──────────────┬─────────────┘
           │              │              │
     ┌─────▼─────┐  ┌────▼─────┐  ┌─────▼─────┐
     │ 正文回复   │  │ 思考过程  │  │ 工具调用   │
     │ (text)    │  │(thought) │  │ (tool)    │
     └─────┬─────┘  └────┬─────┘  └─────┬─────┘
           │              │              │
           │        ┌─────▼─────┐  ┌─────▼──────┐
           │        │ 旁路解说   │  │ 旁路解说    │
           │        │ Agent     │  │ Agent      │
           │        │ 翻译思考   │  │ 翻译工具    │
           │        └─────┬─────┘  └─────┬──────┘
           │              │              │
           ▼              ▼              ▼
     ┌─────────┐  ┌────────────┐  ┌────────────┐
     │ 最终答案 │  │ 🧠 思考卡片 │  │ 📖 工具卡片 │
     │ 直接展示 │  │ "正在按照   │  │ "正在加载   │
     │ 给用户   │  │  方法论逐步  │  │  数据分析的 │
     │         │  │  推进分析"   │  │  专业指导"  │
     └─────────┘  └────────────┘  └────────────┘
```

### 三种输出类型

| 输出类型 | SSE 中的标识 | 前端展示方式 | 说明 |
|---------|-------------|------------|------|
| **正文回复** | `type: "text"` | 实时流式展示，作为主内容 | Agent 给用户的最终答案 |
| **思考过程** | `type: "thought"` | 折叠面板 / 侧边栏，经旁路解说翻译后展示 | 原始思考内容被翻译为通俗中文 |
| **工具调用** | `type: "narrator_card"` | 步骤时间线 / 进度条 | 技术工具名被翻译为友好标签 |

---

## 旁路解说 Agent 的工作原理

### 问题：工具名对用户不友好

Agent 内部使用的工具名是技术性的，普通用户完全看不懂：

| 原始工具名 | 用户看到的 | 用户理解吗？ |
|-----------|-----------|------------|
| `load_skill` | 加载技能指导 | ✅ 经过翻译 |
| `load_skill_resource` | 加载参考资料 | ✅ 经过翻译 |
| `list_skills` | 查看可用技能 | ✅ 经过翻译 |
| `run_command` | 执行系统命令 | ✅ 经过翻译 |
| `search_web` | 搜索信息 | ✅ 经过翻译 |

**如果不翻译**，用户看到的是：`调用 load_skill_resource(resource_path="references/analysis-methods.md")` — 这毫无意义。

### 解决方案：工具标签映射

旁路解说模块维护了一张 **工具名 → 友好标签** 的映射表（`narrator.py` 中的 `TOOL_LABELS`）：

```python
TOOL_LABELS = {
    "load_skill": {
        "label": "加载技能指导",        # 用户看到的标题
        "icon": "📖",                  # 配套图标
        "detail": "读取该技能的详细分步指导，了解正确的执行方法",  # 详细说明
    },
    "load_skill_resource": {
        "label": "加载参考资料",
        "icon": "📚",
        "detail": "查阅深度参考文档，确保分析质量和准确性",
    },
    # ... 更多映射
}
```

对于未预定义的工具名，还支持 **子串模式匹配**（以 `_` 开头的键）：

```python
"_search":   → "搜索信息" 🔍
"_load":     → "加载数据" 📂
"_generate": → "生成输出" ⚙️
"_validate": → "验证结果" ✅
"_analyze":  → "分析数据" 📊
```

最终兜底：将 `tool_name` 转为可读文本，如 `run_command` → `Run Command`。

### 问题：思考过程对用户不友好

Agent 的思考（thought）是原始的推理文本，通常包含：

```
❌ 原始思考（英文、技术化、冗长）：
"I need to first load the data analysis skill instructions, then
 check if there are reference materials available. Step 1 requires
 understanding the data structure before any cleaning..."

❌ 用户看到后的反应：这说了什么？跟我的问题有什么关系？
```

### 解决方案：思考模式匹配

旁路解说模块通过 **正则表达式模式匹配**（`THINKING_PATTERNS`）将原始思考翻译为简短的中文说明：

| 原始思考中的模式 | 翻译后的用户友好说明 |
|----------------|-------------------|
| `step 1`, `第一步`, `step 2` | "按照结构化方法论，逐步推进分析" |
| `need to verify`, `需要验证` | "正在验证信息，确保后续步骤的准确性" |
| `let me think`, `让我考虑` | "仔细思考问题，确保分析全面深入" |
| `first load`, `首先获取` | "先从收集必要的信息开始" |
| `summarize`, `总结`, `归纳` | "将多方面的信息整合成清晰的结论" |
| `edge case`, `边界情况` | "排查边缘情况和特殊情况，确保分析的鲁棒性" |
| `confident`, `confidence`, `unsure` | "评估分析结论的可信度" |
| `compare`, `cross.reference`, `交叉验证` | "交叉对比不同来源的信息，确保准确性" |
| `conclusion`, `结论`, `总结` | "基于前面的分析得出最终结论" |

> **设计原则**：每次 LLM 响应最多生成 **3 张**思考解说卡片，避免信息过载。

---

## 前端集成：SSE 流式输出格式

服务端（`server.py`）通过 SSE（Server-Sent Events）将三种类型的内容流式推送给前端：

### 正文回复事件

```json
{
  "type": "text",
  "text": "根据数据分析的结果..."
}
```

前端处理：直接渲染到主聊天区域，逐字流式展示。

### 思考过程事件

```json
{
  "type": "thought",
  "raw": "I need to first load the skill instructions...",
  "narrated": "先从收集必要的信息开始"
}
```

前端处理：可展示在折叠面板中（摘要显示 narrated 翻译，展开查看 raw 原文），或在侧边栏中展示。

### 解说卡片事件（实时增量推送）

每张卡片作为独立的 SSE 事件实时推送给前端：

```json
{
  "type": "narrator_card",
  "card": {
    "phase": "before_tool",
    "tool": "load_skill",
    "icon": "📖",
    "label": "加载技能指导",
    "detail": "读取该技能的详细分步指导，了解正确的执行方法",
    "args": "skill=data-analysis",
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
    "tool": "load_skill",
    "icon": "📖",
    "label": "加载技能指导 - 完成",
    "detail": "返回 45 行 (2340 字符)，开头: # Data Analysis Instructions",
    "status": "done"
  },
  "card_index": 1
}
```

### 流结束事件

```json
{
  "type": "done",
  "card_count": 7,
  "thought_count": 3
}
```

前端处理：卡片渲染为步骤时间线（带颜色编码的左边框），done 事件标记流结束。

### 前端展示建议

```
┌────────────────────────────────────────────────────────────┐
│  💬 主聊天区域（正文回复，实时流式）                          │
│                                                            │
│  根据对销售数据的完整分析，以下是关键发现：                     │
│  1. 华东地区营收同比增长 23%，是增长最快的区域...              │
│  2. 产品 B 的客户满意度最高（4.7/5.0）...                    │
│                                                            │
├──────────────────────┬─────────────────────────────────────┤
│  📊 过程解说（侧边栏）│                                     │
│                      │                                     │
│  📖 加载技能指导 ✓    │  ← 工具调用解说                      │
│    读取了数据分析的    │                                     │
│    分步指导           │                                     │
│                      │                                     │
│  🧠 思考过程          │  ← 思考解说                         │
│    先从收集必要的      │                                     │
│    信息开始           │                                     │
│                      │                                     │
│  📚 加载参考资料 ✓    │  ← 工具调用解说                      │
│    查阅了统计分析      │                                     │
│    方法参考文档       │                                     │
│                      │                                     │
│  🧠 思考过程          │  ← 思考解说                         │
│    按照结构化方法论，  │                                     │
│    逐步推进分析       │                                     │
└──────────────────────┴─────────────────────────────────────┘
```

---

## 架构设计

### 三个回调钩子

旁路解说通过 ADK 的三个回调实现，挂载在 Agent 上：

| 回调 | 触发时机 | 生成的卡片类型 | 作用 |
|------|---------|--------------|------|
| `before_tool_callback` | 工具执行前 | `status: "running"` | 告诉用户"即将做什么" |
| `after_tool_callback` | 工具执行后 | `status: "done"` | 告诉用户"刚才做了什么，结果如何" |
| `after_model_callback` | LLM 每次响应后 | `status: "info"` | 将思考过程翻译为通俗说明 |

### 关键设计原则

1. **解说粒度**：在工具调用边界触发（不是每个 token 都触发），避免信息洪水
2. **解说范围**：只翻译过程，绝不触碰最终输出 — 正文回复保持原样
3. **独立通道**：卡片存储在 session state 的 `_narrator_cards` 键下，与正文完全隔离
4. **永不阻塞**：解说失败被静默捕获并记录日志，绝不影响主 Agent 运行

### 项目结构

```
skill-process-explain-agents/
├── pyproject.toml              # 项目依赖与配置
├── client.py                   # CLI 客户端（命令行运行 Agent）
├── server.py                   # FastAPI 服务端（SSE 流式接口）
├── app/
│   ├── __init__.py
│   ├── agent.py                # 主 Agent：技能加载 + 回调绑定
│   ├── narrator.py             # 旁路解说模块：工具标签、思考翻译、回调函数
│   └── skills/
│       ├── data-analysis/      # 数据分析技能（5 步方法论）
│       │   ├── SKILL.md
│       │   └── references/
│       │       └── analysis-methods.md
│       └── research-synthesis/ # 研究综合技能（5 阶段方法论）
│           ├── SKILL.md
│           └── references/
│               └── synthesis-guide.md
└── frontend/                   # React 前端（实时展示解说内容）
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx             # 主界面：三通道渲染
        ├── App.css
        └── api.js              # SSE 流式客户端
```

---

## 快速开始

### 环境准备

```bash
# 安装依赖（推荐使用 uv）
uv sync

# 配置 API Key（使用 DeepSeek 模型）
# 复制 .env.example 并填入你的 API Key
cp .env.example .env
# 编辑 .env，填入: DEEPSEEK_API_KEY=your-key-here
```

### 命令行运行

```bash
# 交互模式（选择预设查询）
python client.py

# 运行特定技能的演示
python client.py --skill data-analysis
python client.py --skill research-synthesis

# 自定义查询
python client.py "分析客户流失数据"

# 显示 Agent 原始思考内容（调试用）
python client.py --verbose "研究 AI 伦理趋势"

# 指定服务端地址
python client.py --url http://localhost:9000 "分析销售数据"
```

### 服务端运行

```bash
# 启动服务（默认端口 8000）
python server.py

# 自定义端口
python server.py --port 8080
```

**API 接口：**

| 接口 | 方法 | 说明 |
|------|------|------|
| `/chat` | POST | 一次性对话，返回完整回复 + 解说卡片 |
| `/chat/stream` | GET | SSE 流式对话，实时推送回复和解说卡片 |
| `/docs` | GET | Swagger UI（在线调试） |

**测试请求：**

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"逐步分析销售数据"}'
```

---

## 解说卡片示例

一次完整的数据分析任务，用户看到的解说卡片如下：

```
====================================================================
  过程解说 — Agent 做了什么，为什么这么做
====================================================================

  [1] 📖 加载技能指导 …
      读取该技能的详细分步指导，了解正确的执行方法
      → 参数: skill=data-analysis

  [2] 📖 加载技能指导 - 完成 ✓
      返回 45 行 (2340 字符)，开头: # Data Analysis Instructions

  [3] 🧠 思考过程
      先从收集必要的信息开始

  [4] 📚 加载参考资料 …
      查阅深度参考文档，确保分析质量和准确性
      → 参数: skill=data-analysis, resource=analysis-methods

  [5] 📚 加载参考资料 - 完成 ✓
      返回 120 行 (5680 字符)，开头: # Analysis Methods Reference

  [6] 🧠 思考过程
      按照结构化方法论，逐步推进分析

  [7] 🧠 思考过程
      将多方面的信息整合成清晰的结论

====================================================================
  总计: 7 个步骤
====================================================================
```

---

## 如何扩展新的工具解说

当你给 Agent 添加了新工具，只需在 `narrator.py` 的 `TOOL_LABELS` 中添加映射。支持两种方式：

### 精确匹配（推荐）

直接添加工具名的完整映射：

```python
TOOL_LABELS = {
    # ... 已有映射 ...

    # 新增：命令行工具
    "run_command": {
        "label": "执行数据处理",
        "icon": "⚙️",
        "detail": "运行数据处理脚本，对原始数据进行清洗和转换",
    },
}
```

### 子串模式匹配

对于命名有规律的工具，使用 `_` 前缀的键进行模糊匹配（如 `_search` 匹配任何包含 `search` 的工具名）：

```python
TOOL_LABELS = {
    # ... 已有映射 ...

    # 匹配所有包含 "search" 的工具名
    "_search": {
        "label": "搜索信息",
        "icon": "🔍",
        "detail": "查找相关资料和信息",
    },
}
```

未匹配的工具名会自动转为标题大小写的可读文本（如 `run_command` → `Run Command`），并显示为 🔧 图标。

不需要修改 Agent 或回调逻辑，旁路解说会自动识别新工具并展示友好标签。

---

## 前端界面

项目包含一个 React 前端，通过 SSE 实时展示 Agent 的三通道输出。

### 技术栈

| 组件 | 说明 |
|------|------|
| **React 18** | UI 框架 |
| **Vite 5** | 构建工具（开发服务器端口 3000） |
| **react-markdown** + **remark-gfm** | Markdown 渲染（支持 GFM 表格） |

### 启动方式

```bash
cd frontend
npm install
npm run dev        # 开发模式，自动代理 /chat 到后端 localhost:8000
npm run build      # 生产构建（输出到 dist/）
```

### 三通道渲染

前端根据 SSE 事件的 `type` 字段将内容分发到不同展示区域：

| type | 渲染方式 | 视觉效果 |
|------|---------|---------|
| `text` | Markdown 正文 | 主聊天区域，流式展示 |
| `thought` | `<details>` 折叠面板 | 摘要显示翻译后的中文说明，展开查看原始思考 |
| `narrator_card` | 彩色边框卡片 | 橙色边框=running，绿色边框=done，紫色边框=info |
| `done` | 结束标记 | 停止流，汇总统计 |

### 设计要点

- **合并策略**：连续的同类 part（text/text、thought/thought）自动合并，减少 DOM 碎片
- **实时反馈**：流式过程中显示闪烁光标和"思考中"动画
- **可中断**：提供"停止"按钮，随时中止正在进行的请求

---

## 技术栈（后端）

| 组件 | 说明 |
|------|------|
| **Python >= 3.10** | 运行环境 |
| **google-adk >= 1.0.0** | Agent 开发框架（回调、技能、Runner） |
| **LiteLLM + DeepSeek** | 大模型接入（通过 LiteLLM 适配器） |
| **FastAPI + Uvicorn** | HTTP 服务端（SSE 流式推送） |
| **SkillToolset** | 技能管理（自动从 Markdown 目录加载技能） |

## 参考来源

- `agent-skills-tutorial` — 技能定义和 SkillToolset 模式
- `nexshift-agent` — 基于回调的输出格式化（OutputFormatter、after_model_callback）
- `解说者架构方案.html` — 旁路解说者架构设计文档
