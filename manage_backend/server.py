#!/usr/bin/env python3
"""
云顶新耀 智能体管理后端 — FastAPI 服务

端口: 8686（开发）

API:
  Logs:     GET /api/logs, GET /api/logs/{filename}, GET /api/logs/analyze,
            GET /api/logs/by-skills
  Optimize: GET /chat/optimize_stream  (SSE 流式对话)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# 也加载项目根目录的 .env（获取 DEEPSEEK_API_KEY 等）
_ROOT_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(_ROOT_ENV):
    load_dotenv(_ROOT_ENV)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("manage")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.agent import root_agent
from app.config import BACKEND_DIR
from app.agent_manager import get_agent_config
from app.skill_manager import list_skills, get_skill
from app.log_analyzer import list_logs, get_log, analyze_logs, get_logs_by_skills


# ---------------------------------------------------------------------------
# App + ADK runner
# ---------------------------------------------------------------------------

APP_NAME = "yundingxinyao-optimize"

app = FastAPI(title="云顶新耀 智能体管理后端")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    artifact_service=artifact_service,
    app_name=APP_NAME,
)


def _sse(data: dict) -> bytes:
    """序列化为 SSE 帧（data: ...\n\n）"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _friendly_tool_name(raw: str) -> str:
    mapping = {
        "list_skills": "列出 Skills",
        "load_skill": "加载 Skill 指导",
        "load_skill_resource": "加载 Skill 资源",
        "run_skill_script": "执行 Skill 脚本",
    }
    return mapping.get(raw, raw)


