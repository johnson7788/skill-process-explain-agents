#!/usr/bin/env python3
"""
技能过程解说 Agent — FastAPI 服务端

提供两个 HTTP 接口，将 Agent 输出按三种类型分离推送给前端：
  1. 正文回复  — type: "text"      → 实时流式，作为主聊天内容
  2. 思考过程  — type: "thought"   → 附带 narrated 翻译字段
  3. 工具解说  — type: "narrator_card" → 实时推送（边产生边发）

接口：
  POST /chat          一次性对话，返回完整 JSON（正文 + 思考 + 解说卡片）
  GET  /chat/stream   SSE 流式对话，实时推送三类事件
  GET  /docs          Swagger UI

用法：
    python server.py                    # 默认端口 8000
    python server.py --port 8080        # 自定义端口
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("DEEPSEEK_API_KEY"):
    print("错误: DEEPSEEK_API_KEY 未设置。")
    print("  请创建 .env 文件: DEEPSEEK_API_KEY=your-key")
    sys.exit(1)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from app.agent import root_agent
from app.narrator import (
    _explain_thinking,
    format_cards_for_display,
    get_narrator_cards,
)

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(
    title="技能过程解说 Agent",
    description=(
        "将 Agent 的工具调用、思考过程与正文回复分离，"
        "以不同类型的输出推送给前端，方便普通用户查看。"
    ),
)

# CORS — 允许前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 共享 Runner / Session Service
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    app_name="skill-explain-demo",
)

# session state 中解说卡片的键名
NARRATOR_STATE_KEY = "_narrator_cards"


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"


# ---------------------------------------------------------------------------
# 辅助：从 session state 实时读取解说卡片
# ---------------------------------------------------------------------------
async def _get_current_cards(user_id: str, session_id: str) -> list[dict]:
    """从 session state 获取当前已有的解说卡片列表。"""
    try:
        sess = await session_service.get_session(
            app_name="skill-explain-demo",
            user_id=user_id,
            session_id=session_id,
        )
        if sess and sess.state:
            return get_narrator_cards(sess.state)
    except Exception:
        pass
    return []


def _translate_thought(raw_text: str) -> str | None:
    """将原始思考文本翻译为用户友好的中文说明。"""
    if not raw_text or not raw_text.strip():
        return None
    return _explain_thinking(raw_text)


# ---------------------------------------------------------------------------
# POST /chat — 一次性对话：返回完整 JSON
# ---------------------------------------------------------------------------
@app.post("/chat")
async def chat(req: ChatRequest):
    """
    一次性对话接口。

    返回格式：
    ```json
    {
        "response": "正文回复全文",
        "thoughts": [
            {"raw": "原始思考", "narrated": "翻译后的思考"},
            ...
        ],
        "narrator_cards": [...],
        "card_count": 5,
        "event_count": 42
    }
    ```
    """
    session = await session_service.create_session(
        user_id=req.user_id, app_name="skill-explain-demo"
    )

    message = types.Content(
        role="user", parts=[types.Part.from_text(text=req.message)]
    )

    full_response: list[str] = []
    thoughts: list[dict] = []
    event_count = 0

    print(f"\n{'═' * 60}")
    print(f"  用户提问: {req.message[:100]}...")
    print(f"{'═' * 60}\n")

    async for event in runner.run_async(
        new_message=message,
        user_id=req.user_id,
        session_id=session.id,
        run_config=RunConfig(streaming_mode=StreamingMode.SSE),
    ):
        event_count += 1
        if event.content and event.content.parts:
            for part in event.content.parts:
                # 思考内容 — 翻译后存储
                if hasattr(part, "thought") and part.thought:
                    raw_text = (
                        part.text if hasattr(part, "text") and part.text else ""
                    ).strip()
                    if raw_text:
                        narrated = _translate_thought(raw_text)
                        thoughts.append({
                            "raw": raw_text,
                            "narrated": narrated,
                        })
                    continue
                # 正文内容
                if hasattr(part, "text") and part.text:
                    full_response.append(part.text)

    # 获取解说卡片
    cards = await _get_current_cards(req.user_id, session.id)

    # 终端输出（方便调试）
    print(f"  正文回复:\n{''.join(full_response)[:500]}...\n")
    if cards:
        print(format_cards_for_display(cards))

    return {
        "response": "".join(full_response),
        "thoughts": thoughts,
        "narrator_cards": cards,
        "card_count": len(cards),
        "event_count": event_count,
    }


# ---------------------------------------------------------------------------
# GET /chat/stream — SSE 流式对话
# ---------------------------------------------------------------------------
@app.get("/chat/stream")
async def chat_stream(message: str, user_id: str = "default_user"):
    """
    SSE 流式对话接口。

    SSE 事件类型：

    | type             | 字段                              | 前端用途           |
    |------------------|-----------------------------------|-------------------|
    | `text`           | `text`                            | 主聊天区，实时渲染   |
    | `thought`        | `raw`, `narrated`                 | 侧边栏/折叠面板     |
    | `narrator_card`  | `card` (单张卡片)                  | 步骤时间线/进度条   |
    | `done`           | `card_count`, `thought_count`     | 标记流结束          |
    """
    session = await session_service.create_session(
        user_id=user_id, app_name="skill-explain-demo"
    )

    async def event_generator():
        msg = types.Content(
            role="user", parts=[types.Part.from_text(text=message)]
        )

        # 追踪已发送的解说卡片数量，实现增量推送
        last_card_count = 0
        thought_count = 0

        async for event in runner.run_async(
            new_message=msg,
            user_id=user_id,
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            if not event.content or not event.content.parts:
                continue

            for part in event.content.parts:
                # ---- 思考内容 → type: "thought" ----
                if hasattr(part, "thought") and part.thought:
                    raw_text = (
                        part.text
                        if hasattr(part, "text") and part.text
                        else ""
                    ).strip()
                    if raw_text:
                        narrated = _translate_thought(raw_text)
                        thought_count += 1
                        yield _sse({
                            "type": "thought",
                            "raw": raw_text,
                            "narrated": narrated,
                        })
                    continue

                # ---- 正文内容 → type: "text" ----
                if hasattr(part, "text") and part.text:
                    yield _sse({
                        "type": "text",
                        "text": part.text,
                    })

            # ---- 增量推送新产生的解说卡片 → type: "narrator_card" ----
            current_cards = await _get_current_cards(user_id, session.id)
            while last_card_count < len(current_cards):
                yield _sse({
                    "type": "narrator_card",
                    "card": current_cards[last_card_count],
                    "card_index": last_card_count,
                })
                last_card_count += 1

        # ---- 流结束 → type: "done" ----
        final_cards = await _get_current_cards(user_id, session.id)
        # 推送可能遗漏的最后几张卡片
        while last_card_count < len(final_cards):
            yield _sse({
                "type": "narrator_card",
                "card": final_cards[last_card_count],
                "card_index": last_card_count,
            })
            last_card_count += 1

        yield _sse({
            "type": "done",
            "card_count": len(final_cards),
            "thought_count": thought_count,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(data: dict) -> str:
    """将字典序列化为 SSE data 行。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="启动技能过程解说 Agent 服务端")
    parser.add_argument(
        "--port", type=int, default=8000, help="服务端口 (默认: 8000)"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="服务地址 (默认: 0.0.0.0)"
    )
    args = parser.parse_args()

    import uvicorn

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  技能过程解说 Agent — 服务端                                      ║
║                                                                  ║
║  三类输出分离推送：                                                ║
║    type: "text"            正文回复 → 主聊天区                     ║
║    type: "thought"         思考过程 → 侧边栏（含 narrated 翻译）   ║
║    type: "narrator_card"   工具解说 → 步骤时间线（实时推送）        ║
║                                                                  ║
║  接口：                                                           ║
║    POST /chat          一次性对话，返回完整 JSON                   ║
║    GET  /chat/stream   SSE 流式对话，实时分类推送                   ║
║    GET  /docs          Swagger UI                                ║
║                                                                  ║
║  测试：                                                           ║
║    curl -X POST http://localhost:{args.port}/chat \\\\              ║
║      -H 'Content-Type: application/json' \\\\                      ║
║      -d '{{"message":"逐步分析销售数据"}}'                         ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
