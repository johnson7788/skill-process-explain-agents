"""Skill 管理 — 列出、创建、编辑、删除 skills"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from app.config import SKILLS_DIR, SKILL_VERSIONS_DIR


# ---------------------------------------------------------------------------
# 列出 Skills
# ---------------------------------------------------------------------------

def list_skills() -> list[dict]:
    """列出所有 skills 及其基本信息"""
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue

        skill_info = _read_skill_info(skill_dir)
        if skill_info:
            skills.append(skill_info)

    return skills


def _read_skill_info(skill_dir: Path) -> dict | None:
    """读取单个 skill 的元信息"""
    skill_md = skill_dir / "SKILL.md"
    meta_json = skill_dir / "_meta.json"

    if not skill_md.exists():
        return None

    # 解析 SKILL.md frontmatter
    content = skill_md.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(content)

    # 解析 _meta.json（如果存在）
    meta = {}
    if meta_json.exists():
        try:
            meta = json.loads(meta_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    # 列出 scripts
    scripts = []
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for script in sorted(scripts_dir.iterdir()):
            if script.suffix in (".py", ".sh"):
                scripts.append(
                    {
                        "name": script.name,
                        "path": str(script.relative_to(skill_dir)),
                        "size": script.stat().st_size,
                    }
                )

    # 列出 tests
    tests = []
    tests_dir = skill_dir / "tests"
    if tests_dir.exists():
        for test in sorted(tests_dir.iterdir()):
            if test.suffix == ".py":
                tests.append(test.name)

    return {
        "slug": skill_dir.name,
        "name": frontmatter.get("name", skill_dir.name),
        "description": frontmatter.get("description", ""),
        "dir": str(skill_dir),
        "has_scripts": len(scripts) > 0,
        "scripts": scripts,
        "tests": tests,
        "meta": meta,
        "skill_md_size": skill_md.stat().st_size,
        "created": datetime.fromtimestamp(skill_dir.stat().st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(skill_md.stat().st_mtime).isoformat(),
    }


def _parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter（---...---）"""
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    fm_text = parts[1].strip()
    result = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()

    return result


# ---------------------------------------------------------------------------
# 读取 Skill 详情
# ---------------------------------------------------------------------------

def get_skill(slug: str) -> dict | None:
    """获取 skill 的完整内容（SKILL.md + 所有 scripts）"""
    skill_dir = SKILLS_DIR / slug
    if not skill_dir.exists():
        return None

    info = _read_skill_info(skill_dir)
    if not info:
        return None

    # 读取 SKILL.md 完整内容
    skill_md = skill_dir / "SKILL.md"
    info["skill_md_content"] = skill_md.read_text(encoding="utf-8")

    # 读取所有 scripts 内容
    scripts_content = {}
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for script in scripts_dir.iterdir():
            if script.suffix in (".py", ".sh"):
                scripts_content[script.name] = script.read_text(encoding="utf-8")
    info["scripts_content"] = scripts_content

    # 读取 _meta.json
    meta_json = skill_dir / "_meta.json"
    if meta_json.exists():
        info["meta_content"] = meta_json.read_text(encoding="utf-8")

    return info


def get_skill_script(slug: str, script_name: str) -> str | None:
    """读取 skill 的某个 script 文件内容"""
    script_path = SKILLS_DIR / slug / "scripts" / script_name
    if not script_path.exists():
        return None
    return script_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 创建 Skill
# ---------------------------------------------------------------------------

