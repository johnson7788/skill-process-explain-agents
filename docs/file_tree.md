# 项目文件结构与说明

> **云顶新耀 医学研究智能体** — 基于 Google ADK + DeepSeek 构建的医学研究 AI Agent，采用前后端分离架构，通过旁路解说者（Narrator）架构将 Agent 的工具调用与思考过程翻译为普通用户可理解的可视化卡片。

## 目录结构总览

```
agno_medical_science/
├── 📄 README.md                    # 项目总文档，介绍核心架构（分层输出 / 旁路解说者）
├── 📄 .env                         # 环境变量（DeepSeek API Key、InfoX-Med Token、端口等）
├── 📄 .gitignore                   # Git 忽略规则（.env、__pycache__、node_modules、dist 等）
├── 📄 .dockerignore                # Docker 构建排除规则（.env、.git、node_modules 等）
├── 📄 Dockerfile                   # Docker 镜像构建（Python 3.12 + Node.js 20 + Gunicorn）
├── 📄 docker-compose.yml           # Docker Compose 编排（容器名、端口映射、资源限制）
├── 📄 start.sh                     # 本地开发一键启动脚本（前后端并行，Ctrl+C 统一关闭）
├── 📄 deploy.sh                    # 生产部署脚本（git pull → docker build → 健康检查）
│
├── 🔧 backend/                     # 后端 — Python FastAPI + Google ADK
│   ├── 📄 pyproject.toml           # Python 项目配置（依赖：google-adk、fastapi、litellm 等）
│   ├── 📄 uv.lock                  # uv 包管理器锁文件
│   ├── 📄 env_example              # 环境变量示例（仅 DEEPSEEK_API_KEY）
│   ├── 📄 server.py                # FastAPI 主服务（SSE 流式/非流式聊天、文件上传、事件协议 v2）
│   ├── 📄 client.py                # 命令行客户端（模拟前端，消费 SSE 流并分类渲染三类输出）
│   │
│   └── 📂 app/                     # 后端核心应用包
│       ├── 📄 __init__.py           # 包初始化
│       ├── 📄 agent.py              # Agent 定义（Google ADK Agent + SkillToolset + 旁路回调）
│       ├── 📄 narrator.py           # 旁路解说者模块（拦截工具调用/思考 → 翻译为中文解说卡片）
│       ├── 📄 file_reader.py        # 文件读取模块（PDF/PPTX/PPT/文本，带页码/幻灯片位置标记）
│       │
│       ├── 📂 .adk/                 # Google ADK 运行时数据
│       │   └── 📄 session.db        # ADK 会话数据库（运行时自动生成）
│       │
│       └── 📂 skills/               # Agent 技能目录（ADK Skill 规范）
│           │
│           ├── 📂 medical-keyword-search/   # 技能 1：医学文献关键词搜索
│           │   ├── 📄 SKILL.md              # 技能说明文档（调用方式、参数、语法、示例）
│           │   ├── 📄 _meta.json            # 技能元数据（slug、版本、发布信息）
│           │   └── 📂 scripts/
│           │       └── 📄 medical_search.py # InfoX-Med API 搜索脚本（4 类文献并行搜索、布尔检索）
│           │
│           └── 📂 searxng/                  # 技能 2：互联网通用搜索
│               ├── 📄 SKILL.md              # 技能说明文档（搜索类型、参数、环境变量）
│               ├── 📄 _meta.json            # 技能元数据
│               ├── 📂 scripts/
│               │   └── 📄 search.py         # SearXNG 搜索脚本（带重试、诊断信息）
│               └── 📂 tests/
│                   └── 📄 test_search.py    # SearXNG 搜索脚本的单元测试
│
└── 🎨 frontend/                    # 前端 — React 19 + TypeScript + Vite + Tailwind CSS
    ├── 📄 index.html               # HTML 入口（挂载 #root → main.tsx）
    ├── 📄 package.json             # 前端依赖（react、react-markdown、lucide-react、motion 等）
    ├── 📄 package-lock.json        # npm 锁文件
    ├── 📄 vite.config.ts           # Vite 构建配置（React 插件、Tailwind、开发代理 → :8585）
    ├── 📄 tsconfig.json            # TypeScript 编译配置（ES2022、React JSX、路径别名）
    ├── 📄 metadata.json            # AI Studio 元数据
    ├── 📄 README.md                # 前端本地运行说明（AI Studio 模板遗留）
    ├── 📄 .env.example             # 环境变量示例（AI Studio 模板遗留）
    ├── 📄 .gitignore               # 前端 Git 忽略规则
    │
    ├── 📂 assets/                  # 静态资源目录
    │   └── 📂 .aistudio/           # AI Studio 配置
    │       └── 📄 .gitignore
    │
    └── 📂 src/                     # 前端源码
        ├── 📄 main.tsx             # React 入口（createRoot → App）
        ├── 📄 App.tsx              # 主应用组件（聊天界面、SSE 流式渲染、文件上传、Markdown 渲染）
        ├── 📄 api.ts               # API 客户端（SSE 流解析、文件上传/列表/清除）
        └── 📄 index.css            # 全局样式（Tailwind 导入、滚动条、Markdown 排版）
```

## 测试用例
耐赋康三期研究目标人群蛋白尿基线和泰它西普三期的对比。
有一些PPT和PDF，对其进行问答时，回答时引用ppt给出对应截图。本地上传文件回答时，对本地文件的参考和引用

