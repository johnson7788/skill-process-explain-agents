"""文件操作工具 — 供优化智能体读改「指定路径」下的 Agent 文件。

设计参考 hermes-agent/tools/file_tools.py 的工具面（分页读取带行号、写入、
replace 式编辑、搜索），但去掉了 hermes 内部耦合（task_id 工作区、dedup/staleness
跟踪、cross-profile 守卫、脱敏、registry），改成只依赖标准库、ADK 原生可用的
FunctionTool。

安全约定（与 skills/optimize-agent/SKILL.md 的红线一致）：
- 写入/编辑已存在的文件前，先自动备份为 `<文件名>.bak.<时间戳>`（同目录）。
- read 拒绝读取二进制文件。
- 每个操作都回报实际操作的绝对路径，便于核对。

把这些函数直接放进 Agent(tools=[...])，ADK 会按函数签名 + docstring 自动包装为工具。
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import time
from pathlib import Path

# 读取上限：避免一次性把超大文件灌进上下文
MAX_READ_CHARS = 200_000

# 二进制扩展名（read 直接拒绝）
_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".pdf", ".zip", ".gz", ".tar", ".bz2", ".7z", ".rar",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".bin", ".o", ".a",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".sqlite", ".db", ".pkl", ".npy", ".npz",
}


def _resolve(path: str) -> Path:
    """把传入路径解析成绝对路径（不强制限定根目录，但回报绝对路径便于核对）。"""
    return Path(path).expanduser().resolve()


def _backup(p: Path) -> str | None:
    """已存在的文件在改写前备份为 <name>.bak.<时间戳>，返回备份路径；新文件返回 None。"""
    if not p.exists():
        return None
    bak = p.with_name(f"{p.name}.bak.{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(p, bak)
    return str(bak)


def read_file(path: str, offset: int = 1, limit: int = 500) -> dict:
    """读取文本文件，带行号、分页。

    Args:
        path: 文件路径（绝对或相对）。
        offset: 起始行号（从 1 开始）。
        limit: 最多读取多少行。

    Returns:
        dict，含 content（带行号）、total_lines、file_size、truncated、
        以及超过本页时的 next_offset 提示；出错时含 error。
    """
    p = _resolve(path)
    if not p.exists():
        return {"error": f"文件不存在: {p}"}
    if p.is_dir():
        return {"error": f"这是目录不是文件: {p}。请用 list_dir。"}
    if p.suffix.lower() in _BINARY_EXTS:
        return {"error": f"拒绝读取二进制文件 ({p.suffix}): {p}"}

    offset = max(1, offset)
    limit = max(1, limit)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return {"error": f"读取失败: {type(e).__name__}: {e}", "path": str(p)}

    lines = text.splitlines()
    total = len(lines)
    end = offset + limit - 1
    page = lines[offset - 1:end]
    numbered = "\n".join(f"{offset + i:>6}\t{line}" for i, line in enumerate(page))

    if len(numbered) > MAX_READ_CHARS:
        return {
            "error": (
                f"本页 {len(numbered):,} 字符超过安全上限 {MAX_READ_CHARS:,}，"
                "请缩小 limit 再读。"
            ),
            "path": str(p),
            "total_lines": total,
        }

    result = {
        "path": str(p),
        "content": numbered,
        "total_lines": total,
        "file_size": p.stat().st_size,
        "truncated": total > end,
    }
    if result["truncated"]:
        result["next_offset"] = end + 1
        result["hint"] = f"还有更多内容，用 offset={end + 1} 继续读（共 {total} 行）。"
    return result


def write_file(path: str, content: str) -> dict:
    """把内容整体写入文件（覆盖）。已存在的文件会先自动备份。

    Args:
        path: 目标文件路径。
        content: 要写入的完整文本内容。

    Returns:
        dict，含 status、resolved_path、backup（备份路径或 None）；出错时含 error。
    """
    p = _resolve(path)
    if p.is_dir():
        return {"error": f"目标是目录: {p}"}
    try:
        backup = _backup(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"error": f"写入失败: {type(e).__name__}: {e}", "path": str(p)}
    return {
        "status": "written",
        "resolved_path": str(p),
        "backup": backup,
        "bytes": len(content.encode("utf-8")),
    }


def edit_file(
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> dict:
    """在文件中把 old_string 替换为 new_string（不读全文即可精确改动）。改动前自动备份。

    默认要求 old_string 在文件中唯一出现；若出现多次需把 replace_all 设为 true，
    否则报错并提示加更多上下文。

    Args:
        path: 目标文件路径。
        old_string: 要被替换的原文（需与文件中完全一致，含缩进/换行）。
        new_string: 替换后的新文本。
        replace_all: 是否替换全部匹配；默认 False（仅在唯一匹配时替换）。

    Returns:
        dict，含 status、resolved_path、replacements、backup；出错时含 error。
    """
    p = _resolve(path)
    if not p.exists():
        return {"error": f"文件不存在: {p}"}
    if p.is_dir():
        return {"error": f"目标是目录: {p}"}

    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"error": f"读取失败: {type(e).__name__}: {e}", "path": str(p)}

    count = text.count(old_string)
    if count == 0:
        return {
            "error": "未找到 old_string。请先用 read_file 核对当前内容，或加更多上下文。",
            "path": str(p),
        }
    if count > 1 and not replace_all:
        return {
            "error": (
                f"old_string 出现 {count} 次（不唯一）。请加更多上下文使其唯一，"
                "或把 replace_all 设为 true。"
            ),
            "path": str(p),
            "occurrences": count,
        }

    new_text = text.replace(old_string, new_string)
    try:
        backup = _backup(p)
        p.write_text(new_text, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"error": f"写入失败: {type(e).__name__}: {e}", "path": str(p)}

    return {
        "status": "edited",
        "resolved_path": str(p),
        "replacements": count if replace_all else 1,
        "backup": backup,
    }


def list_dir(path: str = ".") -> dict:
    """列出目录内容（不递归），区分文件与子目录。

    Args:
        path: 目录路径，默认当前目录。

    Returns:
        dict，含 dirs、files（含大小）；出错时含 error。
    """
    p = _resolve(path)
    if not p.exists():
        return {"error": f"路径不存在: {p}"}
    if not p.is_dir():
        return {"error": f"不是目录: {p}"}

    dirs, files = [], []
    for child in sorted(p.iterdir()):
        if child.is_dir():
            dirs.append(child.name)
        else:
            files.append({"name": child.name, "size": child.stat().st_size})
    return {"path": str(p), "dirs": dirs, "files": files}


def search_files(
    pattern: str,
    path: str = ".",
    target: str = "content",
    file_glob: str = "",
    limit: int = 50,
) -> dict:
    """在目录下递归搜索。

    Args:
        pattern: 正则表达式（target=content 时匹配文件内容；target=filename 时匹配文件名）。
        path: 搜索根目录，默认当前目录。
        target: "content" 搜内容（默认），"filename" 搜文件名。
        file_glob: 可选的文件名过滤（如 "*.py"），只在匹配的文件里搜。
        limit: 最多返回多少条匹配。

    Returns:
        dict，含 matches（content 模式为 {file,line,text}；filename 模式为路径列表）、
        total、truncated；出错时含 error。
    """
    root = _resolve(path)
    if not root.exists():
        return {"error": f"路径不存在: {root}"}

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"error": f"正则无效: {e}"}

    matches: list = []
    truncated = False

    def _iter_files():
        if root.is_file():
            yield root
            return
        for dirpath, dirnames, filenames in os.walk(root):
            # 跳过常见噪声目录
            dirnames[:] = [
                d for d in dirnames
                if d not in {".git", "__pycache__", ".venv", "node_modules"}
            ]
            for fn in filenames:
                yield Path(dirpath) / fn

    for f in _iter_files():
        if file_glob and not fnmatch.fnmatch(f.name, file_glob):
            continue

        if target == "filename":
            if regex.search(f.name):
                matches.append(str(f))
        else:  # content
            if f.suffix.lower() in _BINARY_EXTS:
                continue
            try:
                for i, line in enumerate(
                    f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    if regex.search(line):
                        matches.append({"file": str(f), "line": i, "text": line[:300]})
                        if len(matches) >= limit:
                            break
            except Exception:  # noqa: BLE001
                continue

        if len(matches) >= limit:
            truncated = True
            break

    return {
        "pattern": pattern,
        "target": target,
        "matches": matches[:limit],
        "total": len(matches),
        "truncated": truncated,
    }
