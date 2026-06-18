"""Agent 配置管理 — 读取、编辑、版本控制 agent.py 中的 instruction"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from app.config import AGENT_PY, AGENT_VERSIONS_DIR


def _read_agent_source() -> str:
    """读取 agent.py 原始内容"""
    return AGENT_PY.read_text(encoding="utf-8")


def get_agent_config() -> dict:
    """从 agent.py 中提取当前配置"""
    source = _read_agent_source()

    # 提取 instruction 字符串（三引号之间的内容）
    instruction_match = re.search(
        r'instruction\s*=\s*\(\s*"(.*?)"\s*\)',
        source,
        re.DOTALL,
    )
    instruction = instruction_match.group(1) if instruction_match else ""

    # 提取 description
    desc_match = re.search(
        r'description\s*=\s*\(\s*"(.*?)"\s*\)',
        source,
        re.DOTALL,
    )
    description = desc_match.group(1) if desc_match else ""

    # 提取 name
    name_match = re.search(r'name\s*=\s*"([^"]+)"', source)
    name = name_match.group(1) if name_match else ""

    # 提取 model — MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-chat")
    model_match = re.search(
        r'MODEL_NAME\s*=\s*os\.environ\.get\(\s*"MODEL_NAME"\s*,\s*"([^"]+)"\s*\)',
        source,
    )
    model = model_match.group(1) if model_match else ""

    return {
        "name": name,
        "description": description,
        "instruction": instruction,
        "model": model,
        "source_file": str(AGENT_PY),
    }


def get_instruction() -> str:
    """获取当前 instruction 文本"""
    config = get_agent_config()
    return config["instruction"]


def _save_version(content: str, tag: str = "auto") -> str:
    """保存当前版本到历史"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_id = f"{ts}_{tag}"
    version_file = AGENT_VERSIONS_DIR / f"{version_id}.json"
    version_file.write_text(
        json.dumps(
            {
                "version_id": version_id,
                "timestamp": datetime.now().isoformat(),
                "tag": tag,
                "content": content,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return version_id


def list_versions() -> list[dict]:
    """列出所有历史版本"""
    versions = []
    for f in sorted(AGENT_VERSIONS_DIR.glob("*.json"), reverse=True):
        data = json.loads(f.read_text(encoding="utf-8"))
        versions.append(
            {
                "version_id": data["version_id"],
                "timestamp": data["timestamp"],
                "tag": data["tag"],
                "preview": data["content"][:100] + "...",
            }
        )
    return versions


def get_version(version_id: str) -> dict | None:
    """获取指定版本的完整内容"""
    for f in AGENT_VERSIONS_DIR.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data["version_id"] == version_id:
            return data
    return None


def update_instruction(new_instruction: str, save_version: bool = True) -> dict:
    """
    更新 agent.py 中的 instruction 字段。

    策略：用正则定位 instruction=(...) 块并替换内容。
    """
    source = _read_agent_source()

    # 先保存当前版本
    current_instruction = get_instruction()
    version_id = None
    if save_version and current_instruction != new_instruction:
        version_id = _save_version(source, "before_update")

    # 构建新的 instruction 字符串（保持 Python 多行字符串格式）
    # 将 instruction 转为 Python 拼接字符串格式
    lines = new_instruction.split("\n")
    python_str_parts = []
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace('"', '\\"')
        python_str_parts.append(f'"{escaped}\\n"')

    new_instruction_block = "\n        ".join(python_str_parts)

    # 替换 instruction 块
    pattern = r'(instruction\s*=\s*\(\s*)(.*?)(\s*\))'
    replacement = rf'\g<1>\n        {new_instruction_block}\n    \g<3>'

    new_source = re.sub(pattern, replacement, source, flags=re.DOTALL)

    if new_source == source:
        return {"status": "unchanged", "message": "instruction 未发生变化"}

    AGENT_PY.write_text(new_source, encoding="utf-8")

    return {
        "status": "updated",
        "version_id": version_id,
        "message": "instruction 已更新",
    }


def update_description(new_description: str, save_version: bool = True) -> dict:
    """更新 agent.py 中的 description 字段"""
    source = _read_agent_source()

    version_id = None
    if save_version:
        version_id = _save_version(source, "before_desc_update")

    escaped = new_description.replace("\\", "\\\\").replace('"', '\\"')

    pattern = r'(description\s*=\s*\(\s*")[^"]*("\s*\))'
    replacement = rf'\g<1>{escaped}\g<2>'

    new_source = re.sub(pattern, replacement, source, flags=re.DOTALL)
    AGENT_PY.write_text(new_source, encoding="utf-8")

    return {
        "status": "updated",
        "version_id": version_id,
        "message": "description 已更新",
    }


def rollback(version_id: str) -> dict:
    """回滚到指定版本"""
    version = get_version(version_id)
    if not version:
        return {"status": "error", "message": f"版本 {version_id} 不存在"}

    # 先保存当前状态
    current_source = _read_agent_source()
    _save_version(current_source, "before_rollback")

    # 恢复
    AGENT_PY.write_text(version["content"], encoding="utf-8")

    return {
        "status": "rolled_back",
        "version_id": version_id,
        "message": f"已回滚到版本 {version_id}",
    }