def _is_error_result(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    return bool(
        result.get("error")
        or result.get("status") == "error"
        or "Error" in str(result.get("output", ""))
    )

# ===========================================================================
# Skills API（只读列表，供 Optimize 页面选择 skill）
# ===========================================================================

@app.get("/api/skills")
def api_list_skills():
    """列出所有 Skills（供 Optimize 页面 skill 选择器使用）"""
    return list_skills()


# ===========================================================================
# Logs API
# ===========================================================================

@app.get("/api/logs")
def api_list_logs(limit: int = 50, q: str = ""):
    """列出日志文件，q 为关键词过滤（匹配用户消息）"""
    logs = list_logs(limit)
    if q:
        q_lower = q.lower()
        logs = [l for l in logs if q_lower in (l.get("user_message") or "").lower()]
    return logs


@app.get("/api/logs/analyze")
def api_analyze_all_logs():
    """分析所有日志，返回聚合统计和优化提示"""
    return analyze_logs()


@app.get("/api/logs/by-skills")
def api_logs_by_skills(skills: str = "", limit: int = 10):
    """
    获取与指定 skills 相关的日志记录。

    skills: 逗号分隔的 skill slug 列表
    """
    slugs = [s.strip() for s in skills.split(",") if s.strip()]
    return get_logs_by_skills(slugs, limit=limit)


@app.get("/api/logs/analyze/{filename}")
def api_analyze_log(filename: str):
    """分析单个日志文件"""
    result = analyze_logs(filename)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.get("/api/logs/{filename}")
def api_get_log(filename: str):
    """获取单个日志文件详情"""
    log = get_log(filename)
    if not log:
        raise HTTPException(status_code=404, detail=f"日志 '{filename}' 不存在")
    return log


# ===========================================================================
# Optimize API（LLM 驱动 — SSE 流式）
# ===========================================================================

def _build_context_message(message: str, skill_slugs: list[str], log_files: list[str]) -> str:
    """
    将 agent 配置、选中 skill 内容、待分析日志文件名打包到用户消息中。
    日志内容由 agent 在对话中自行读取，此处只传递文件名。
    """
    parts: list[str] = ["## 当前配置上下文（已自动加载）\n\n"]

    # Agent 配置
    try:
        cfg = get_agent_config()
        parts.append(
            f"需要优化的Agent项目: {BACKEND_DIR}"
            f"- **Agent名称**: {cfg.get('name')}\n"
            f"- **使用的模型**: {cfg.get('model')}\n\n"
        )
    except Exception as e:
        parts.append(f"### Agent 配置（读取失败: {e}）\n\n")

    # 选中 Skills
    if skill_slugs:
        parts.append("### 选中的 Skills\n\n")
        for slug in skill_slugs:
            skill_data = get_skill(slug)
            if not skill_data:
                parts.append(f"#### {slug}（未找到）\n\n")
                continue
            parts.append(f"#### Skill: {slug}\n")
            md = skill_data.get("skill_md_content", "")
            parts.append(f"**SKILL.md**:\n```markdown\n{md[:3000]}\n```\n\n")
            for fname, fcontent in skill_data.get("scripts_content", {}).items():
                parts.append(f"**{fname}**:\n```python\n{fcontent[:4000]}\n```\n\n")

    # 待分析的日志文件（用户在 Step 1 选定的）
    if log_files:
        parts.append("### 需要分析的日志文件\n\n")
        parts.append("用户已选定以下日志文件，请读取并分析后再提出优化建议：\n\n")
        for fname in log_files:
            parts.append(f"- `{BACKEND_DIR}/logs/{fname}`\n")
        parts.append("\n")

    parts.append(f"---\n\n## 用户的优化需求\n\n{message}")
    return "".join(parts)


@app.get("/chat/optimize_stream")
async def chat_optimize_stream(
    message: str,
    skills: str = "",
    log_files: str = "",
    user_id: str = "default_user",
):
    """
    优化 Agent 对话流式接口（SSE，Google ADK 协议）。

    Query params:
      message  — 用户输入的优化方向
      skills   — 逗号分隔的 skill slugs（选中要优化的 skills）
      user_id  — 用户标识（可选）

    SSE 事件类型（与主 backend /chat/stream 协议一致）:
      {"type": "text", "text": str}
      {"type": "thought", "raw": str, "narrated": str}
      {"type": "tool_step", "step_id": str, "summary": str, "calls": [...]}
      {"type": "tool_call", "step_id": str, "call_id": str, "status": str, "result_summary": str}
      {"type": "done", "text_len": int, "thought_count": int, "step_count": int}
      {"type": "error", "message": str}
    """
    skill_slugs = [s.strip() for s in skills.split(",") if s.strip()]
    log_file_list = [f.strip() for f in log_files.split(",") if f.strip()]
    logger.info(
        "optimize_stream: skills=%s, log_files=%s, message=%s",
        skill_slugs, log_file_list, message,
    )

    session = await session_service.create_session(user_id=user_id, app_name=APP_NAME)
    full_message = _build_context_message(message, skill_slugs, log_file_list)
    logger.info(f"形成的full_message: {full_message}")
    async def event_generator():
        msg = types.Content(role="user", parts=[types.Part.from_text(text=full_message)])

        thought_count = 0
        step_count = 0
        text_len = 0
        pending_calls: dict[str, str] = {}  # call_id → step_id

        try:
            async for event in runner.run_async(
                new_message=msg,
                user_id=user_id,
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                if not event.content or not event.content.parts:
                    continue
                if getattr(event, "partial", True) is False:
                    continue

                # ---- 工具调用事件 ----
                has_fc = any(
                    (hasattr(p, "function_call") and p.function_call)
                    or (hasattr(p, "function_response") and p.function_response)
                    for p in event.content.parts
                )
                if has_fc:
                    step_id = f"step_{step_count}"
                    calls_out = []
                    summary_parts = []

                    for part in event.content.parts:
                        if hasattr(part, "thought") and part.thought:
                            summary_parts.append((part.text or "").strip())
                        elif hasattr(part, "text") and part.text:
                            summary_parts.append(part.text.strip())
                        elif hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            cid = fc.id or str(uuid.uuid4())[:8]
                            calls_out.append({
                                "id": cid,
                                "tool_name": fc.name,
                                "display_name": _friendly_tool_name(fc.name),
                                "args_summary": json.dumps(fc.args or {}, ensure_ascii=False),
                                "status": "running",
                                "result_summary": None,
                            })
                            pending_calls[cid] = step_id
                        elif hasattr(part, "function_response") and part.function_response:
                            fr = part.function_response
                            rid = fr.id or ""
                            result_raw = fr.response or {}
                            result_str = json.dumps(result_raw, ensure_ascii=False)
                            status = "error" if _is_error_result(result_raw) else "done"
                            calls_out.append({
                                "id": rid,
                                "tool_name": fr.name,
                                "display_name": _friendly_tool_name(fr.name),
                                "args_summary": "",
                                "status": status,
                                "result_summary": result_str,
                            })
                            if rid in pending_calls:
                                yield _sse({
                                    "type": "tool_call",
                                    "step_id": pending_calls[rid],
                                    "call_id": rid,
                                    "status": status,
                                    "result_summary": result_str,
                                })
                                del pending_calls[rid]

                    if calls_out:
                        summary = (
                            " ".join(summary_parts)
                            or _friendly_tool_name(calls_out[0]["tool_name"])
                        )
                        yield _sse({
                            "type": "tool_step",
                            "step_id": step_id,
                            "summary": summary,
                            "call_count": len(calls_out),
                            "calls": calls_out,
                        })
                        step_count += 1
                    continue

                # ---- 思考 / 正文 ----
                for part in event.content.parts:
                    if hasattr(part, "thought") and part.thought:
                        raw = part.text or ""
                        if raw.strip():
                            thought_count += 1
                            yield _sse({"type": "thought", "raw": raw, "narrated": raw})
                        continue
                    if hasattr(part, "text") and part.text:
                        text_len += len(part.text)
                        yield _sse({"type": "text", "text": part.text})

            yield _sse({
                "type": "done",
                "text_len": text_len,
                "thought_count": thought_count,
                "step_count": step_count,
            })

        except Exception as exc:
            logger.error("optimize_stream error: %s", exc, exc_info=True)
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



# ===========================================================================
# Health
# ===========================================================================

@app.get("/health")
def health():
    return {"status": "ok", "service": "manage-backend"}


@app.get("/api/status")
def status():
    """管理后端状态，包含主 backend 的路径信息"""
    from app.config import BACKEND_DIR, SKILLS_DIR, LOGS_DIR

    return {
        "backend_dir": str(BACKEND_DIR),
        "skills_dir": str(SKILLS_DIR),
        "logs_dir": str(LOGS_DIR),
        "skills_count": len(list_skills()),
        "logs_count": len(list_logs()),
    }


# ===========================================================================
# 启动
# ===========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="云顶新耀 管理后端")
    parser.add_argument("--port", type=int, default=8686)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    import uvicorn

    logger.info(f"管理后端启动 — {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
