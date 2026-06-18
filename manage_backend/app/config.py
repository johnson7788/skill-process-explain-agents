"""路径配置 — 指向主 backend 的目录"""

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# 主 backend 目录
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_APP_DIR = BACKEND_DIR / "app"

# Agent 配置
AGENT_PY = BACKEND_APP_DIR / "agent.py"

# Skills 目录
SKILLS_DIR = BACKEND_APP_DIR / "skills"

# Logs 目录
LOGS_DIR = BACKEND_DIR / "logs"

# 版本历史存储（管理端自己的数据）
MANAGE_DATA_DIR = Path(__file__).parent.parent / "data"
AGENT_VERSIONS_DIR = MANAGE_DATA_DIR / "agent_versions"
SKILL_VERSIONS_DIR = MANAGE_DATA_DIR / "skill_versions"

# 确保数据目录存在
for d in [MANAGE_DATA_DIR, AGENT_VERSIONS_DIR, SKILL_VERSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
