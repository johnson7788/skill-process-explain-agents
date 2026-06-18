"""企业 Agent 自定义工具。

P1 工具：
- todo:     任务规划/进度跟踪，状态存于 tool_context.state（单次会话内有效）
- terminal: 在服务器上执行 shell 命令（高权限，请在受信部署边界内使用）

注册方式见 app/agent.py：用 FunctionTool 包装后加入 tools=[...]。
"""

from __future__ import annotations

import subprocess

from google.adk.tools import ToolContext

# ---------------------------------------------------------------------------
# todo — 任务规划
# ---------------------------------------------------------------------------
_TODO_KEY = "_todo_list"
_VALID_STATUS = {"pending", "in_progress", "completed", "cancelled"}
_MAX_ITEMS = 256
_MAX_CONTENT = 4000


def todo(tool_context: ToolContext, todos: list[dict] | None = None) -> dict:
    """管理本次任务的待办清单，用于拆解复杂任务并跟踪进度。

    用法：
    - 传入 todos 写入/覆盖整张清单；不传则只读取当前清单。
    - 每个待办项为 {"id": str, "content": str, "status": "..."}，
      status 取值：pending / in_progress / completed / cancelled。
    - 列表顺序即优先级。复杂任务（>=3 步）开始时先写清单，
      每完成一步立即把对应项更新为 completed，并把下一项设为 in_progress。

    返回当前完整清单 {"todos": [...]}。
    """
    items = list(tool_context.state.get(_TODO_KEY, []))
    if todos is not None:
        cleaned: list[dict] = []
        for t in todos[:_MAX_ITEMS]:
            if not isinstance(t, dict):
                continue
            status = str(t.get("status", "pending")).strip().lower()
            cleaned.append({
                "id": str(t.get("id", "")).strip() or str(len(cleaned) + 1),
                "content": str(t.get("content", "")).strip()[:_MAX_CONTENT],
                "status": status if status in _VALID_STATUS else "pending",
            })
        items = cleaned
        tool_context.state[_TODO_KEY] = items
    return {"todos": items}


# ---------------------------------------------------------------------------
# terminal — shell 命令执行
# ---------------------------------------------------------------------------
_TERMINAL_MAX_STDOUT = 8000
_TERMINAL_MAX_STDERR = 2000


def terminal(command: str, timeout: int = 60) -> dict:
    """在服务器上执行 shell 命令并返回输出。

    适用于查看文件、运行构建/检索脚本、查询系统信息等。
    注意：这是高权限能力，仅在你明确知道命令安全时使用。

    参数：
    - command: 要执行的 shell 命令。
    - timeout: 超时秒数（默认 60）。

    返回 {"stdout", "stderr", "returncode"}；超时返回 {"error"}。
    """
    if not command or not command.strip():
        return {"error": "command 不能为空"}
    try:
        r = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": r.stdout[-_TERMINAL_MAX_STDOUT:],
            "stderr": r.stderr[-_TERMINAL_MAX_STDERR:],
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"命令超时（>{timeout}s）"}
    except Exception as e:  # noqa: BLE001 — 工具边界，统一回报给模型
        return {"error": str(e)}
