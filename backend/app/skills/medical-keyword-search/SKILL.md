---
name: medical-keyword-search
description: 医学文献关键词精确搜索技能，通过 InfoX-Med API 进行关键词和布尔表达式检索，支持中文指南、英文指南、系统评价/Meta分析、RCT 四类文献的并行搜索，以及自由检索表达式搜索。支持字段标签、影响因子/时间筛选、多种排序方式。适合精确定位特定文献、按条件筛选、或使用高级检索表达式时触发此技能。
---

# Medical Keyword Search — 医学文献关键词精确搜索

## 概述

通过 InfoX-Med API 执行医学文献关键词搜索，支持精确的布尔检索表达式和多维度筛选。

> **与 medical-pico-search 的区别**：本技能侧重**精确关键词匹配**，支持布尔运算符、字段标签、影响因子/时间/类型筛选和多种排序方式，适合精确定位特定文献；而 medical-pico-search 侧重**语义匹配**，输入为结构化 PICO 要素，适合回答明确的临床问题。

支持以下搜索模式：

| 模式 | 命令 | 说明 |
|------|------|------|
| 并行全搜 | `all` | 同时搜索中文指南、英文指南、系统评价/Meta分析、RCT |
| 中文指南 | `chinese-guideline` | 仅中华系列期刊指南 |
| 英文指南 | `english-guideline` | 排除中华系列的英文指南 |
| 系统评价 | `systematic-meta` | Meta-Analysis & Systematic Review |
| RCT | `rct` | 随机对照试验 |
| 自由搜索 | `free` | 直接传入检索表达式和筛选条件 |

## 调用方式

### 步骤 1：从用户问题中提取搜索关键词

分析用户的医学问题，提取核心英文关键词（通常 2-5 个）。关键词应覆盖疾病、干预、人群等核心概念。

> **重要**：关键词必须为英文，禁止包含年份/日期（日期通过 filter 参数传入）。

### 步骤 2：调用搜索脚本

通过 `run_skill_script` 工具调用脚本，`args` 参数为字符串列表（位置参数 + 选项参数按顺序排列）。

> **重要参数规则**：
> - `args` 为列表时，**禁止**同时传 `short_options` 或 `positional_args`
> - **不要使用 `--output`**，脚本结果直接通过 stdout 返回，无需保存到文件再读取
> - 列表元素顺序：`[搜索模式, 关键词1, 关键词2, ...]`，选项参数跟在后面如 `["rct", "keyword1", "--sort", "docPublishTime"]`

#### RCT 搜索（最常用，适合临床试验数据查询）

```json
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["rct", "Nefecon", "IgA nephropathy", "proteinuria"]
}
```

#### 并行搜索 4 类文献

```json
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["all", "lung cancer", "immunotherapy", "PD-1"]
}
```

#### 搜索指定类别

```json
// 英文指南
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["english-guideline", "hypertension", "ACE inhibitor"]
}

// 系统评价/Meta分析
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["systematic-meta", "stroke", "thrombolysis"]
}
```

#### 自由搜索（高级用户，带排序和筛选）

```json
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["free", "--query", "(Lung Cancer[Title]) AND (Immunotherapy[Title/Abstract])", "--filter", "$$doc_publish_time$$2020-01-01$$2025-12-31", "--sort", "docPublishTime"]
}
```

### 步骤 3：分析 stdout 返回的 JSON 结果

脚本执行后，搜索结果以 JSON 格式直接返回在 `stdout` 字段中，可直接解析使用。

## 参数说明

### 关键词模式 (all / chinese-guideline / english-guideline / systematic-meta / rct)

| 参数 | 必选 | 说明 |
|------|------|------|
| `keywords` | 是 | 一个或多个英文搜索关键词，空格分隔 |
| `--output / -o` | 否 | 结果输出到 JSON 文件，不指定则输出到 stdout |

### 自由搜索模式 (free)

