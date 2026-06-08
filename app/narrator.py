"""
Narrator / Explainer module for skill-based agents.

Translates raw tool calls, thinking processes, and technical outputs into
user-friendly explanation cards. This is a programmatic "旁路解说者"
(side-channel narrator) that intercepts agent activity and renders it
in plain language — without blocking the main agent's workflow.

Architecture inspired by:
- 解说者架构方案.html (side-channel narrator design)
- nexshift-agent's OutputFormatter (content-type detection + formatting)
- nexshift-agent's after_model_callback (transparent interception)

Cards are stored in session.state["_narrator_cards"] for retrieval
by client code or frontend displays.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.context import Context
from google.adk.models import LlmResponse
from google.adk.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session state key for storing narrator cards
# ---------------------------------------------------------------------------
NARRATOR_STATE_KEY = "_narrator_cards"

# ---------------------------------------------------------------------------
# Tool name → user-friendly label mapping
# ---------------------------------------------------------------------------
TOOL_LABELS: dict[str, dict[str, str]] = {
    # Skill tools
    "list_skills": {
        "label": "查看可用技能",
        "icon": "📋",
        "detail": "检查当前有哪些专业技能可以用来处理这个任务",
    },
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
    # Generic fallback patterns
    "_search": {
        "label": "搜索信息",
        "icon": "🔍",
        "detail": "查找相关资料和信息",
    },
    "_load": {
        "label": "加载数据",
        "icon": "📂",
        "detail": "获取所需的数据和资源",
    },
    "_generate": {
        "label": "生成输出",
        "icon": "⚙️",
        "detail": "根据处理结果生成结构化输出",
    },
    "_validate": {
        "label": "验证结果",
        "icon": "✅",
        "detail": "检查输出质量和正确性",
    },
    "_save": {
        "label": "保存结果",
        "icon": "💾",
        "detail": "保存结果以备后续使用",
    },
    "_analyze": {
        "label": "分析数据",
        "icon": "📊",
        "detail": "处理和分析数据，提取洞察",
    },
}

# ---------------------------------------------------------------------------
# Thinking → explanation mapping (pattern-based)
# ---------------------------------------------------------------------------
THINKING_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)step\s*\d|第\s*\d+\s*步", "按照结构化方法论，逐步推进分析"),
    (r"(?i)need to (check|verify|confirm)|需要(检查|验证|确认)", "正在验证信息，确保后续步骤的准确性"),
    (r"(?i)let me (think|consider|analyze)|让我(想想|考虑|分析)", "仔细思考问题，确保分析全面深入"),
    (r"(?i)first.{0,20}(load|read|fetch|get)|首先(加载|读取|获取)", "先从收集必要的信息开始"),
    (r"(?i)summarize|synthesize|combine|总结|归纳|整合", "将多方面的信息整合成清晰的结论"),
    (r"(?i)edge case|corner case|boundary|边缘|极端|边界", "排查边缘情况和特殊情况，确保分析的鲁棒性"),
    (r"(?i)confident|confidence|unsure|verify|置信|确定|验证", "评估分析结论的可信度"),
    (r"(?i)compare|cross.reference|validate against|对比|交叉验证", "交叉对比不同来源的信息，确保准确性"),
    (r"(?i)conclusion|finally|in summary|overall|结论|总结|最终", "基于前面的分析得出最终结论"),
]


def _find_tool_label(tool_name: str) -> dict[str, str]:
    """Find the best matching label for a tool, falling back to pattern matching."""
    if tool_name in TOOL_LABELS:
        return TOOL_LABELS[tool_name]

    for pattern, info in TOOL_LABELS.items():
        if pattern.startswith("_") and pattern[1:] in tool_name.lower():
            return info

    # Ultimate fallback
    return {
        "label": tool_name.replace("_", " ").title(),
        "icon": "🔧",
        "detail": f"正在执行 {tool_name}",
    }


def _explain_thinking(text: str) -> str | None:
    """Try to match thinking text to a user-friendly explanation."""
    for pattern, explanation in THINKING_PATTERNS:
        if re.search(pattern, text):
            return explanation
    return None


def _truncate(s: str, max_len: int = 200) -> str:
    """Truncate a string for display, adding ellipsis if needed."""
    if len(s) <= max_len:
        return s
    return s[:max_len] + "…"


def _summarize_args(args: dict[str, Any]) -> str:
    """Create a human-readable summary of tool arguments."""
    if not args:
        return ""

    parts = []
    for key, value in args.items():
        if isinstance(value, str):
            parts.append(f"{key}={_truncate(value, 80)}")
        elif isinstance(value, (int, float, bool)):
            parts.append(f"{key}={value}")
        elif isinstance(value, list):
            parts.append(f"{key}=[{len(value)} items]")
        elif isinstance(value, dict):
            parts.append(f"{key}={{...}}")
        else:
            parts.append(f"{key}=...")

    return ", ".join(parts)


def _summarize_result(result: Any) -> str:
    """Create a human-readable summary of a tool result."""
    if result is None:
        return "无返回内容"

    if isinstance(result, str):
        lines = result.strip().split("\n")
        line_count = len(lines)
        char_count = len(result)
        first_line = _truncate(lines[0].strip(), 120) if lines else ""

        if line_count == 1:
            return f"返回: {_truncate(result, 200)}"
        else:
            return (
                f"返回 {line_count} 行 ({char_count} 字符)，"
                f"开头: {first_line}"
            )

    if isinstance(result, dict):
        keys = list(result.keys())
        if "error" in keys:
            return f"错误: {_truncate(str(result['error']), 150)}"
        return f"返回结构化数据，包含 {len(keys)} 个字段: {', '.join(keys[:5])}"

    if isinstance(result, list):
        return f"返回列表，共 {len(result)} 条数据"

    return _truncate(str(result), 200)


# ===========================================================================
# Callback Functions
# ===========================================================================


def before_tool_callback(
    *, tool: BaseTool, args: dict[str, Any], tool_context: Context
) -> dict[str, Any] | None:
    """
    Called before each tool execution. Adds a narrator card explaining
    what the agent is about to do, in plain language.

    ADK calls with keyword args:
      callback(tool=tool, args=args, tool_context=tool_context)

    Returns None (no modification to the tool call) but stores a card
    in session state.
    """
    tool_name = tool.name
    info = _find_tool_label(tool_name)
    args_summary = _summarize_args(args)

    card = {
        "phase": "before_tool",
        "tool": tool_name,
        "icon": info["icon"],
        "label": info["label"],
        "detail": info["detail"],
        "args": args_summary,
        "status": "running",
    }

    _store_card(tool_context, card)
    return None  # Don't modify the tool call


def after_tool_callback(
    *, tool: BaseTool, args: dict[str, Any], tool_context: Context, tool_response: Any
) -> Any:
    """
    Called after each tool execution. Adds a narrator card explaining
    what the tool produced, in plain language.

    ADK calls with keyword args:
      callback(tool=tool, args=args, tool_context=tool_context, tool_response=response)

    Returns the result unchanged but stores a completion card in session state.
    """
    tool_name = tool.name
    info = _find_tool_label(tool_name)
    result_summary = _summarize_result(tool_response)

    card = {
        "phase": "after_tool",
        "tool": tool_name,
        "icon": info["icon"],
        "label": f"{info['label']} - 完成",
        "detail": result_summary,
        "status": "done",
    }

    _store_card(tool_context, card)
    return tool_response  # Don't modify the result


def after_model_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """
    Called after each LLM response. Analyzes the thinking/reasoning in the
    response and may add a commentary card. Also can add a process summary
    card if the response contains final answer content.

    Returns None to use original response, or a modified LlmResponse.
    """
    if not llm_response or not llm_response.content or not llm_response.content.parts:
        return None

    has_thinking = False
    thinking_explanations = []

    for part in llm_response.content.parts:
        # Check for thought/reasoning content
        if hasattr(part, "thought") and part.thought:
            has_thinking = True
            text = part.text if hasattr(part, "text") and part.text else str(part.thought)
            explanation = _explain_thinking(text)
            if explanation:
                thinking_explanations.append(explanation)
            continue

        # Check for text parts that look like thinking (but aren't marked as thought)
        if hasattr(part, "text") and part.text and not getattr(part, "thought", False):
            text = part.text
            if re.search(
                r"(?i)(let me|I need to|I should|first.{0,10}I|step \d)"
                r"|(让我|我需要|首先|第一步|接下来|然后|现在|好的|我来)",
                text,
            ):
                has_thinking = True
                explanation = _explain_thinking(text)
                if explanation:
                    thinking_explanations.append(explanation)

    if thinking_explanations:
        for explanation in thinking_explanations[:3]:  # Cap at 3 to avoid noise
            card = {
                "phase": "thinking",
                "icon": "🧠",
                "label": "思考过程",
                "detail": explanation,
                "status": "info",
            }
            _store_card(callback_context, card)

    return None  # Don't modify the LLM response


# ===========================================================================
# Helper Functions
# ===========================================================================


def _store_card(ctx: Context, card: dict[str, Any]) -> None:
    """
    Store a narrator card in session state for later retrieval.

    Appends to a list stored at NARRATOR_STATE_KEY in the session state.
    Uses ADK's State dict-like interface: read via .get(), write via []=.
    """
    try:
        state = ctx.state
        if state is None:
            return

        # state is a google.adk.sessions.state.State object — supports dict-like ops
        cards: list[dict[str, Any]] = state.get(NARRATOR_STATE_KEY, [])
        cards.append(card)
        state[NARRATOR_STATE_KEY] = cards
    except Exception:
        logger.debug("Could not store narrator card in session state", exc_info=True)


def get_narrator_cards(session_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Retrieve all narrator cards stored in session state.

    Args:
        session_state: The session state dict from the runner.

    Returns:
        List of narrator card dicts, or empty list if none found.
    """
    if not session_state:
        return []
    return session_state.get(NARRATOR_STATE_KEY, [])


