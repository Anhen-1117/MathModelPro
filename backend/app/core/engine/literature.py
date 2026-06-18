"""文献搜索模块 — OpenAlex + 独立文献表 + BibTeX 导出"""

import uuid
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class Paper:
    """论文"""
    title: str
    authors: List[str] = field(default_factory=list)
    year: int = 0
    abstract: str = ""
    doi: str = ""
    url: str = ""
    journal: str = ""
    citation_count: int = 0
    source: str = "openalex"

    def to_bibtex(self, cite_key: str = None) -> str:
        """生成 BibTeX 条目"""
        if not cite_key:
            # 自动生成引用键：第一作者姓氏 + 年份 + 标题首词
            first_author = self.authors[0] if self.authors else "unknown"
            last_name = first_author.split()[-1].lower() if first_author else "unknown"
            first_word = self.title.split()[0].lower().rstrip(",.;:") if self.title else "unknown"
            cite_key = f"{last_name}{self.year}{first_word}"

        authors_bib = " and ".join(self.authors) if self.authors else "{Unknown}"
        lines = [f"@article{{{cite_key},"]
        lines.append(f"  title = {{{self.title}}},")
        lines.append(f"  author = {{{authors_bib}}},")
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.journal:
            lines.append(f"  journal = {{{self.journal}}},")
        if self.doi:
            lines.append(f"  doi = {{{self.doi}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        if self.abstract:
            # 截断过长的摘要
            short_abstract = self.abstract[:500]
            lines.append(f"  abstract = {{{short_abstract}}},")
        lines.append("}")
        return "\n".join(lines)

    def to_reference(self, style: str = "gb7714") -> str:
        """生成格式化参考文献条目（GB/T 7714 格式）

        [1] 作者1, 作者2. 论文标题[J]. 期刊名, 年份.
        """
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += ", 等"
        ref = f"{authors_str}. {self.title}"
        if self.journal:
            ref += f"[J]. {self.journal}"
        if self.year:
            ref += f", {self.year}"
        if self.doi:
            ref += f". DOI: {self.doi}"
        return ref


class LiteratureSearch:
    """文献搜索 — 多数据源（OpenAlex / CNKI）+ 独立文献表"""

    # 支持的文献数据源
    SOURCE_OPENALEX = "openalex"
    SOURCE_CNKI = "cnki"

    def __init__(self, email: Optional[str] = None):
        self.email = email
        self.base_url = "https://api.openalex.org"
        self._db_session = None  # 延迟注入
        self._cnki = None  # 知网搜索引擎（延迟初始化）

    def set_db_session(self, session):
        """注入数据库会话"""
        self._db_session = session

    async def search(
        self,
        query: str,
        limit: int = 10,
        source: str = SOURCE_OPENALEX,
    ) -> List[Paper]:
        """搜索文献（支持多数据源）。

        Args:
            query: 搜索关键词。
            limit: 最大返回条数。
            source: 数据源（"openalex" 或 "cnki"）。

        Returns:
            Paper 列表。
        """
        if source == self.SOURCE_CNKI:
            return await self._search_cnki(query, limit)
        return await self._search_openalex(query, limit)

    async def _search_cnki(self, query: str, limit: int = 10) -> List[Paper]:
        """通过知网搜索文献（含百度学术兜底）。"""
        if self._cnki is None:
            from app.core.engine.cnki_search import CnkiSearch
            import os
            # 调试模式：保存 HTML 到 data/debug/ 目录
            debug_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "debug"
            )
            self._cnki = CnkiSearch(debug_dir=debug_dir)
        try:
            papers = await self._cnki.search(query, limit)
            if papers:
                logger.info(f"知网/百度学术搜索完成: {len(papers)} 篇")
            return papers
        except Exception as e:
            logger.warning(f"知网搜索失败: {e}")
            return []

    async def _search_openalex(self, query: str, limit: int = 10) -> List[Paper]:
        """通过 OpenAlex API 搜索文献。"""
        params = {
            "search": query,
            "per_page": limit,
            "sort": "cited_by_count:desc",
        }
        if self.email:
            params["mailto"] = self.email

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/works",
                    params=params
                )
                response.raise_for_status()
                data = response.json()

                papers = []
                for item in data.get("results", []):
                    # 提取作者
                    authors = [
                        author.get("author", {}).get("display_name", "")
                        for author in item.get("authorships", [])
                    ]
                    # 提取 DOI
                    doi = item.get("doi", "")
                    if doi and doi.startswith("https://doi.org/"):
                        doi = doi[16:]  # 去掉前缀

                    # 提取期刊名
                    primary_location = item.get("primary_location", {}) or {}
                    source_info = primary_location.get("source", {}) or {}
                    journal = source_info.get("display_name", "")

                    paper = Paper(
                        title=item.get("title", ""),
                        authors=authors,
                        year=item.get("publication_year", 0),
                        abstract=item.get("abstract", ""),
                        doi=doi,
                        url=item.get("doi", ""),
                        journal=journal,
                        citation_count=item.get("cited_by_count", 0),
                        source="openalex",
                    )
                    papers.append(paper)

                return papers

        except Exception as e:
            logger.warning(f"OpenAlex 搜索失败: {e}")
            return []

    async def search_and_save(
        self,
        query: str,
        task_id: str = None,
        limit: int = 10,
        source: str = SOURCE_CNKI,
    ) -> List[Paper]:
        """搜索文献并保存到独立文献表（DOI 去重）

        Args:
            source: 数据源，默认 "cnki"（中国网络环境 CNKI 可用）。
        """
        papers = await self.search(query, limit, source=source)

        if self._db_session:
            await self._save_to_db(papers, query, task_id)

        return papers

    async def _save_to_db(
        self,
        papers: List[Paper],
        query: str,
        task_id: str = None,
    ):
        """保存文献到独立表（DOI 去重，增量更新引用计数）"""
        from app.models.database import LiteratureDB

        saved = 0
        updated = 0
        for paper in papers:
            try:
                # DOI 去重
                existing = None
                if paper.doi:
                    existing = self._db_session.query(LiteratureDB).filter(
                        LiteratureDB.doi == paper.doi
                    ).first()

                if existing:
                    # 更新引用计数（可能已增长）
                    if paper.citation_count > (existing.citation_count or 0):
                        existing.citation_count = paper.citation_count
                    # 补充缺失字段
                    if not existing.abstract and paper.abstract:
                        existing.abstract = paper.abstract[:1000]
                    if not existing.journal and paper.journal:
                        existing.journal = paper.journal
                    updated += 1
                else:
                    entry = LiteratureDB(
                        id=str(uuid.uuid4())[:12],
                        title=paper.title[:500],
                        authors=paper.authors,
                        year=paper.year,
                        abstract=paper.abstract[:1000] if paper.abstract else "",
                        doi=paper.doi,
                        url=paper.url,
                        journal=paper.journal,
                        citation_count=paper.citation_count,
                        source=paper.source,
                        search_query=query,
                        task_id=task_id,
                    )
                    self._db_session.add(entry)
                    saved += 1
            except Exception as e:
                logger.warning(f"保存文献失败 '{paper.title[:50]}': {e}")

        if saved or updated:
            self._db_session.commit()
            logger.info(f"文献保存: {saved} 新增, {updated} 更新 (查询: {query})")

    async def search_math_modeling(
        self,
        topic: str,
        task_id: str = None,
        limit: int = 5,
        source: str = None,
    ) -> List[Paper]:
        """搜索数学建模相关文献（保存到独立表）

        Args:
            source: 数据源，默认 None（自动选 CNKI，中国网络环境可用）。
        """
        if source is None:
            source = self.SOURCE_CNKI
        query = f"mathematical modeling {topic}"
        return await self.search_and_save(query, task_id, limit, source=source)

    async def get_history(
        self,
        task_id: str = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取文献搜索历史"""
        if not self._db_session:
            return []
        from app.models.database import LiteratureDB

        q = self._db_session.query(LiteratureDB)
        if task_id:
            q = q.filter(LiteratureDB.task_id == task_id)
        q = q.order_by(LiteratureDB.created_at.desc()).limit(limit)
        entries = q.all()

        return [
            {
                "id": e.id,
                "title": e.title,
                "authors": e.authors,
                "year": e.year,
                "doi": e.doi,
                "journal": e.journal,
                "citation_count": e.citation_count,
                "search_query": e.search_query,
                "task_id": e.task_id,
            }
            for e in entries
        ]

    @staticmethod
    def export_bibtex(papers: List[Dict[str, Any]]) -> str:
        """导出 BibTeX 格式"""
        lines = []
        for i, p in enumerate(papers):
            authors = p.get("authors", [])
            authors_bib = " and ".join(authors) if authors else "{Unknown}"
            first_author = authors[0].split()[-1] if authors else "unknown"
            cite_key = f"{first_author}{p.get('year', '')}{p.get('title', '')[:20].split()[0].lower().rstrip(',.;:')}"

            lines.append(f"@article{{{cite_key},")
            lines.append(f"  title = {{{p.get('title', '')}}},")
            lines.append(f"  author = {{{authors_bib}}},")
            if p.get("year"):
                lines.append(f"  year = {{{p['year']}}},")
            if p.get("journal"):
                lines.append(f"  journal = {{{p['journal']}}},")
            if p.get("doi"):
                lines.append(f"  doi = {{{p['doi']}}},")
            if p.get("url"):
                lines.append(f"  url = {{{p['url']}}},")
            lines.append("}\n")

        return "\n".join(lines)

    @staticmethod
    def export_reference_list(papers: List[Dict[str, Any]], style: str = "gb7714") -> str:
        """导出格式化参考文献列表"""
        lines = ["# 参考文献\n"]
        for i, p in enumerate(papers, 1):
            authors = p.get("authors", [])
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += ", 等"

            ref = f"[{i}] {authors_str}. {p.get('title', '')}"
            if p.get("journal"):
                ref += f"[J]. {p['journal']}"
            if p.get("year"):
                ref += f", {p['year']}"
            if p.get("doi"):
                ref += f". DOI: {p['doi']}"
            lines.append(ref)

        return "\n".join(lines)
