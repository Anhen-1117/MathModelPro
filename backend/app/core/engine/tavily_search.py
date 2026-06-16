"""Tavily Web Search — Agent 自主联网搜索获取真实数据

Tavily 是为 AI Agent 优化的搜索 API，支持：
- 实时网页搜索
- 新闻搜索
- 结构化答案提取
- 域名过滤
"""

import os
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class SearchResult:
    """搜索"""
    title: str
    url: str
    content: str
    score: float = 0.0
    raw_content: Optional[str] = None


@dataclass
class SearchResponse:
    """搜索响应"""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    answer: Optional[str] = None
    images: List[str] = field(default_factory=list)
    response_time: float = 0.0


class TavilySearchEngine:
    """Tavily 搜索引擎"""

    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self.enabled = bool(self.api_key)

    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
        include_answer: bool = True,
        include_raw_content: bool = False,
        include_images: bool = False,
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
        days: int = None,
    ) -> SearchResponse:
        """执行搜索

        Args:
            query: 搜索查询
            search_depth: "basic" 或 "advanced"
            max_results: 最大结果数 (1-20)
            include_answer: 是否生成 AI 答案
            include_raw_content: 是否包含原始内容
            include_images: 是否包含图片
            include_domains: 限定域名
            exclude_domains: 排除域名
            days: 只搜索最近 N 天的内容
        """
        if not self.enabled:
            logger.warning("Tavily API Key 未配置，搜索功能不可用")
            return SearchResponse(query=query)

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "include_images": include_images,
        }

        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        if days:
            payload["days"] = days

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/search",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

                return SearchResponse(
                    query=query,
                    results=[
                        SearchResult(
                            title=r.get("title", ""),
                            url=r.get("url", ""),
                            content=r.get("content", ""),
                            score=r.get("score", 0.0),
                            raw_content=r.get("raw_content"),
                        )
                        for r in data.get("results", [])
                    ],
                    answer=data.get("answer"),
                    images=data.get("images", []),
                    response_time=data.get("response_time", 0.0),
                )
        except Exception as e:
            logger.error(f"Tavily 搜索失败: {e}")
            return SearchResponse(query=query)

    async def search_academic(
        self,
        topic: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """学术搜索"""
        response = await self.search(
            query=f"{topic} mathematical modeling research paper",
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
            include_domains=["arxiv.org", "scholar.google.com", "researchgate.net", "springer.com", "ieee.org"],
        )

        return [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.content[:300],
                "score": r.score,
            }
            for r in response.results
        ]

    async def search_data(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """数据搜索（优先 gov/edu/org 域名）"""
        response = await self.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=[
                "data.gov", "stats.gov", "worldbank.org", "un.org",
                "who.int", "ourworldindata.org", "kaggle.com",
            ],
        )

        return [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.content[:300],
            }
            for r in response.results
        ]

    def format_for_llm(self, response: SearchResponse, max_chars: int = 3000) -> str:
        """将搜索结果格式化为 LLM 可用的上下文"""
        parts = []

        if response.answer:
            parts.append(f"## AI 生成的答案\n{response.answer}\n")

        if response.results:
            parts.append(f"## 搜索结果 ({len(response.results)} 条)\n")
            for i, r in enumerate(response.results, 1):
                parts.append(f"[{i}] **{r.title}**")
                parts.append(f"    URL: {r.url}")
                parts.append(f"    {r.content[:500]}")
                parts.append("")

        result = "\n".join(parts)
        return result[:max_chars]


# 全局实例
tavily_engine = TavilySearchEngine()
