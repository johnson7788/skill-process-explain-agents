#!/usr/bin/env python3
"""
SearXNG 搜索工具 — 通过自部署 SearXNG 实例进行网页、新闻、图片搜索。
支持命令行调用和 Python 模块导入两种方式。
"""

import argparse
import json
import os
import random
import sys
import time
from typing import Any, Optional

import requests

DEFAULT_BASE_URL = "http://localhost:8080/search"
DEFAULT_REQUEST_TIMEOUT = 30.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY = 1.0


def _read_float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _read_int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _format_unresponsive_engines(raw: Any) -> list[list[str]]:
    formatted: list[list[str]] = []
    if not isinstance(raw, list):
        return formatted

    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            formatted.append([str(item[0]), str(item[1])])
    return formatted


def _format_results(results: list[dict], num_results: int) -> list[dict]:
    formatted_results = []
    for item in results[:num_results]:
        formatted_results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "engine": item.get("engine", ""),
            "score": item.get("score", 0),
            "category": item.get("category", ""),
            "publishedDate": item.get("publishedDate", ""),
        })
    return formatted_results


def _build_final_diagnostics(data: dict[str, Any], formatted_results: list[dict], unresponsive_engines: list[list[str]]) -> dict[str, Any]:
    return {
        "status": "ok",
        "resultsCount": len(formatted_results),
        "numberOfResults": data.get("number_of_results", 0),
        "answersCount": len(data.get("answers", [])),
        "infoboxesCount": len(data.get("infoboxes", [])),
        "unresponsiveEngines": unresponsive_engines,
    }


def _sleep_before_retry(attempt_number: int, base_delay_seconds: float) -> None:
    if base_delay_seconds <= 0:
        return
    delay = base_delay_seconds * (2 ** max(0, attempt_number - 1))
    delay += random.uniform(0, base_delay_seconds)
    time.sleep(delay)


