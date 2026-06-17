"""Web tools: web_fetch and web_search (Brave primary, DuckDuckGo fallback)."""

from __future__ import annotations

import html
import json
import logging
import re
from typing import Annotated

import httpx

from oracle.tools.base import tool
import oracle.config as _cfg

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; Oracle/0.1)"


def _strip_html(raw: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@tool(description="Fetch a URL and return stripped text content. Requires approval.", requires_permission=True)
async def web_fetch(
    url: Annotated[str, "URL to fetch"],
    max_chars: Annotated[int, "Maximum characters to return"] = 8_000,
) -> str:
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA},
            follow_redirects=True,
            timeout=20,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type:
                text = _strip_html(resp.text)
            else:
                text = resp.text
            return text[:max_chars] + ("\n[...truncated]" if len(text) > max_chars else "")
    except Exception as e:
        return f"[Tool error] {type(e).__name__}: {e}"


async def _brave_search(query: str, api_key: str, num: int = 5) -> list[dict]:
    url = "https://api.search.brave.com/res/v1/web/search"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                params={"q": query, "count": num},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                })
            return results
    except Exception as e:
        log.warning(f"Brave search failed: {e}")
        return []


async def _ddg_search(query: str, num: int = 5) -> list[dict]:
    """DuckDuckGo instant answer API — no key required, lower quality."""
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA},
            follow_redirects=True,
            timeout=15,
        ) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "no_redirect": "1"},
            )
            data = resp.json()
            results = []
            # Instant answer
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("AbstractSource", "DuckDuckGo"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["AbstractText"],
                })
            # Related topics
            for topic in data.get("RelatedTopics", [])[:num]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                    })
            return results[:num]
    except Exception as e:
        log.warning(f"DuckDuckGo search failed: {e}")
        return []


@tool(description="Search the web. Uses Brave Search API if BRAVE_API_KEY is set, otherwise DuckDuckGo.", requires_permission=False, read_only=True)
async def web_search(
    query: Annotated[str, "Search query"],
    num_results: Annotated[int, "Number of results to return (max 10)"] = 5,
) -> str:
    cfg = _cfg.get()
    num = min(num_results, 10)

    if cfg.brave_api_key:
        results = await _brave_search(query, cfg.brave_api_key, num)
    else:
        results = await _ddg_search(query, num)

    if not results:
        return "(no results)"

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
        lines.append(f"   {r['snippet']}")
        lines.append("")
    return "\n".join(lines).strip()
