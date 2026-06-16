"""Web 搜索集成 — Tavily + Semantic Scholar"""

import httpx
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str = ""


@dataclass
class ScholarPaper:
    """学术论文"""
    paper_id: str
    title: str
    authors: List[str]
    year: int
    abstract: str
    citation_count: int
    url: str
    venue: str = ""


class TavilySearch:
    """Tavily Web 搜索"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self.base_url = "https://api.tavily.com"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> List[SearchResult]:
        """搜索网页"""
        if not self.available:
            logger.warning("Tavily API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": search_depth,
                        "include_answer": True,
                    },
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:300],
                        source="tavily",
                    ))
                return results

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []


class SemanticScholarSearch:
    """Semantic Scholar 学术搜索"""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    async def search(
        self,
        query: str,
        limit: int = 10,
        year_range: Optional[str] = None,
    ) -> List[ScholarPaper]:
        """搜索学术论文"""
        try:
            params = {
                "query": query,
                "limit": limit,
                "fields": "paperId,title,authors,year,abstract,citationCount,url,venue",
            }
            if year_range:
                params["year"] = year_range

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/paper/search",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                papers = []
                for item in data.get("data", []):
                    authors = [a.get("name", "") for a in item.get("authors", [])]
                    papers.append(ScholarPaper(
                        paper_id=item.get("paperId", ""),
                        title=item.get("title", ""),
                        authors=authors,
                        year=item.get("year", 0),
                        abstract=item.get("abstract", "") or "",
                        citation_count=item.get("citationCount", 0),
                        url=item.get("url", ""),
                        venue=item.get("venue", ""),
                    ))
                return papers

        except Exception as e:
            logger.error(f"Semantic Scholar search failed: {e}")
            return []

    async def search_math_modeling(
        self,
        topic: str,
        limit: int = 5,
    ) -> List[ScholarPaper]:
        """搜索数学建模相关论文"""
        return await self.search(
            query=f"mathematical modeling {topic}",
            limit=limit,
        )


class UnifiedSearch:
    """统一搜索接口"""

    def __init__(self, tavily_key: Optional[str] = None):
        self.tavily = TavilySearch(tavily_key)
        self.scholar = SemanticScholarSearch()

    async def search_all(
        self,
        query: str,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """同时搜索网页和学术论文"""
        import asyncio

        web_results, papers = await asyncio.gather(
            self.tavily.search(query, max_results),
            self.scholar.search_math_modeling(query, max_results),
            return_exceptions=True,
        )

        return {
            "web": [
                {"title": r.title, "url": r.url, "snippet": r.snippet}
                for r in (web_results if isinstance(web_results, list) else [])
            ],
            "papers": [
                {
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "abstract": p.abstract[:200],
                    "citations": p.citation_count,
                    "url": p.url,
                    "venue": p.venue,
                }
                for p in (papers if isinstance(papers, list) else [])
            ],
        }


# 全局实例
unified_search = UnifiedSearch(tavily_key=os.getenv("TAVILY_API_KEY"))
