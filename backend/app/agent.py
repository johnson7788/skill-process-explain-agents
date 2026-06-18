"""
云顶新耀 医学研究智能体 — 基于技能 + 旁路解说者架构

该智能体面向药企客户"云顶新耀"，提供医学文献检索、临床研究分析、
药物对比研究等专业医学研究能力。

架构：
- MAIN agent: 运行医学搜索和分析技能（多步骤、深度思考）
- NARRATOR layer (callbacks): 拦截工具调用、思考过程和结果，
  翻译为普通用户可理解的解说卡片
- 解说卡片存储在 session state 中，可随主输出一起展示

技能：
  1. medical-keyword-search — InfoX-Med 医学文献精确搜索
     支持中文/英文指南、系统评价/Meta分析、RCT 四类并行搜索、
     自由检索表达式、影响因子/时间筛选
  2. searxng — 互联网通用搜索（自部署 SearXNG 实例）
     支持通用、新闻、图片、视频搜索，可指定语言和搜索引擎
"""

from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from app.create_model import create_model
from app.narrator import (
    after_model_callback,
    after_tool_callback,
    before_tool_callback,
)

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
# Skills — 医学文献检索 + 互联网搜索
# ---------------------------------------------------------------------------

# Skill 1: 医学文献关键词搜索 — InfoX-Med API
medical_keyword_search_skill = load_skill_from_dir(
    SKILLS_DIR / "medical-keyword-search"
)

# Skill 2: 网页搜索 — 自部署 SearXNG 实例
searxng_search_skill = load_skill_from_dir(
    SKILLS_DIR / "searxng"
)

# ---------------------------------------------------------------------------
# SkillToolset — 自动生成 list_skills, load_skill, load_skill_resource, run_skill_script
# ---------------------------------------------------------------------------
skill_toolset = SkillToolset(
    skills=[
        medical_keyword_search_skill,
        searxng_search_skill,
    ]
)

# ---------------------------------------------------------------------------
# 模型 — 从 .env 读取 MODEL_PROVIDER 与 MODEL_NAME
# ---------------------------------------------------------------------------
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "deepseek")
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-v4-pro")

# ---------------------------------------------------------------------------
# 云顶新耀 医学研究智能体
# ---------------------------------------------------------------------------
root_agent = Agent(
    model=create_model(model=MODEL_NAME, provider=MODEL_PROVIDER),
    name="yundingxinyao_medical_agent",
    code_executor=UnsafeLocalCodeExecutor(),
    description=(
        "云顶新耀医学研究智能体 — 提供医学文献检索、临床研究分析、"
        "药物对比研究等专业医学研究服务，同时以旁路解说的方式"
        "实时向用户展示工作过程。"
    ),
    instruction=_INSTRUCTION,
    tools=[
        skill_toolset
    ],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_model_callback=after_model_callback,
)
