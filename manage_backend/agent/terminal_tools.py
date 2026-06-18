"""终端工具 — 供优化智能体在指定路径下执行任意 shell 命令。

设计参考 hermes-agent/tools/terminal_tool.py 的工具面（前台执行 + 超时 +
合并 stdout/stderr + 工作目录），但去掉 hermes 内部耦合（多后端、容器/云沙箱、
后台任务注册、中断事件、脱敏、registry），只依赖标准库的 subprocess，
作为 ADK 原生可用的 FunctionTool。

把 run_command 直接放进 Agent(tools=[...])，ADK 会按函数签名 + docstring
自动包装为工具。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# 单次命令的硬性超时上限（秒），避免命令挂死阻塞智能体
MAX_TIMEOUT = 600

# 输出截断上限（字符），避免超长输出灌满上下文
MAX_OUTPUT_CHARS = 50_000


def run_command(command: str, cwd: str = ".", timeout: int = 120) -> dict:
    """在 shell 中执行任意命令，返回合并后的输出与退出码。

    命令通过系统默认 shell 执行（支持管道、重定向、&& 等）。stdout 与 stderr
    合并返回。命令超时会被终止并返回 timed_out=true。

    Args:
        command: 要执行的完整 shell 命令。
        cwd: 命令的工作目录，默认当前目录。
        timeout: 超时秒数，默认 120，上限 600。

    Returns:
        dict，含 status、command、cwd、exit_code、output、truncated、timed_out；
        出错时含 error。
    """
    work_dir = Path(cwd).expanduser().resolve()
    if not work_dir.exists():
        return {"error": f"工作目录不存在: {work_dir}", "command": command}
    if not work_dir.is_dir():
        return {"error": f"工作目录不是目录: {work_dir}", "command": command}

    timeout = max(1, min(int(timeout), MAX_TIMEOUT))

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + (e.stderr or "")
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        return {
            "status": "timeout",
            "command": command,
            "cwd": str(work_dir),
            "timed_out": True,
            "output": partial[:MAX_OUTPUT_CHARS],
            "error": f"命令在 {timeout}s 内未完成，已终止。",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "error": f"执行失败: {type(e).__name__}: {e}",
            "command": command,
            "cwd": str(work_dir),
        }

    output = (proc.stdout or "") + (proc.stderr or "")
    truncated = len(output) > MAX_OUTPUT_CHARS

    return {
        "status": "ok" if proc.returncode == 0 else "failed",
        "command": command,
        "cwd": str(work_dir),
        "exit_code": proc.returncode,
        "timed_out": False,
        "output": output[:MAX_OUTPUT_CHARS],
        "truncated": truncated,
    }
