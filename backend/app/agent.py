"""
学术论文研究智能体 — 基于技能 + 旁路解说者架构

该智能体提供学术论文检索、研究综述、方向追踪等能力，并以旁路解说的
方式实时向用户展示工作过程。

架构：
- MAIN agent: 运行论文检索和分析技能（多步骤、深度思考）
- NARRATOR layer (callbacks): 拦截工具调用、思考过程和结果，
  翻译为普通用户可理解的解说卡片
- 解说卡片存储在 session state 中，可随主输出一起展示

技能：
  1. arxiv-paper-search — arXiv 学术论文检索
     支持按相关性/最新提交并行检索、按分类/作者检索、
     自由检索表达式
  2. bingsearch — 互联网通用搜索（Bing 搜索）
     支持通用、新闻、图片、视频搜索，可指定语言和搜索引擎
"""

from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.skills import load_skill_from_dir
from google.adk.tools import FunctionTool
from google.adk.tools.skill_toolset import SkillToolset

from app.create_model import create_model
from app.narrator import (
    after_model_callback,
    after_tool_callback,
    before_tool_callback,
)
from app.tools import terminal, todo, vision_analyze

load_dotenv()

# ---------------------------------------------------------------------------
# 目录常量
# ---------------------------------------------------------------------------
SKILLS_DIR = pathlib.Path(__file__).parent / "skills"
UPLOADS_DIR = pathlib.Path(__file__).parent.parent / "uploads"

# ---------------------------------------------------------------------------
# Instruction — 从 instruction.md 加载
# ---------------------------------------------------------------------------
_INSTRUCTION = (pathlib.Path(__file__).parent / "instruction.md").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Skills — 学术论文检索 + 互联网搜索
# ---------------------------------------------------------------------------

# Skill 1: arXiv 学术论文检索 — arXiv 公开 API
arxiv_paper_search_skill = load_skill_from_dir(
    SKILLS_DIR / "arxiv-paper-search"
)

# Skill 2: 网页搜索 — Bing 搜索
bing_search_skill = load_skill_from_dir(
    SKILLS_DIR / "bingsearch"
)

# ---------------------------------------------------------------------------
# SkillToolset — 自动生成 list_skills, load_skill, load_skill_resource, run_skill_script
# ---------------------------------------------------------------------------
skill_toolset = SkillToolset(
    skills=[
        arxiv_paper_search_skill,
        bing_search_skill,
    ]
)

# ---------------------------------------------------------------------------
# 模型 — 从 .env 读取 MODEL_PROVIDER 与 MODEL_NAME
# ---------------------------------------------------------------------------
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "deepseek")
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-v4-pro")

# ---------------------------------------------------------------------------
# 学术论文研究智能体
# ---------------------------------------------------------------------------
root_agent = Agent(
    model=create_model(model=MODEL_NAME, provider=MODEL_PROVIDER),
    name="arxiv_research_agent",
    code_executor=UnsafeLocalCodeExecutor(),
    description=(
        "学术论文研究智能体 — 提供 arXiv 论文检索、研究综述、"
        "方向追踪等服务，同时以旁路解说的方式"
        "实时向用户展示工作过程。"
    ),
    instruction=_INSTRUCTION,
    tools=[
        skill_toolset,
        FunctionTool(todo),
        FunctionTool(terminal),
        FunctionTool(vision_analyze),
    ],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_model_callback=after_model_callback,
)