def search_with_diagnostics(
    query: str,
    num_results: int = 10,
    language: str = "zh",
    categories: str = "general",
    engines: Optional[str] = None,
    time_range: Optional[str] = None,
    base_url: Optional[str] = None,
    request_timeout: Optional[float] = None,
    max_attempts: Optional[int] = None,
    retry_base_delay: Optional[float] = None,
) -> tuple[list[dict], dict[str, Any]]:
    """
    使用 SearXNG 进行搜索，并返回诊断信息。

    在请求异常，或结果为空且引擎被限流/验证码拦截时，执行有限重试。
    """
    url = base_url or os.environ.get("SEARXNG_BASE_URL", DEFAULT_BASE_URL)
    timeout = request_timeout if request_timeout is not None else _read_float_env(
        "SEARXNG_REQUEST_TIMEOUT",
        DEFAULT_REQUEST_TIMEOUT,
    )
    attempts = max(
        1,
        max_attempts if max_attempts is not None else _read_int_env("SEARXNG_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
    )
    base_delay_seconds = max(
        0.0,
        retry_base_delay if retry_base_delay is not None else _read_float_env(
            "SEARXNG_RETRY_BASE_DELAY",
            DEFAULT_RETRY_BASE_DELAY,
        ),
    )

    params = {
        "q": query,
        "format": "json",
        "language": language,
        "categories": categories,
        "safesearch": 0,
    }

    if engines:
        params["engines"] = engines
    if time_range:
        params["time_range"] = time_range

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PythonSearchBot/1.0)",
        "Accept": "application/json",
    }

    diagnostics: dict[str, Any] = {
        "query": query,
        "language": language,
        "categories": categories,
        "engines": engines,
        "timeRange": time_range,
        "baseUrl": url,
        "attempts": [],
    }

    for attempt_number in range(1, attempts + 1):
        attempt_diagnostics: dict[str, Any] = {
            "attempt": attempt_number,
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()

            data = response.json()
            raw_results = data.get("results", [])
            formatted_results = _format_results(raw_results, num_results)
            unresponsive_engines = _format_unresponsive_engines(data.get("unresponsive_engines", []))

            attempt_diagnostics.update({
                "status": "ok",
                "httpStatus": response.status_code,
                "resultsCount": len(formatted_results),
                "numberOfResults": data.get("number_of_results", 0),
                "answersCount": len(data.get("answers", [])),
                "infoboxesCount": len(data.get("infoboxes", [])),
                "unresponsiveEngines": unresponsive_engines,
            })

            should_retry = len(formatted_results) == 0 and len(unresponsive_engines) > 0 and attempt_number < attempts
            if should_retry:
                attempt_diagnostics["retryReason"] = "empty_results_with_unresponsive_engines"

            diagnostics["attempts"].append(attempt_diagnostics)

            if not should_retry:
                diagnostics["final"] = _build_final_diagnostics(data, formatted_results, unresponsive_engines)
                return formatted_results, diagnostics
        except requests.RequestException as exc:
            attempt_diagnostics.update({
                "status": "error",
                "error": str(exc),
            })
            if attempt_number < attempts:
                attempt_diagnostics["retryReason"] = "request_exception"
            diagnostics["attempts"].append(attempt_diagnostics)

            if attempt_number >= attempts:
                diagnostics["final"] = {
                    "status": "error",
                    "error": str(exc),
                    "resultsCount": 0,
                    "numberOfResults": 0,
                    "answersCount": 0,
                    "infoboxesCount": 0,
                    "unresponsiveEngines": [],
                }
                raise

        if attempt_number < attempts:
            _sleep_before_retry(attempt_number, base_delay_seconds)

    diagnostics["final"] = {
        "status": "ok",
        "resultsCount": 0,
        "numberOfResults": 0,
        "answersCount": 0,
        "infoboxesCount": 0,
        "unresponsiveEngines": [],
    }
    return [], diagnostics


def search(
    query: str,
    num_results: int = 10,
    language: str = "zh",
    categories: str = "general",
    engines: Optional[str] = None,
    time_range: Optional[str] = None,
    base_url: Optional[str] = None,
) -> list[dict]:
    """
    使用 SearXNG 进行搜索

    Args:
        query: 搜索关键词
        num_results: 返回结果数量（默认10）
        language: 搜索语言（默认 'zh'，可选 'en', 'auto' 等）
        categories: 搜索类别（默认 'general'，可选 'images', 'news', 'videos' 等）
        engines: 指定搜索引擎（逗号分隔，如 'google,bing'，默认 None 使用所有引擎）
        time_range: 时间范围（可选 'day', 'week', 'month', 'year'）
        base_url: SearXNG 实例地址（默认从环境变量或内置默认值）

    Returns:
        搜索结果列表，每个结果包含 title, url, content 等字段
    """
    results, _diagnostics = search_with_diagnostics(
        query=query,
        num_results=num_results,
        language=language,
        categories=categories,
        engines=engines,
        time_range=time_range,
        base_url=base_url,
    )
    return results


def _format_diagnostics_summary(diagnostics: dict[str, Any]) -> str:
    attempts = diagnostics.get("attempts", [])
    final = diagnostics.get("final", {})
    unresponsive = final.get("unresponsiveEngines", []) if isinstance(final, dict) else []
    summary = [
        f"attempts={len(attempts) if isinstance(attempts, list) else 0}",
        f"results={final.get('resultsCount', 0) if isinstance(final, dict) else 0}",
    ]
    if unresponsive:
        engines = ", ".join(f"{engine}: {reason}" for engine, reason in unresponsive)
        summary.append(f"unresponsive={engines}")
    return "; ".join(summary)


def main():
    parser = argparse.ArgumentParser(description="SearXNG 搜索工具")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument(
        "--type", "-t",
        choices=["general", "news", "images", "videos"],
        default="general",
        help="搜索类型（默认 general）",
    )
    parser.add_argument("--num", "-n", type=int, default=10, help="返回结果数量（默认 10）")
    parser.add_argument("--language", "-l", default="zh", help="搜索语言（默认 zh）")
    parser.add_argument("--engines", "-e", default=None, help="指定搜索引擎，逗号分隔（如 google,bing）")
    parser.add_argument("--time-range", choices=["day", "week", "month", "year"], default=None, help="时间范围")
    parser.add_argument("--output", "-o", default=None, help="结果输出到 JSON 文件路径")
    parser.add_argument("--diagnostics-output", default=None, help="诊断信息输出到 JSON 文件路径")

    args = parser.parse_args()

    try:
        results, diagnostics = search_with_diagnostics(
            query=args.query,
            num_results=args.num,
            language=args.language,
            categories=args.type,
            engines=args.engines,
            time_range=args.time_range,
        )
    except requests.RequestException as e:
        # 请求失败时输出空结果而非以错误码退出
        results = []
        diagnostics = {"final": {"status": "error", "error": str(e)}}

    output = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"结果已保存到 {args.output}（共 {len(results)} 条）")
    else:
        print(output)

    if args.diagnostics_output:
        with open(args.diagnostics_output, "w", encoding="utf-8") as f:
            json.dump(diagnostics, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
