#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date  : 2025/08/13
# @File  : tools_merged.py
# @Author: merged by ChatGPT (based on johnson's originals)
# @Desc  : Bing 搜索（缓存没生效)
import os
import json
import asyncio
import time
import re
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import aiohttp
from bs4 import BeautifulSoup


# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# 缓存搜索结果
# --------------------------------------------------------------------------------------
CACHE_DIR = Path("cache_search")
CACHE_DIR.mkdir(exist_ok=True)

USER_AGENT = os.getenv(
    "USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
)

# Bing 搜索的暂存（用 ID 取回抓取内容）
search_results: Dict[str, Dict[str, Any]] = {}

# --------------------------------------------------------------------------------------
# Bing 搜索（解析 SERP） + 抓取网页正文 + 高级筛选（站点/排除/filetype）
# --------------------------------------------------------------------------------------
async def search_bing(query: str, num_results: int = 5, site: Optional[str] = None) -> List[Dict[str, Any]]:
    """执行 Bing 搜索并返回结果，可选指定站点。

    返回元素：{id, title, link, snippet, site}
    """
    try:
        search_query = query
        if site:
            site_clean = site.replace("https://", "").replace("http://", "").rstrip("/")
            search_query = f"site:{site_clean} {query}"
            logger.info(f"使用站点过滤: {site_clean}")
        search_url = f"https://cn.bing.com/search?q={quote(search_query)}&setlang=zh-CN&ensearch=0"
        logger.info(f"Bing 搜索 URL: {search_url}")

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Cookie": "SRCHHPGUSR=SRCHLANG=zh-Hans; _EDGE_S=ui=zh-cn; _EDGE_V=1",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers, timeout=15) as resp:
                logger.info(f"Bing 响应状态码: {resp.status}")
                html_text = await resp.text()

        soup = BeautifulSoup(html_text, "lxml")
        results: List[Dict[str, Any]] = []

        selectors = ["#b_results > li.b_algo", "#b_results > .b_ans", "#b_results > li"]
        for sel in selectors:
            elements = soup.select(sel)
            for idx, el in enumerate(elements):
                if len(results) >= num_results:
                    break
                # 跳过广告
                if "b_ad" in (el.get("class") or []):
                    continue
                title = ""
                link = ""
                a = el.select_one("h2 a")
                if a:
                    title = a.get_text(strip=True)
                    link = a.get("href", "")
                if not title:
                    alt = el.select_one(".b_title a, a.tilk, a strong")
                    if alt:
                        title = alt.get_text(strip=True)
                        link = alt.get("href", "")

                snippet = ""
                snode = el.select_one(".b_caption p, .b_snippet, .b_algoSlug")
                if snode:
                    snippet = snode.get_text(strip=True)
                if not snippet:
                    text = el.get_text(strip=True)
                    if title and text.startswith(title):
                        text = text[len(title):].strip()
                    snippet = (text[:150] + "...") if len(text) > 150 else text

                # 相对链接补全
                if link and not link.startswith("http"):
                    link = (f"https://cn.bing.com{link}" if link.startswith("/") else f"https://cn.bing.com/{link}")

                if not title and not snippet:
                    continue

                if site and site not in link:
                    # 再次确保限定站点
                    continue

                rid = f"result_{datetime.now().timestamp()}_{idx}"
                item = {"id": rid, "title": title, "link": link, "snippet": snippet, "site": site or None}
                search_results[rid] = item
                results.append(item)
            if results:
                break

        if not results:
            rid = f"result_{datetime.now().timestamp()}_fallback"
            fallback = {
                "id": rid,
                "title": f"搜索结果: {query}" + (f" site:{site}" if site else ""),
                "link": search_url,
                "snippet": "未能解析出结构化结果，已给出直接 Bing 搜索链接。",
                "site": site or None,
            }
            search_results[rid] = fallback
            results.append(fallback)

        logger.info(f"Bing 返回 {len(results)} 条结果")
        return results
    except Exception as e:
        logger.error(f"Bing 搜索出错: {e}")
        rid = f"error_{datetime.now().timestamp()}"
        err = {
            "id": rid,
            "title": f"搜索 \"{query}\" 出错" + (f"（站点: {site}）" if site else ""),
            "link": f"https://cn.bing.com/search?q={quote(query)}",
            "snippet": f"搜索时发生错误: {e}",
            "site": site or None,
        }
        search_results[rid] = err
        return [err]