## 核心文件详细说明

### 后端

| 文件 | 作用 |
|------|------|
| `server.py` | FastAPI 服务入口。提供 `GET /chat/stream`（SSE 流式）和 `POST /chat`（非流式）两个聊天接口，以及 `POST /upload`、`GET /uploads`、`DELETE /uploads` 文件管理接口。SSE 协议 v2 定义了 `text`、`thought`、`tool_step`、`tool_call`、`narrator_card`、`done` 六种事件类型。 |
| `app/agent.py` | 基于 Google ADK 定义根 Agent（`root_agent`），使用 DeepSeek 模型，挂载两个技能（medical-keyword-search、searxng），并注册 `before_tool_callback`、`after_tool_callback`、`after_model_callback` 三个旁路解说回调。 |
| `app/narrator.py` | 旁路解说者模块。拦截 Agent 的工具调用和思考过程，通过模式匹配将技术操作翻译为中文解说卡片（如"🔬 检索医学文献"、"🌐 互联网搜索"）。卡片存储在 `session.state["_narrator_cards"]` 中。 |
| `app/file_reader.py` | 统一文件读取模块。支持 PDF（逐页 + `[第X页]` 标记）、PPTX（逐幻灯片 + `[幻灯片X]` 标记）、旧版 PPT（OLE 二进制解析）、文本文件。所有输出带位置标记，方便 Agent 引用。 |
| `app/skills/medical-keyword-search/scripts/medical_search.py` | InfoX-Med API 搜索脚本。支持 4 类文献并行搜索（中文指南、英文指南、系统评价/Meta 分析、RCT），以及自由检索表达式模式。内置查询构造器（`QueryBuilder`）、筛选构造器（`FilterBuilder`）、参数校验和结果清洗。 |
| `app/skills/searxng/scripts/search.py` | SearXNG 搜索脚本。通过自部署 SearXNG 实例进行通用/新闻/图片/视频搜索，支持自动重试和诊断信息输出。 |
| `client.py` | 命令行客户端，模拟前端行为。连接 SSE 流，按 `type` 字段分类渲染正文、思考过程、解说卡片，适合调试和演示。 |

### 前端

| 文件 | 作用 |
|------|------|
| `src/App.tsx` | 主界面组件。包含聊天消息列表、流式实时渲染（打字机效果）、工具步骤折叠卡片、思考过程卡片、文件上传（拖拽 + 点击）、Markdown 渲染（含表格/代码块）。消费 SSE 事件并管理消息历史状态。 |
| `src/api.ts` | API 客户端层。封装 `streamChat`（SSE 异步生成器）、`postChat`（非流式）、`uploadFile`、`listUploads`、`clearUploads` 五个接口函数。 |
| `src/index.css` | 全局样式。基于 Tailwind CSS，自定义滚动条、Markdown 排版（标题/引用/表格/代码块）、textarea 样式。 |
| `vite.config.ts` | Vite 构建配置。集成 React 和 Tailwind 插件，开发服务器监听 3585 端口，将 `/chat`、`/upload`、`/uploads` 请求代理到后端 8585 端口。 |

### 部署与运维

| 文件 | 作用 |
|------|------|
| `start.sh` | 本地开发启动脚本。同时启动后端（`uv run python server.py --port 8585`）和前端（`npm run dev`），支持 `Ctrl+C` 统一关闭。 |
| `deploy.sh` | 生产环境部署脚本。自动执行环境检查 → `git pull` → `docker compose up --build` → 健康检查 → 状态展示。 |
| `Dockerfile` | 生产镜像构建。基于 Python 3.12-slim，安装 pandoc、LibreOffice、Node.js（PptxGenJS）、CJK 字体，使用 Gunicorn + UvicornWorker 运行。 |
| `docker-compose.yml` | 容器编排。映射端口、注入环境变量、限制 CPU 2 核 / 内存 2G。 |

## 数据流架构

```
用户提问
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                   server.py (FastAPI)                 │
│  接收请求 → 附加上传文件内容 → 调用 ADK Runner        │
└──────────────┬───────────────────────────┬────────────┘
               │                           │
               ▼                           ▼
┌─────────────────────────┐   ┌────────────────────────┐
│   app/agent.py (Agent)  │   │   app/narrator.py       │
│   DeepSeek + 技能调用    │──▶│  回调拦截 → 解说卡片    │
│   思考 → 工具 → 正文     │   │  存入 session state    │
└──────────┬──────────────┘   └───────────┬────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────────────────────────────────────┐
│              SSE 事件流 (协议 v2)                      │
│  text | thought | tool_step | tool_call | done        │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│             frontend (React + Tailwind)               │
│  src/api.ts → SSE 解析                                │
│  src/App.tsx → 打字机正文 / 折叠工具卡片 / 思考卡片    │
└──────────────────────────────────────────────────────┘
```

## 技能体系

| 技能 | 目录 | 用途 | 数据源 |
|------|------|------|--------|
| medical-keyword-search | `backend/app/skills/medical-keyword-search/` | 医学文献关键词精确搜索（指南、RCT、Meta 分析） | InfoX-Med API |
| searxng | `backend/app/skills/searxng/` | 互联网通用搜索（新闻、动态、非学术信息） | 自部署 SearXNG 实例 |
