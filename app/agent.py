"""
Skill Process Explain Agent — A skills-based agent with a narrator layer.

This agent demonstrates the "旁路解说者" (side-channel narrator) architecture:
- The MAIN agent runs skills (which involve long, multi-step processes with
  lots of thinking and tool calls)
- The NARRATOR layer (callbacks) intercepts tool calls, thinking, and results,
  translating them into user-friendly explanation cards
- These cards are stored in session state and can be displayed alongside
  or separately from the final output

Key design decisions (from 解说者架构方案.html):
  1. Narrator granularity: tool-call boundary triggers (not per-token)
  2. Narrator scope: only translates process, never touches final output
  3. Channel: cards stored in session state (SSE-free demo; extendable to SSE type:5)
  4. Never blocks: narrator failures never break the main agent

Reference implementations:
  - agent-skills-tutorial: skill definition and toolset patterns
  - nexshift-agent: callback-based output formatting
"""

import pathlib

from google.adk import Agent
from google.adk.models import LiteLlm
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from app.narrator import (
    after_model_callback,
    after_tool_callback,
    before_tool_callback,
)

# ---------------------------------------------------------------------------
# Skills — complex, multi-step processes that run long and involve deep thinking
# ---------------------------------------------------------------------------

# Skill 1: Data Analysis — 5-step methodology (load → clean → explore → model → report)
data_analysis_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "skills" / "data-analysis"
)

# Skill 2: Research Synthesis — 5-phase methodology with source evaluation
research_synthesis_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "skills" / "research-synthesis"
)

# ---------------------------------------------------------------------------
# SkillToolset — auto-generates list_skills, load_skill, load_skill_resource
# ---------------------------------------------------------------------------
skill_toolset = SkillToolset(
    skills=[
        data_analysis_skill,
        research_synthesis_skill,
    ]
)

# ---------------------------------------------------------------------------
# Root Agent — wires skills with narrator callbacks
# ---------------------------------------------------------------------------
root_agent = Agent(
    model=LiteLlm(model="deepseek/deepseek-v4-pro"),
    name="skill_explain_agent",
    description=(
        "An agent that performs complex multi-step analysis and research tasks "
        "while providing real-time user-friendly explanations of its process."
    ),
    instruction=(
        "You are an expert analysis and research assistant with specialized skills.\n\n"
        "You have two skills available:\n"
        "- **data-analysis**: Multi-step data analysis methodology (load, clean, explore, "
        "model, report) — load this when the user needs data analyzed\n"
        "- **research-synthesis**: Comprehensive research synthesis (scope, collect, "
        "evaluate, synthesize, report) — load this when the user needs topic research\n\n"
        "When the user asks a question:\n"
        "1. Identify which skill(s) are relevant to their request\n"
        "2. Call `load_skill` to get the detailed step-by-step instructions\n"
        "3. If the instructions reference additional materials, call "
        "`load_skill_resource` to access them\n"
        "4. Follow the skill's methodology carefully, completing each step "
        "before moving to the next\n"
        "5. Think through each step — do NOT rush. Consider edge cases, "
        "verify your reasoning, and explain your thinking\n"
        "6. Use `load_skill_resource` when the skill instructions tell you to "
        "read detailed reference materials\n"
        "7. Produce a final well-structured report or analysis\n\n"
        "Always tell the user which skill you're using and walk through "
        "your process step by step. Take your time — thoroughness is valued "
        "over speed."
    ),
    tools=[skill_toolset],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_model_callback=after_model_callback,
)