async def fetch_webpage_content(result_id: str) -> str:
    """根据 search_bing 返回的 ID 抓取网页正文（尽量提取主内容）。"""
    try:
        result = search_results.get(result_id)
        if not result:
            raise ValueError(f"未找到 ID={result_id} 的搜索结果")

        url = result["link"]
        logger.info(f"抓取网页内容: {url}")

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://cn.bing.com/",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                logger.info(f"网页响应状态码: {resp.status}")
                content_type = resp.headers.get("content-type", "")
                encoding = "utf-8"
                if "charset=" in content_type:
                    try:
                        encoding = content_type.split("charset=")[1].split(";")[0].strip() or "utf-8"
                    except Exception:
                        encoding = "utf-8"
                try:
                    html_text = await resp.text(encoding=encoding)
                except UnicodeDecodeError:
                    html_text = await resp.text(encoding="utf-8", errors="ignore")

        soup = BeautifulSoup(html_text, "lxml")
        # 清理噪音节点
        for el in soup.select(
            "script, style, iframe, noscript, nav, header, footer, .header, .footer, .nav, .sidebar, .ad, .advertisement, #header, #footer, #nav, #sidebar"
        ):
            el.decompose()

        content = ""
        main_selectors = [
            "main",
            "article",
            ".article",
            ".post",
            ".content",
            "#content",
            ".main",
            "#main",
            ".body",
            "#body",
            ".entry",
            ".entry-content",
            ".post-content",
            ".article-content",
            ".text",
            ".detail",
        ]
        for sel in main_selectors:
            m = soup.select_one(sel)
            if m:
                content = m.get_text(strip=True, separator="\n")
                if len(content) > 100:
                    break

        if not content or len(content) < 100:
            paras = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 20]
            if paras:
                content = "\n\n".join(paras)

        if not content or len(content) < 100:
            body = soup.find("body")
            if body:
                content = body.get_text(strip=True, separator="\n")

        content = " ".join(content.split())  # 压缩空白
        title_tag = soup.find("title")
        if title_tag:
            content = f"标题: {title_tag.get_text(strip=True)}\n\n{content}"
        if result.get("site"):
            content = f"来源站点: {result['site']}\n{content}"
        if len(content) > 8000:
            content = content[:8000] + "... (内容已截断)"
        return content
    except Exception as e:
        logger.error(f"抓取网页内容出错: {e}")
        return f"抓取网页内容失败: {e}"

async def advanced_search(
    query: str,
    sites: Optional[List[str]] = None,
    exclude_sites: Optional[List[str]] = None,
    file_type: Optional[str] = None,
    num_results: int = 5,
) -> Dict[str, Any]:
    """多重过滤的高级搜索（组合 site / -site / filetype）。

    返回：{"query": ..., "filters": {...}, "results": [...]}  （results 为 search_bing 的结果列表）
    """
    try:
        search_query = query
        if sites:
            site_expr = " OR ".join([f"site:{s}" for s in sites])
            search_query = f"({site_expr}) {search_query}"
        if exclude_sites:
            for s in exclude_sites:
                search_query += f" -site:{s}"
        if file_type:
            search_query += f" filetype:{file_type}"
        logger.info(f"高级搜索语句: {search_query}")
        results = await search_bing(search_query, num_results=num_results)
        return {
            "query": query,
            "filters": {"sites": sites, "exclude_sites": exclude_sites, "file_type": file_type},
            "results": results,
        }
    except Exception as e:
        logger.error(f"高级搜索出错: {e}")
        return {"error": f"高级搜索失败: {e}"}

async def main():

    print("\n== Demo: Bing search + fetch ==")
    try:
        results = await search_bing("site:tesla.cn 特斯拉", num_results=3)
        print(json.dumps(results, ensure_ascii=False, indent=2)[:5000], "...\n")
        if results:
            rid = results[0]["id"]
            content = await fetch_webpage_content(rid)
            print(content[:5000], "...\n")
    except Exception as e:
        print("Bing demo error:", e)

    print("\n== Demo: Advanced search ==")
    try:
        adv = await advanced_search(
            "特斯拉", sites=["tesla.cn"], exclude_sites=["cn.bing.com"], file_type=None, num_results=3
        )
        print(json.dumps(adv, ensure_ascii=False, indent=2)[:600], "...\n")
    except Exception as e:
        print("Advanced search demo error:", e)

if __name__ == "__main__":
    asyncio.run(main())