| 参数 | 必选 | 说明 |
|------|------|------|
| `--query` | 是 | 检索表达式 |
| `--filter` | 否 | 筛选条件字符串 |
| `--sort` | 否 | 排序：`relevant`（默认）/ `docPublishTime` / `docIf` / `citedBy` |
| `--output / -o` | 否 | 输出文件路径 |

## 检索表达式语法（free 模式）

```
("关键词"[字段]) AND/OR/NOT ("关键词"[字段])
```

**可用字段标签：**
- `[Title]` 标题、`[Abstract]` 摘要、`[Title/Abstract]` 标题+摘要
- `[MeSH Terms]` 医学主题词、`[Journal]` 期刊
- `[Author]` / `[First Author]` / `[Last Author]` 作者
- `[Affiliation]` 机构

**示例：**
```
(Lung Cancer[Title]) AND (Immunotherapy[Title/Abstract]) NOT (Review[Title])
```

## 筛选条件语法（filter_string）

| 筛选项 | 格式 | 示例 |
|--------|------|------|
| 发表时间 | `$$doc_publish_time$$开始$$结束` | `$$doc_publish_time$$2020-01-01$$2025-12-31` |
| 影响因子 | `$$doc_if$$下限$$上限` | `$$doc_if$$5$$30` |
| 文章类型 | `$$doc_publish_type$$类型` | `$$doc_publish_type$$Review` |
| 多类型 | 用 `$OR$` 连接 | `$$doc_publish_type$$Clinical Study$OR$Clinical Trial` |

多个筛选条件用 `@@AND$$` 连接。

## 返回结果格式

### 单条文献

```json
{
  "id": "文献ID",
  "title": "文献标题",
  "abstract": "摘要",
  "authors": "作者",
  "journal": "期刊名",
  "publish_date": "2024-01-15 00:00:00",
  "impact_factor": "影响因子",
  "publication_type": "文献类型",
  "link": "https://www.infox-med.com/#/articleDetails?id=xxx"
}
```

### all 模式返回结构

```json
{
  "chinese_guideline": [...],
  "english_guideline": [...],
  "systematic_meta": [...],
  "rct": [...]
}
```

## 特殊过滤规则

- **中文指南**：自动限定 Journal 包含 "Zhonghua"
- **英文指南**：自动排除 Journal 包含 "Zhonghua" 的文献
- **系统评价/Meta分析**：标题必须包含 "meta-analysis" 或 "systematic review"（不区分大小写）
- 关键词搜索采用**两两组合策略**：多个关键词自动生成 (K1 AND K2) OR (K1 AND K3) OR ... 的查询

## 排序规则

| 值 | 触发场景 |
|----|----------|
| `relevant` | 默认，按相关性 |
| `docPublishTime` | 用户强调"最新"、"recent" |
| `docIf` | 用户强调"高分"、"高影响因子" |
| `citedBy` | 用户强调"高引用"、"经典" |

## 依赖

- `aiohttp` — 异步 HTTP 请求

## 示例场景

### 场景 1：糖尿病与胰岛素治疗

```json
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["all", "diabetes mellitus", "insulin therapy", "glycemic control"]
}
```

### 场景 2：查找最新肺癌免疫治疗 RCT

```json
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["rct", "lung cancer", "immunotherapy", "PD-1"]
}
```

### 场景 3：高级自由检索 + 时间过滤

```json
{
  "skill_name": "medical-keyword-search",
  "file_path": "scripts/medical_search.py",
  "args": ["free", "--query", "(septic shock[Title/Abstract]) AND (fluid resuscitation[Title/Abstract])", "--filter", "$$doc_publish_time$$2022-01-01$$2025-12-31", "--sort", "docPublishTime"]
}
```

## 注意事项

1. 搜索关键词**必须为英文**，中文需转译
2. **禁止在 query_string 中包含日期**，日期放入 filter_string
3. **不要使用 `--output`**，结果直接通过 stdout 返回
4. 每次搜索最多返回 20 条结果
