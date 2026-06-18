---
name: optimize-agent
description: 基于运行日志，优化「指定路径下」某个 ADK Agent 的 instruction、skills 与代码。当用户给出一个目标 Agent 的目录路径（或 agent.py 路径），并希望分析它的运行日志、诊断问题、提出并应用改进时使用。改动前必须备份，改动后给出 diff 摘要。
---

# 优化指定路径下的 Agent

本技能让你对**用户指定路径**下的某个 ADK Agent 进行「日志驱动」的优化：读取它的
`agent.py` / `instruction` / `skills`，结合它的运行日志找出问题，给出并**安全地应用**
改进，且每次改动前先备份、改动后给出差异摘要。

## 重要：你怎么操作文件

你有以下文件工具，所有「定位 / 读取 / 改写 / 搜索」都通过它们完成：

- `list_dir(path)` — 列目录，确认结构。
- `read_file(path, offset, limit)` — 分页读取，带行号；先读后改。
- `search_files(pattern, path, target, file_glob, limit)` — 正则搜内容或文件名。
- `edit_file(path, old_string, new_string, replace_all)` — 精确替换某段文本（首选，改动最小）。
- `write_file(path, content)` — 整体覆盖写入（仅在需要重写整文件时用）。

`edit_file` 和 `write_file` 在改写已有文件前会**自动备份**为 `<文件名>.bak.<时间戳>`，
并在返回里给出 `backup` 路径与 `resolved_path`。你不需要、也不应自己再写代码去操作文件。

## 安全红线（必须遵守）

1. **只在用户给定的目标路径内读写**。绝不修改该路径之外的任何文件。
2. **先读后改**：改任何文件前先 `read_file` 看清当前内容，避免基于过期内容改动。
3. **优先 `edit_file`**：能精确替换就不要整文件 `write_file`，改动最小化。
4. **绝不删除**用户的文件（工具也不提供删除）。
5. **先展示、后落地**：把准备应用的改动以 diff 形式展示并说明理由，确认后再调用写工具。

## 步骤

### 步骤 1：确认目标

向用户确认（或从消息中提取）以下信息，缺失就主动询问：
- **目标 Agent 根目录**（含 `agent.py` 的目录），例如 `/path/to/some/backend/app`。
- **日志位置**（若有）。常见约定：根目录或上层的 `logs/` 下的 `*.jsonl`。
- **优化范围**：只优化 `instruction`，还是也包括 `skills` / 工具代码。

用 `list_dir("<用户给的目标路径>")` 确认结构，看是否有 `agent.py` / `skills/` / `logs/`。

### 步骤 2：读取当前实现

读取并打印关键内容，建立基线认知：
- `agent.py`：提取 `name` / `model` / `description` / `instruction` / `tools`。
- `skills/*/SKILL.md`：每个 skill 的 frontmatter（name、description）与正文要点。
- 若有 `instruction.md` 等外部指令文件，一并读取。

### 步骤 3：分析运行日志

定位日志目录下的 `*.jsonl`（每行一个 JSON 事件）。逐文件、逐行解析，提取优化信号：
- **错误**：`type == "error"` 的事件，统计重复错误模式。
- **工具失败率**：`tool_call` / `tool_step` 中 `status` 为 `error`/`failed` 的占比。
- **耗时热点**：`summary.elapsed_seconds`，以及思考/工具/输出各阶段时间分布。
- **用户意图分布**：`meta.message`，看高频诉求是否被 skill / instruction 覆盖。
- **跑偏**：思考冗长、反复调用同一工具、答非所问等。

把信号汇总成「问题清单」，每条标注：现象 → 证据（来自哪个日志/事件）→ 影响。

### 步骤 4：诊断并提出改进

针对每个问题给出**具体、可落地**的改动，而非泛泛建议：
- instruction：补充缺失的步骤约束、澄清歧义、加入针对高频错误的处置规则。
- skills：修正 `SKILL.md` 描述（影响何时被加载）、补全步骤、修复脚本参数校验。
- 代码：仅在明确定位到 bug 时改 `agent.py` 或工具代码，改动最小化。

输出一份**优化方案**：逐条「问题 → 改动 → 预期效果」，并标明会改哪些文件。

### 步骤 5：应用改动

用户确认方案后，对每个要改的文件：

- 局部改动（最常见，如改 instruction 里某段、改 SKILL.md 某节）：用
  `edit_file(path, old_string, new_string)`。`old_string` 要带足够上下文以唯一定位；
  工具会自动备份并返回 `backup` 路径。
- 需要重写整文件时才用 `write_file(path, content)`（同样自动备份）。

修改 `instruction` 这类嵌在 `agent.py` 里的 Python 字符串时，`old_string`/`new_string`
要保持合法的 Python 语法（引号、缩进、换行一致）。改完后 `read_file` 复读改动区域，
确认替换正确、未破坏语法。

### 步骤 6：汇报

给出本次改动摘要：
- 改了哪些文件、对应的备份路径。
- 每个改动的 before/after 关键差异（diff 片段）。
- 这些改动预期解决日志里的哪些问题。
- 建议的验证方式（重跑哪类用户请求来确认改善）。

## 输出风格

- 全程说明你在做什么、依据是哪条日志证据。
- 方案要具体到「改哪个文件的哪一段、改成什么」。
- 任何写文件操作前，先确认已经备份。