def create_skill(
    slug: str,
    name: str,
    description: str,
    skill_md_content: str = "",
    scripts: dict[str, str] | None = None,
) -> dict:
    """
    创建新 skill。

    Args:
        slug: 目录名（如 "drug-interaction-check"）
        name: 显示名称
        description: 描述
        skill_md_content: SKILL.md 正文（不含 frontmatter）
        scripts: {filename: content} 脚本字典
    """
    skill_dir = SKILLS_DIR / slug
    if skill_dir.exists():
        return {"status": "error", "message": f"Skill '{slug}' 已存在"}

    # 创建目录结构
    skill_dir.mkdir(parents=True)
    (skill_dir / "scripts").mkdir()
    (skill_dir / "tests").mkdir()

    # 生成 SKILL.md（含 frontmatter）
    if not skill_md_content:
        skill_md_content = _generate_default_skill_md(name, description)

    full_md = f"---\nname: {name}\ndescription: {description}\n---\n\n{skill_md_content}"
    (skill_dir / "SKILL.md").write_text(full_md, encoding="utf-8")

    # 生成 _meta.json
    meta = {
        "slug": slug,
        "version": "1.0.0",
        "created": datetime.now().isoformat(),
    }
    (skill_dir / "_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 写入 scripts
    if scripts:
        for filename, content in scripts.items():
            script_path = skill_dir / "scripts" / filename
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(content, encoding="utf-8")

    return {
        "status": "created",
        "slug": slug,
        "message": f"Skill '{slug}' 已创建",
    }


def _generate_default_skill_md(name: str, description: str) -> str:
    """生成默认的 SKILL.md 模板"""
    return f"""# {name}

## 概述

{description}

## 调用方式

### 步骤 1：准备参数

根据用户需求，确定调用参数。

### 步骤 2：调用脚本

通过 `run_skill_script` 工具调用脚本：

```json
{{
  "skill_name": "{name.lower().replace(' ', '-')}",
  "file_path": "scripts/main.py",
  "args": ["参数1", "参数2"]
}}
```

### 步骤 3：分析结果

脚本执行后，结果以 JSON 格式返回在 stdout 字段中。

## 参数说明

| 参数 | 必选 | 说明 |
|------|------|------|
| `param1` | 是 | 参数描述 |

## 返回结果格式

```json
{{
  "result": "结果数据"
}}
```

## 依赖

- `requests` — HTTP 请求

## 注意事项

1. 注意事项一
2. 注意事项二
"""


# ---------------------------------------------------------------------------
# 更新 Skill
# ---------------------------------------------------------------------------

def update_skill_md(slug: str, content: str) -> dict:
    """更新 skill 的 SKILL.md 内容"""
    skill_dir = SKILLS_DIR / slug
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return {"status": "error", "message": f"Skill '{slug}' 不存在"}

    # 保存版本
    _save_skill_version(slug, skill_md.read_text(encoding="utf-8"))

    skill_md.write_text(content, encoding="utf-8")
    return {"status": "updated", "slug": slug, "message": "SKILL.md 已更新"}


def update_skill_script(slug: str, script_name: str, content: str) -> dict:
    """更新 skill 的某个 script 文件"""
    script_path = SKILLS_DIR / slug / "scripts" / script_name
    if not script_path.exists():
        return {"status": "error", "message": f"脚本 {script_name} 不存在"}

    # 保存版本
    _save_skill_version(slug, script_path.read_text(encoding="utf-8"), script_name)

    script_path.write_text(content, encoding="utf-8")
    return {"status": "updated", "slug": slug, "script": script_name}


def create_skill_script(slug: str, filename: str, content: str) -> dict:
    """在 skill 中创建新脚本"""
    scripts_dir = SKILLS_DIR / slug / "scripts"
    if not scripts_dir.exists():
        return {"status": "error", "message": f"Skill '{slug}' 不存在"}

    script_path = scripts_dir / filename
    if script_path.exists():
        return {"status": "error", "message": f"脚本 {filename} 已存在"}

    script_path.write_text(content, encoding="utf-8")
    return {"status": "created", "slug": slug, "script": filename}


# ---------------------------------------------------------------------------
# 删除 Skill
# ---------------------------------------------------------------------------

def delete_skill(slug: str) -> dict:
    """删除整个 skill 目录（先备份）"""
    skill_dir = SKILLS_DIR / slug
    if not skill_dir.exists():
        return {"status": "error", "message": f"Skill '{slug}' 不存在"}

    # 备份到版本目录
    backup_dir = SKILL_VERSIONS_DIR / f"{slug}_deleted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(skill_dir, backup_dir)

    # 删除
    shutil.rmtree(skill_dir)

    return {
        "status": "deleted",
        "slug": slug,
        "backup": str(backup_dir),
        "message": f"Skill '{slug}' 已删除，备份在 {backup_dir}",
    }


# ---------------------------------------------------------------------------
# 版本管理
# ---------------------------------------------------------------------------

def _save_skill_version(slug: str, content: str, filename: str = "SKILL.md") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_id = f"{slug}_{filename}_{ts}"
    version_file = SKILL_VERSIONS_DIR / f"{version_id}.json"
    version_file.write_text(
        json.dumps(
            {
                "version_id": version_id,
                "slug": slug,
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
                "content": content,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return version_id


def list_skill_versions(slug: str) -> list[dict]:
    """列出某个 skill 的所有版本"""
    versions = []
    for f in sorted(SKILL_VERSIONS_DIR.glob(f"{slug}_*.json"), reverse=True):
        data = json.loads(f.read_text(encoding="utf-8"))
        versions.append(
            {
                "version_id": data["version_id"],
                "timestamp": data["timestamp"],
                "filename": data["filename"],
                "preview": data["content"][:100] + "...",
            }
        )
    return versions
