"""日志分析器 — 解析 backend/logs 的 JSONL 文件，提取优化洞察"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from collections import Counter

from app.config import LOGS_DIR


# ---------------------------------------------------------------------------
# 日志列表
# ---------------------------------------------------------------------------

def list_logs(limit: int = 50) -> list[dict]:
    """列出所有日志文件的基本信息"""
    logs = []
    if not LOGS_DIR.exists():
        return logs

    for f in sorted(LOGS_DIR.glob("*.jsonl"), reverse=True)[:limit]:
        size = f.stat().st_size
        # 从文件名解析时间和 session_id
        # 格式: 20260615_211245_a68f6ecf-256c-4d7d-bc44-0dd31383.jsonl
        parts = f.stem.split("_", 2)
        date_str = parts[0] if len(parts) >= 1 else ""
        time_str = parts[1] if len(parts) >= 2 else ""
        session_id = parts[2] if len(parts) >= 3 else f.stem

        # 读取第一行（meta）和最后一行（summary）
        meta = {}
        summary = {}
        try:
            lines = f.read_text(encoding="utf-8").strip().split("\n")
            if lines:
                meta = json.loads(lines[0])
            if len(lines) > 1:
                # 找最后的 summary 行
                for line in reversed(lines):
                    try:
                        record = json.loads(line)
                        if record.get("type") == "summary":
                            summary = record
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        logs.append(
            {
                "filename": f.name,
                "session_id": session_id,
                "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str,
                "time": f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:]}" if len(time_str) == 6 else time_str,
                "size_kb": round(size / 1024, 1),
                "event_count": summary.get("event_count", 0),
                "elapsed_seconds": summary.get("elapsed_seconds", 0),
                "user_message": meta.get("message", "")[:100],
            }
        )

    return logs


# ---------------------------------------------------------------------------
# 读取单个日志详情
# ---------------------------------------------------------------------------

def get_log(filename: str) -> dict | None:
    """读取完整的日志文件内容，聚合 token 流、构建时间线"""
    log_path = LOGS_DIR / filename
    if not log_path.exists():
        return None

    events = []
    try:
        for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return None

    # 按类型分组统计
    type_counter = Counter(e.get("type", "unknown") for e in events)

    # 提取关键事件
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    tool_steps = [e for e in events if e.get("type") == "tool_step"]
    thought_tokens = [e for e in events if e.get("type") == "thought"]
    errors = [e for e in events if e.get("type") == "error"]
    narrator_cards = [e for e in events if e.get("type") == "narrator_card"]
    text_tokens = [e for e in events if e.get("type") == "text"]
    meta_event = next((e for e in events if e.get("type") == "meta"), {})
    summary_event = next((e for e in events if e.get("type") == "summary"), {})
    done_event = next((e for e in events if e.get("type") == "done"), {})

    # 聚合 thought tokens → 完整思考文本
    full_thought = "".join(e.get("raw", "") for e in thought_tokens)

    # 聚合 text tokens → 完整回复文本
    full_text = "".join(e.get("text", e.get("content", "")) for e in text_tokens)

    # 工具调用摘要
    tool_summary = []
    for tc in tool_calls:
        tool_summary.append(
            {
                "tool": tc.get("tool_name", tc.get("tool", "unknown")),
                "status": tc.get("status", "unknown"),
                "args_preview": str(tc.get("args", ""))[:300],
                "result_preview": str(tc.get("result", ""))[:300],
            }
        )

    # tool_step 详情（含子调用）
    tool_step_details = []
    for ts in tool_steps:
        calls = ts.get("calls", [])
        tool_step_details.append(
            {
                "step_id": ts.get("step_id", ""),
                "summary": ts.get("summary", ""),
                "call_count": len(calls),
                "calls": [
                    {
                        "tool": c.get("tool_name", "unknown"),
                        "status": c.get("status", ""),
                        "args_summary": c.get("args_summary", ""),
                        "result_summary": c.get("result_summary", "")[:300],
                    }
                    for c in calls
                ],
            }
        )

    # 构建时间线阶段
    start_ts = meta_event.get("ts", events[0].get("ts", 0) if events else 0)

    def offset(ts_val):
        return round(ts_val - start_ts, 2) if ts_val else 0

    timeline_phases = []
    if thought_tokens:
        timeline_phases.append(
            {
                "phase": "思考",
                "start_offset": offset(thought_tokens[0].get("ts", start_ts)),
                "end_offset": offset(thought_tokens[-1].get("ts", start_ts)),
                "token_count": len(thought_tokens),
            }
        )
    if tool_steps:
        first_ts = tool_steps[0].get("ts", start_ts)
        last_ts = tool_steps[-1].get("ts", start_ts)
        timeline_phases.append(
            {
                "phase": "工具调用",
                "start_offset": offset(first_ts),
                "end_offset": offset(last_ts),
                "token_count": len(tool_steps),
            }
        )
    if text_tokens:
        timeline_phases.append(
            {
                "phase": "输出",
                "start_offset": offset(text_tokens[0].get("ts", start_ts)),
                "end_offset": offset(text_tokens[-1].get("ts", start_ts)),
                "token_count": len(text_tokens),
            }
        )

    return {
        "filename": filename,
        "meta": {
            "session_id": meta_event.get("session_id", ""),
            "user_id": meta_event.get("user_id", ""),
            "message": meta_event.get("message", ""),
            "start_time": meta_event.get("start_time", ""),
        },
        "summary": {
            "elapsed_seconds": summary_event.get("elapsed_seconds", 0),
            "event_count": summary_event.get("event_count", 0),
            "text_len": done_event.get("text_len", len(full_text)),
            "thought_count": done_event.get("thought_count", len(thought_tokens)),
            "step_count": done_event.get("step_count", len(tool_steps)),
        },
        "total_events": len(events),
        "event_types": dict(type_counter),
        "full_thought": full_thought,
        "full_response_text": full_text,
        "tool_calls": tool_summary,
        "tool_steps": tool_step_details,
        "errors": errors,
        "timeline_phases": timeline_phases,
        "narrator_cards": narrator_cards,
    }


# ---------------------------------------------------------------------------
# 日志分析 — 提取优化洞察
# ---------------------------------------------------------------------------

def analyze_logs(filename: str | None = None) -> dict:
    """
    分析日志，提取可优化的模式。

    如果 filename 为 None，分析所有日志。
    """
    if filename:
        files = [LOGS_DIR / filename]
    else:
        files = sorted(LOGS_DIR.glob("*.jsonl"))

    if not files or not files[0].exists():
        return {"status": "error", "message": "没有找到日志文件"}

    # 聚合统计
    all_tool_calls = []
    all_errors = []
    all_tool_names = Counter()
    total_sessions = 0
    total_elapsed = 0
    total_events = 0
    user_messages = []

    for f in files:
        try:
            events = []
            for line in f.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            total_sessions += 1

            for e in events:
                etype = e.get("type", "")
                total_events += 1

                if etype == "tool_call":
                    tool_name = e.get("tool_name", e.get("tool", "unknown"))
                    all_tool_names[tool_name] += 1
                    all_tool_calls.append(
                        {
                            "tool": tool_name,
                            "status": e.get("status", ""),
                            "session": f.stem,
                        }
                    )

                elif etype == "error":
                    all_errors.append(
                        {
                            "error": str(e.get("error", e.get("message", ""))),
                            "session": f.stem,
                        }
                    )

                elif etype == "summary":
                    total_elapsed += e.get("elapsed_seconds", 0)

                elif etype == "meta":
                    msg = e.get("message", "")
                    if msg:
                        user_messages.append(msg[:100])

        except Exception:
            continue

    # 生成分析报告
    avg_elapsed = round(total_elapsed / total_sessions, 1) if total_sessions else 0

    # 失败的工具调用
    failed_tools = [tc for tc in all_tool_calls if tc.get("status") in ("error", "failed")]
    success_tools = [tc for tc in all_tool_calls if tc.get("status") not in ("error", "failed")]

    # 每个会话摘要
    session_summaries = []
    for f in files:
        try:
            events = []
            for line in f.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            meta = next((e for e in events if e.get("type") == "meta"), {})
            summary = next((e for e in events if e.get("type") == "summary"), {})
            thought_count = sum(1 for e in events if e.get("type") == "thought")
            text_count = sum(1 for e in events if e.get("type") == "text")
            tool_count = sum(1 for e in events if e.get("type") == "tool_call")
            error_count = sum(1 for e in events if e.get("type") == "error")

            # 解析文件名时间
            parts = f.stem.split("_", 2)
            date_str = parts[0] if len(parts) >= 1 else ""
            time_str = parts[1] if len(parts) >= 2 else ""

            session_summaries.append(
                {
                    "filename": f.name,
                    "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str,
                    "time": f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:]}" if len(time_str) == 6 else time_str,
                    "user_message": meta.get("message", "")[:80],
                    "elapsed_seconds": summary.get("elapsed_seconds", 0),
                    "thought_tokens": thought_count,
                    "text_tokens": text_count,
                    "tool_calls": tool_count,
                    "errors": error_count,
                }
            )
        except Exception:
            continue

    return {
        "summary": {
            "total_sessions": total_sessions,
            "total_events": total_events,
            "avg_elapsed_seconds": avg_elapsed,
            "total_tool_calls": len(all_tool_calls),
            "failed_tool_calls": len(failed_tools),
            "success_rate": (
                f"{len(success_tools) / len(all_tool_calls) * 100:.1f}%"
                if all_tool_calls
                else "N/A"
            ),
            "total_errors": len(all_errors),
        },
        "tool_usage": dict(all_tool_names.most_common()),
        "user_messages": user_messages,
        "failed_tool_details": failed_tools[:20],
        "error_details": all_errors[:20],
        "session_summaries": session_summaries,
        "optimization_hints": _generate_hints(
            all_tool_calls, all_errors, all_tool_names, total_sessions
        ),
    }


# ---------------------------------------------------------------------------
# 按 Skill 筛选日志
# ---------------------------------------------------------------------------

def get_logs_by_skills(skill_slugs: list[str], limit: int = 10) -> list[dict]:
    """
    返回与指定 skill(s) 相关的日志摘要。

    判断依据：日志中的 tool_step 事件的 calls[].result_summary 包含 skill slug
    （run_skill_script / load_skill / load_skill_resource 的返回值均带有 "skill_name": "<slug>"）。
    """
    if not skill_slugs or not LOGS_DIR.exists():
        return []

    results: list[dict] = []
    for log_info in list_logs(100):
        if len(results) >= limit:
            break

        log_path = LOGS_DIR / log_info["filename"]
        try:
            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        except Exception:
            continue

        relevant_steps: list[dict] = []
        errors: list[dict] = []

        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")

            if etype == "tool_step":
                for call in event.get("calls", []):
                    result_summary = call.get("result_summary", "")
                    if any(slug in result_summary for slug in skill_slugs):
                        relevant_steps.append(
                            {
                                "tool": call.get("tool_name", "unknown"),
                                "status": call.get("status", ""),
                                "result_preview": result_summary[:200],
                            }
                        )

            elif etype == "error":
                errors.append(event)

        if not relevant_steps:
            continue

        results.append(
            {
                "filename": log_info["filename"],
                "date": log_info.get("date", ""),
                "time": log_info.get("time", ""),
                "user_message": log_info.get("user_message", ""),
                "relevant_tool_calls": relevant_steps[:5],
                "errors": errors[:3],
            }
        )

    return results


def _generate_hints(
    tool_calls: list,
    errors: list,
    tool_names: Counter,
    sessions: int,
) -> list[str]:
    """基于日志数据生成优化提示"""
    hints = []

    # 检查工具失败率
    failed = [tc for tc in tool_calls if tc.get("status") in ("error", "failed")]
    if tool_calls and len(failed) / len(tool_calls) > 0.2:
        hints.append(
            f"⚠️ 工具调用失败率较高 ({len(failed)}/{len(tool_calls)})，"
            "建议检查 skill 脚本的稳定性和参数校验逻辑"
        )

    # 检查是否有频繁使用的工具
    if tool_names:
        most_used = tool_names.most_common(1)[0]
        if most_used[1] > sessions * 3:
            hints.append(
                f"💡 工具 '{most_used[0]}' 使用频率很高 ({most_used[1]} 次)，"
                "考虑在 instruction 中添加更具体的使用指引"
            )

    # 检查错误模式
    error_messages = [e["error"] for e in errors]
    if error_messages:
        error_counter = Counter(error_messages)
        for msg, count in error_counter.most_common(3):
            if count > 1:
                hints.append(
                    f"🔴 重复错误: '{msg[:80]}' 出现 {count} 次，需要在 skill 中增加错误处理"
                )

    # 通用建议
    if sessions >= 5:
        hints.append(
            "📊 建议查看用户提问分布，确认 skill 是否覆盖了最常见的查询场景"
        )

    if not tool_names:
        hints.append(
            "ℹ️ 暂无工具调用记录，可能是用户只进行了简单问答"
        )

    return hints