def format_cards_for_display(cards: list[dict[str, Any]]) -> str:
    """
    Format a list of narrator cards into a readable text display.

    Used by client.py to show the narrated process to users.
    """
    if not cards:
        return "(无解说数据)"

    lines = []
    lines.append("=" * 68)
    lines.append("  过程解说 — Agent 做了什么，为什么这么做")
    lines.append("=" * 68)

    for i, card in enumerate(cards, 1):
        icon = card.get("icon", "•")
        label = card.get("label", "")
        detail = card.get("detail", "")
        status = card.get("status", "")
        tool = card.get("tool", "")

        status_mark = "✓" if status == "done" else "…" if status == "running" else ""

        lines.append(f"\n  [{i}] {icon} {label} {status_mark}")
        if detail:
            lines.append(f"      {detail}")

        phase = card.get("phase", "")
        if phase == "before_tool" and card.get("args"):
            lines.append(f"      → 参数: {card['args']}")

    lines.append("\n" + "=" * 68)
    lines.append(f"  总计: {len(cards)} 个步骤")
    lines.append("=" * 68)

    return "\n".join(lines)


def format_cards_as_conversation(cards: list[dict[str, Any]]) -> str:
    """
    Format narrator cards as a natural-language conversation,
    suitable for non-technical users.
    """
    if not cards:
        return ""

    lines = ["\n--- 幕后过程 ---"]
    for card in cards:
        icon = card.get("icon", "")
        detail = card.get("detail", "")
        label = card.get("label", "")
        status = card.get("status", "")

        if status == "running":
            lines.append(f"  {icon} {detail}")
        elif status == "done":
            lines.append(f"  {icon} {detail}")
        elif status == "info":
            lines.append(f"  {icon} {label}: {detail}")
        else:
            lines.append(f"  {icon} {label}")

    lines.append("---")
    return "\n".join(lines)
