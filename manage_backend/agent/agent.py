"""
优化智能体 — 基于 Google ADK 框架

架构：
- MAIN agent: 使用 optimize-agent skill + 文件工具，读取/修改指定路径下的
  Agent 的 agent.py、skills、instruction，基于运行日志进行优化。

文件操作通过 app/file_tools.py 提供的受控工具完成（读/写/编辑/搜索/列目录），
写改前自动备份。terminal_tools.py 额外提供 run_command，可在指定工作目录执行
任意 shell 命令（跑测试、查看 diff、验证启动等）。
"""

from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from agent.create_model import create_model
from agent.file_tools import (
    edit_file,
    list_dir,
    read_file,
    search_files,
    write_file,
)
from agent.terminal_tools import run_command

load_dotenv()

# ---------------------------------------------------------------------------
# 目录
# ---------------------------------------------------------------------------
SKILLS_DIR = pathlib.Path(__file__).parent / "skills"

# ---------------------------------------------------------------------------
# Instruction — 从 instruction.md 加载
# ---------------------------------------------------------------------------
_INSTRUCTION = (pathlib.Path(__file__).parent / "instruction.md").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Skill — optimize-agent
# ---------------------------------------------------------------------------
optimize_agent_skill = load_skill_from_dir(SKILLS_DIR / "optimize-agent")

skill_toolset = SkillToolset(skills=[optimize_agent_skill])

# ---------------------------------------------------------------------------
# 模型 — 从 .env 读取 MODEL_PROVIDER 与 MODEL_NAME
# ---------------------------------------------------------------------------
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "deepseek")
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-v4-pro")

# ---------------------------------------------------------------------------
# 优化智能体
# ---------------------------------------------------------------------------
root_agent = Agent(
    model=create_model(model=MODEL_NAME, provider=MODEL_PROVIDER),
    name="optimize_agent",
    description="优化智能体 — 分析给定智能体的 agent/skill 的运行日志，给出并应用优化方案",
    instruction=_INSTRUCTION,
    tools=[
        read_file,
        write_file,
        edit_file,
        list_dir,
        search_files,
        run_command,
        skill_toolset,
    ],
)
