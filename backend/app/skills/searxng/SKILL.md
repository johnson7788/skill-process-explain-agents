---
name: searxng
description: 使用自部署 SearXNG 实例进行隐私友好的网页搜索，支持通用搜索、新闻搜索、图片搜索，可指定语言、搜索引擎和时间范围。当用户需要搜索互联网信息、查找最新资讯、获取网页搜索结果时触发此技能。
---

# SearXNG Search — 网页搜索技能

## 概述

通过自部署的 SearXNG 实例执行隐私友好的互联网搜索，支持以下搜索类型：

| 类型 | `--type` 值 | 说明 |
|------|-------------|------|
| 通用搜索 | `general` | 默认，综合网页搜索 |
| 新闻搜索 | `news` | 最新新闻资讯 |
| 图片搜索 | `images` | 图片结果 |
| 视频搜索 | `videos` | 视频结果 |

## 调用方式

### 步骤 1：确定搜索关键词和类型

根据用户需求，提取搜索关键词，判断搜索类型（通用 / 新闻 / 图片 / 视频）。

### 步骤 2：调用搜索脚本

通过 `run_skill_script` 工具调用脚本，`args` 参数为字符串列表（位置参数 + 选项参数按顺序排列）。

> **重要参数规则**：
> - `args` 为列表时，**禁止**同时传 `short_options` 或 `positional_args`
> - **不要使用 `--output`**，脚本结果直接通过 stdout 返回，无需保存到文件再读取
> - 列表第一个元素是搜索关键词，后面跟选项参数如 `["搜索词", "--type", "news", "--language", "en"]`

#### 通用搜索

```json
{
  "skill_name": "searxng",
  "file_path": "scripts/search.py",
  "args": ["Python 编程教程"]
}
```

#### 新闻搜索（英文）

```json
{
  "skill_name": "searxng",
  "file_path": "scripts/search.py",
  "args": ["Nefecon phase 3 trial results", "--type", "news", "--language", "en"]
}
```

#### 指定引擎 + 时间范围

```json
{
  "skill_name": "searxng",
  "file_path": "scripts/search.py",
  "args": ["SGLT2 inhibitor", "--engines", "google,bing", "--time-range", "month", "--language", "en"]
}
```

#### 图片搜索

```json
{
  "skill_name": "searxng",
  "file_path": "scripts/search.py",
  "args": ["机器学习架构图", "--type", "images", "--num", "5"]
}
```

### 步骤 3：分析 stdout 返回的 JSON 结果

脚本执行后，搜索结果以 JSON 格式直接返回在 `stdout` 字段中，可直接解析使用。

## 参数说明

| 参数 | 缩写 | 必选 | 说明 |
|------|------|------|------|
| `query` | — | 是 | 搜索关键词（位置参数） |
| `--type` | `-t` | 否 | 搜索类型：`general`（默认）/ `news` / `images` / `videos` |
| `--num` | `-n` | 否 | 返回结果数量，默认 10 |
| `--language` | `-l` | 否 | 搜索语言，默认 `zh`，可选 `en`、`auto` 等 |
| `--engines` | `-e` | 否 | 指定搜索引擎，逗号分隔（如 `google,bing`） |
| `--time-range` | — | 否 | 时间范围：`day` / `week` / `month` / `year` |
| `--output` | `-o` | 否 | 结果输出到 JSON 文件，不指定则输出到 stdout |
| `--diagnostics-output` | — | 否 | 将请求诊断信息输出到 JSON 文件，便于排查空结果或限流 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SEARXNG_BASE_URL` | SearXNG 实例搜索接口地址 | `https://ai-searxng.infox-med.com/search` |
| `SEARXNG_MAX_ATTEMPTS` | 请求最大尝试次数（含首次请求） | `3` |
| `SEARXNG_RETRY_BASE_DELAY` | 重试基础退避秒数 | `1.0` |
| `SEARXNG_REQUEST_TIMEOUT` | 单次请求超时时间（秒） | `30` |

## 返回结果格式

```json
[
  {
    "title": "结果标题",
    "url": "https://example.com/page",
    "content": "结果摘要内容...",
    "engine": "google",
    "score": 1.5,
    "category": "general",
    "publishedDate": "2025-03-15T10:00:00"
  }
]
```

| 字段 | 说明 |
|------|------|
| `title` | 结果标题 |
| `url` | 结果链接 |
| `content` | 摘要/内容片段 |
| `engine` | 来源搜索引擎 |
| `score` | SearXNG 相关性评分 |
| `category` | 结果类别 |
| `publishedDate` | 发布时间（如有） |

## 依赖

- `requests` — HTTP 请求

## 注意事项

1. **不要使用 `--output`**，结果直接通过 stdout 返回
2. 默认语言为中文（`zh`），搜索英文内容请加 `--language en`
3. 不指定 `--engines` 时使用 SearXNG 实例配置的全部引擎
4. 当搜索引擎出现限流、验证码或 access denied 导致空结果时，脚本会自动进行有限重试
5. 若需要排查 `0 items`，请同时使用 `--diagnostics-output` 查看 `unresponsiveEngines` 和每次尝试的诊断信息
