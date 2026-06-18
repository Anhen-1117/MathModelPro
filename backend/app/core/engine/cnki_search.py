"""知网（CNKI）文献搜索引擎

使用 Playwright 无头浏览器（绕过 JS 验证）+ httpx 回退 +
BeautifulSoup HTML 解析，返回与 LiteratureSearch 兼容的 Paper 列表。

反爬策略：
- Playwright Chromium 无头浏览器（执行 JS，绕过验证码页面）
- Cookie 持久化复用
- 模拟浏览器请求头
- 请求节流（≥1.5 秒间隔）
- 指数退避重试（3 次）
- 百度学术兜底
- 失败降级（返回空列表）
"""

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from app.core.engine.literature import Paper


class CnkiSearch:
    """知网（CNKI）文献搜索引擎。

    通过模拟浏览器请求访问知网检索页，解析 HTML 获取文献列表。
    支持 Cookie 持久化、请求节流、自动重试。

    用法:
        cnki = CnkiSearch()
        papers = await cnki.search("数学建模 高血脂", limit=10)
        for p in papers:
            print(p.title, p.authors, p.year)
    """

    # ── 常量 ──────────────────────────────────────────
    BASE_URL = "https://kns.cnki.net"
    # 知网新版检索首页（用于获取 Cookie）
    HOME_URL = f"{BASE_URL}/kns8s/"
    # 检索提交地址（POST）
    SEARCH_URL = f"{BASE_URL}/kns8s/search"
    # 备选：旧版检索 GET 模式
    SEARCH_URL_V2 = f"{BASE_URL}/kns8/defaultresult/index"

    # 浏览器请求头
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # 检索结果页数（每页约 20 条）
    RESULTS_PER_PAGE = 20

    def __init__(
        self,
        cookie_dir: Optional[str] = None,
        proxy: Optional[str] = None,
        request_interval: float = 1.5,
        max_retries: int = 3,
        debug_dir: Optional[str] = None,
    ):
        """初始化知网搜索引擎。

        Args:
            cookie_dir: Cookie 持久化目录。None 则不持久化。
            proxy: HTTP 代理 URL（如 "http://127.0.0.1:7890"）。
            request_interval: 两次请求最小间隔（秒），防止触发反爬。
            max_retries: 最大重试次数。
            debug_dir: 调试目录，保存原始 HTML 响应用于排查解析问题。
        """
        self._cookie_dir = cookie_dir
        self._cookie_file = (
            Path(cookie_dir) / "cnki_cookies.json" if cookie_dir else None
        )
        self._proxy = proxy
        self._request_interval = request_interval
        self._max_retries = max_retries
        self._debug_dir = Path(debug_dir) if debug_dir else None
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

    # ── 公开接口 ──────────────────────────────────────

    async def search(self, query: str, limit: int = 10) -> List[Paper]:
        """搜索知网文献。

        Args:
            query: 搜索关键词。
            limit: 最大返回条数。

        Returns:
            Paper 列表（source 字段标记为 "cnki"）。
        """
        if not query.strip():
            return []

        client = await self._get_client()
        page_limit = max(1, (limit + self.RESULTS_PER_PAGE - 1) // self.RESULTS_PER_PAGE)

        all_papers: List[Paper] = []

        for page in range(1, page_limit + 1):
            try:
                papers = await self._search_page(client, query, page)
                all_papers.extend(papers)
                if len(all_papers) >= limit:
                    break
            except Exception as e:
                logger.warning(f"知网检索第 {page} 页失败: {e}")
                # 继续尝试下一页
                continue

        return all_papers[:limit]

    async def search_math_modeling(
        self, topic: str, limit: int = 5
    ) -> List[Paper]:
        """搜索数学建模相关文献。

        Args:
            topic: 建模主题。
            limit: 最大返回条数。

        Returns:
            Paper 列表。
        """
        query = f"数学建模 {topic}"
        return await self.search(query, limit)

    # ── 会话管理 ──────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端（单例复用）。"""
        if self._client is not None:
            return self._client

        client = httpx.AsyncClient(
            headers=self.DEFAULT_HEADERS.copy(),
            timeout=30.0,
            follow_redirects=True,
            proxy=self._proxy,
        )

        # 尝试加载持久化 Cookie
        if self._load_cookies(client):
            logger.info("知网 Cookie 已加载（复用已保存的会话）")
        else:
            # 建立新会话
            await self._establish_session(client)

        self._client = client
        return self._client

    async def _establish_session(self, client: httpx.AsyncClient) -> bool:
        """访问知网首页建立新会话。

        Args:
            client: httpx 客户端。

        Returns:
            成功返回 True。
        """
        for attempt in range(self._max_retries):
            try:
                await self._throttle()
                resp = await client.get(
                    self.HOME_URL,
                    headers={"Referer": "https://www.cnki.net/"},
                )
                if resp.status_code < 400:
                    logger.info("知网会话建立成功")
                    self._save_cookies(client)
                    return True
                logger.warning(
                    f"知网首页返回 {resp.status_code}（第 {attempt + 1} 次）"
                )
            except Exception as e:
                logger.warning(
                    f"知网会话建立失败（第 {attempt + 1} 次）: {e}"
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        logger.warning("知网会话建立失败，将使用无 Cookie 模式")
        return False

    # ── 搜索实现 ──────────────────────────────────────

    async def _search_page(
        self,
        client: httpx.AsyncClient,
        query: str,
        page: int = 1,
    ) -> List[Paper]:
        """搜索单页结果。依次尝试多种检索模式。

        Args:
            client: httpx 客户端。
            query: 搜索关键词。
            page: 页码（从 1 开始）。

        Returns:
            Paper 列表。
        """
        # 模式 1：Playwright 无头浏览器（绕过 JS 安全验证）
        if PLAYWRIGHT_AVAILABLE:
            try:
                papers = await self._search_with_browser(query, page)
                if papers:
                    return papers
            except Exception as e:
                logger.warning(f"Playwright 浏览器模式失败: {e}")
        else:
            logger.info("Playwright 未安装，使用 HTTP 模式")

        # 模式 2：httpx POST 检索
        try:
            papers = await self._search_post(client, query, page)
            if papers:
                return papers
        except Exception as e:
            logger.debug(f"POST 模式失败: {e}")

        # 模式 3：httpx GET 检索（知网新版）
        try:
            papers = await self._search_get_v2(client, query, page)
            if papers:
                return papers
        except Exception as e:
            logger.debug(f"GET v2 模式失败: {e}")

        # 模式 4：百度学术兜底
        try:
            return await self._search_baidu_scholar(client, query)
        except Exception as e:
            logger.warning(f"百度学术失败: {e}")
            return []

    async def _search_post(
        self,
        client: httpx.AsyncClient,
        query: str,
        page: int = 1,
    ) -> List[Paper]:
        """POST 模式检索知网文献。

        向 /kns8s/search 发送 POST 请求，参数模拟浏览器行为。
        """
        await self._throttle()

        # 知网 POST 检索参数
        form_data = {
            "searchType": "MulityTermsSearch",
            "Platform": "kns8s",
            "ParamIsNullOrEmpty": "false",
            "IsSearch": "false",
            "DbCode": "CFLS",  # 中国学术期刊全文数据库
            "QueryJson": json.dumps(
                {
                    "Platform": "kns8s",
                    "DBCode": "CFLS",
                    "QNode": {
                        "QGroup": [
                            {
                                "Key": "Subject",
                                "Logic": 1,
                                "Items": [],
                                "Title": "",
                                "Type": "def",
                            }
                        ]
                    },
                    "SearchType": "MulityTermsSearch",
                    "SearchFrom": "",
                    "KuaLibCode": "",
                    "SearchNo": "",
                    "KeyWord": query,
                },
                ensure_ascii=False,
            ),
            "SearchStateJson": json.dumps(
                {
                    "DBCodeList": ["CFLS"],
                    "StateID": "",
                    "Plt": "kns8s",
                    "kuaLibCodes": "",
                    "DBCodes": "",
                    "S_Mode": "",
                    "CurrSortField": "DESC",
                    "CurrSortFieldType": "1",
                }
            ),
            "PageIndex": str(page),
            "PageSize": str(self.RESULTS_PER_PAGE),
            "SortField": "DESC",
            "SortFieldType": "1",
            "KeyWord": query,
        }

        resp = await client.post(
            self.SEARCH_URL,
            data=form_data,
            headers={
                "Referer": self.HOME_URL,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        if resp.status_code == 200:
            self._save_debug_html("cnki_post", resp.text)
            return self._parse_html(resp.text, limit=self.RESULTS_PER_PAGE)
        elif resp.status_code == 302 or resp.status_code >= 400:
            raise RuntimeError(f"POST 返回 {resp.status_code}")

        return []

    async def _search_get_v2(
        self,
        client: httpx.AsyncClient,
        query: str,
        page: int = 1,
    ) -> List[Paper]:
        """GET 模式检索（新版知网页面）。

        知网新版检索页通过 URL 参数传递查询。
        """
        await self._throttle()

        # 知网新版检索 GET URL
        # 参考: kns8/defaultresult/index
        from urllib.parse import quote

        params = {
            "kwd": query,
            "dbcode": "CFLS",
            "page": str(page),
            "pageSize": str(self.RESULTS_PER_PAGE),
        }
        query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())

        resp = await client.get(
            f"{self.SEARCH_URL_V2}?{query_string}",
            headers={"Referer": self.HOME_URL},
        )

        if resp.status_code == 200:
            return self._parse_html(resp.text, limit=self.RESULTS_PER_PAGE)

        raise RuntimeError(f"GET v2 检索返回 {resp.status_code}")

    async def _search_get_simple(
        self,
        client: httpx.AsyncClient,
        query: str,
    ) -> List[Paper]:
        """最简 GET 模式（最后兜底）。"""
        await self._throttle()

        resp = await client.get(
            f"{self.BASE_URL}/kns8s/search",
            params={
                "dbcode": "CFLS",
                "kw": query,
                "kwd": query,
            },
            headers={"Referer": self.HOME_URL},
        )

        if resp.status_code == 200:
            return self._parse_html(resp.text, limit=self.RESULTS_PER_PAGE)

        raise RuntimeError(f"GET simple 检索返回 {resp.status_code}")

    # ── HTML 解析 ──────────────────────────────────────

    def _parse_html(self, html: str, limit: int = 20) -> List[Paper]:
        """解析知网检索结果 HTML。

        知网检索结果页的关键 HTML 结构（可能随版本变化）：
        - 结果容器：table.result-table-list 或 div.result-table-list
        - 每一行：tr 元素，包含标题链接 <a>、作者、期刊、年份等

        Args:
            html: 检索结果页 HTML。
            limit: 最大解析条数。

        Returns:
            Paper 列表。
        """
        soup = BeautifulSoup(html, "lxml")
        papers: List[Paper] = []

        # ── 尝试多种选择器（兼容不同版本的知网页面）──

        # 模式 A：新版结果行
        rows = soup.select("tr[id^='tr']")
        if not rows:
            # 模式 B：class 选择
            rows = soup.select("tr.result-row, tr.result-item")
        if not rows:
            # 模式 C：表格行（旧版）
            result_table = soup.select_one(
                "table.result-table-list, div.result-table-list"
            )
            if result_table:
                rows = result_table.select("tr")[1:]  # 跳过表头

        # 如果以上都没匹配到，尝试更宽泛的匹配
        if not rows:
            rows = soup.select("table tbody tr")
            # 过滤掉明显不是结果的行（比如表头）
            rows = [r for r in rows if r.select_one("a") and len(r.select("td")) >= 3]

        for row in rows:
            if len(papers) >= limit:
                break

            try:
                paper = self._parse_row(row)
                if paper and paper.title:
                    papers.append(paper)
            except Exception as e:
                logger.debug(f"解析知网结果行失败: {e}")
                continue

        # 如果结构化解析没结果，尝试从页面全文提取链接
        if not papers:
            papers = self._parse_fallback(soup, limit)

        logger.info(f"知网检索解析到 {len(papers)} 篇文献")
        return papers

    def _parse_row(self, row) -> Optional[Paper]:
        """解析单行结果。

        知网结果行的典型 <td> 结构：
        [序号] [标题+作者+来源链接] [来源期刊] [发表时间] [被引] [下载]

        Args:
            row: BeautifulSoup Tag（<tr> 元素）。

        Returns:
            Paper 或 None。
        """
        # ── 提取标题 + 链接 ──
        title_tag = row.select_one("a[href*='detail'], a[target='_blank']")
        if not title_tag:
            title_tag = row.select_one("a")
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        if not title or len(title) < 2:
            return None

        url = title_tag.get("href", "")
        if url and not url.startswith("http"):
            url = self.BASE_URL + url

        # ── 提取文本 ──
        # 知网结果行的完整文本（包含作者、期刊等信息）
        row_text = row.get_text(" ", strip=True)

        # ── 提取作者 ──
        authors = self._extract_authors(row, row_text)

        # ── 提取年份 ──
        year = self._extract_year(row_text)

        # ── 提取期刊 ──
        journal = self._extract_journal(row)

        # ── 提取被引数 ──
        citation_count = self._extract_citations(row)

        # ── 提取摘要 ──
        abstract = self._extract_abstract(row)

        # ── 提取 DOI ──
        doi = self._extract_doi(row, row_text)

        paper = Paper(
            title=title,
            authors=authors,
            year=year,
            abstract=abstract,
            doi=doi,
            url=url,
            journal=journal,
            citation_count=citation_count,
            source="cnki",
        )
        return paper

    # ── 字段提取辅助方法 ──────────────────────────────

    @staticmethod
    def _extract_authors(row, row_text: str) -> List[str]:
        """从结果行提取作者列表。

        作者通常出现在标题之后、期刊名之前。
        知网的作者格式：张三, 李四, 王五 或 张三;李四;王五
        """
        # 尝试从特定的作者元素提取
        author_tag = row.select_one(
            "td.author, span.author, .author, [class*='author']"
        )
        if author_tag:
            text = author_tag.get_text(strip=True)
            if text:
                authors = re.split(r"[,;，；\s]+", text)
                return [a.strip() for a in authors if a.strip() and len(a.strip()) > 1]

        # 从行文本中用正则提取（标题后的作者模式）
        # 匹配：作者名通常为2-4个中文字符，逗号分隔
        author_patterns = [
            r"】\s*([^】]+?)\s*\d{4}",  # 】作者名 2024
            r"\.\s*([^.]+\d{4})",  # 有时作者和年份连在一起
        ]
        for pattern in author_patterns:
            match = re.search(pattern, row_text)
            if match:
                text = match.group(1)
                # 尝试按分隔符拆分
                parts = re.split(r"[,;，；\s]{2,}", text)
                parts = [p.strip() for p in parts if len(p.strip()) >= 2]
                if parts and all(len(p) <= 6 for p in parts):
                    return parts

        return []

    @staticmethod
    def _extract_year(text: str) -> int:
        """从文本中提取发表年份。"""
        # 匹配 4 位年份（1900-2099）
        match = re.search(r"(19|20)\d{2}", text)
        if match:
            return int(match.group(0))
        return 0

    @staticmethod
    def _extract_journal(row) -> str:
        """从结果行提取期刊名。"""
        journal_tag = row.select_one(
            "td.source, span.source, .source, [class*='source'], [class*='journal']"
        )
        if journal_tag:
            return journal_tag.get_text(strip=True)
        return ""

    @staticmethod
    def _extract_citations(row) -> int:
        """从结果行提取被引次数。"""
        cite_tag = row.select_one(
            "td.cite, span.cite, .cite, [class*='cite'], [class*='引用']"
        )
        if cite_tag:
            text = cite_tag.get_text(strip=True)
            match = re.search(r"\d+", text)
            if match:
                return int(match.group(0))
        return 0

    @staticmethod
    def _extract_abstract(row) -> str:
        """从结果行提取摘要。"""
        abstract_tag = row.select_one(
            "td.abstract, span.abstract, .abstract, [class*='abstract'], [class*='摘要']"
        )
        if abstract_tag:
            return abstract_tag.get_text(strip=True)[:1000]
        return ""

    @staticmethod
    def _extract_doi(row, row_text: str) -> str:
        """从结果行提取 DOI。"""
        # DOI 格式：10.xxxx/xxxx
        match = re.search(r"10\.\d{4,}/[^\s\"'<>]+", row_text)
        if match:
            return match.group(0)
        return ""

    def _parse_fallback(self, soup: BeautifulSoup, limit: int) -> List[Paper]:
        """兜底解析：从页面全文提取任何可能的文献链接。"""
        papers = []
        seen = set()

        for tag in soup.select("a[href*='detail'], a[href*='Article']"):
            title = tag.get_text(strip=True)
            if title and len(title) > 5 and title not in seen:
                seen.add(title)
                papers.append(
                    Paper(
                        title=title,
                        authors=[],
                        url=self.BASE_URL + tag["href"]
                        if tag["href"].startswith("/")
                        else tag["href"],
                        source="cnki",
                    )
                )
            if len(papers) >= limit:
                break

        return papers

    # ── Cookie 持久化 ──────────────────────────────────

    def _save_cookies(self, client: httpx.AsyncClient):
        """保存 Cookie 到文件。"""
        if not self._cookie_file:
            return
        try:
            self._cookie_file.parent.mkdir(parents=True, exist_ok=True)
            cookies = [
                {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
                for c in client.cookies.jar
            ]
            self._cookie_file.write_text(
                json.dumps(cookies, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug(f"知网 Cookie 已保存 ({len(cookies)} 条)")
        except Exception as e:
            logger.debug(f"保存知网 Cookie 失败: {e}")

    def _load_cookies(self, client: httpx.AsyncClient) -> bool:
        """从文件加载 Cookie。

        Returns:
            成功加载返回 True。
        """
        if not self._cookie_file or not self._cookie_file.exists():
            return False
        try:
            cookies = json.loads(self._cookie_file.read_text(encoding="utf-8"))
            for c in cookies:
                client.cookies.set(
                    name=c["name"],
                    value=c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                )
            logger.debug(f"知网 Cookie 已加载 ({len(cookies)} 条)")
            return True
        except Exception as e:
            logger.debug(f"加载知网 Cookie 失败: {e}")
            return False

    # ── 请求节流 ──────────────────────────────────────

    async def _throttle(self):
        """请求节流，确保两次请求间隔 >= request_interval 秒。"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._request_interval:
                await asyncio.sleep(self._request_interval - elapsed)
            self._last_request_time = time.monotonic()

    # ── 调试 ──────────────────────────────────────────

    def _save_debug_html(self, label: str, html: str):
        """保存原始 HTML 到调试目录。"""
        if not self._debug_dir:
            return
        try:
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            path = self._debug_dir / f"{label}_{int(time.time())}.html"
            path.write_text(html, encoding="utf-8")
            logger.info(f"调试 HTML 已保存: {path} ({len(html)} 字节)")
        except Exception as e:
            logger.debug(f"保存调试 HTML 失败: {e}")

    # ── Playwright 无头浏览器 ─────────────────────────

    async def _search_with_browser(
        self,
        query: str,
        page: int = 1,
    ) -> List[Paper]:
        """使用 Playwright Chromium 无头浏览器搜索知网。

        这是绕过知网 JS 安全验证（CAPTCHA）的关键方法：
        1. 启动无头 Chromium
        2. 访问知网首页（获取 Cookie + 执行 JS 验证）
        3. 在搜索框输入关键词并提交
        4. 等待结果页加载完毕（JS 渲染）
        5. 获取完整 HTML
        6. 传给 BeautifulSoup 解析

        Args:
            query: 搜索关键词。
            page: 页码。

        Returns:
            Paper 列表。
        """
        from urllib.parse import quote

        await self._throttle()
        logger.info(f"Playwright 浏览器搜索知网: {query}")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )

            page_obj = await context.new_page()

            try:
                # Step 1: 访问知网首页（建立会话，通过 JS 验证）
                await page_obj.goto(
                    self.HOME_URL,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                # 等待页面 JS 执行完毕（安全验证可能在这时完成）
                await asyncio.sleep(2)

                # Step 2: 使用搜索框提交查询
                # 知网首页有搜索框，直接填关键词 + 点击搜索按钮
                try:
                    # 等待搜索框出现
                    await page_obj.wait_for_selector(
                        "input#txt_search, input.search-input, input[type='text']",
                        timeout=5000,
                    )
                    # 填入关键词
                    await page_obj.fill(
                        "input#txt_search, input.search-input, input[type='text']",
                        query,
                    )
                    # 点击搜索按钮
                    await page_obj.click(
                        "input[type='submit'], button.search-btn, input[type='button'][value*='搜索']",
                        timeout=3000,
                    )
                except Exception:
                    # 如果首页搜索框不可用，直接通过 URL 访问结果页
                    search_url = (
                        f"{self.BASE_URL}/kns8/defaultresult/index?"
                        f"kwd={quote(query)}&dbcode=CFLS&page={page}"
                    )
                    await page_obj.goto(
                        search_url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )

                # Step 3: 等待结果加载
                await asyncio.sleep(3)
                # 等待结果列表渲染
                try:
                    await page_obj.wait_for_selector(
                        "table.result-table-list, div.result-table-list, "
                        "div.result, tr[class*='result'], td a[href*='detail']",
                        timeout=10000,
                    )
                except Exception:
                    logger.debug("等待结果超时，尝试获取当前 HTML")

                # Step 4: 获取渲染后的 HTML
                html = await page_obj.content()
                self._save_debug_html("cnki_browser", html)

            except Exception as e:
                logger.error(f"Playwright 浏览器搜索失败: {e}")
                # 截图保存现场
                try:
                    if self._debug_dir:
                        screenshot = self._debug_dir / f"cnki_error_{int(time.time())}.png"
                        await page_obj.screenshot(path=str(screenshot))
                        logger.info(f"错误截图已保存: {screenshot}")
                except Exception:
                    pass
                raise

            finally:
                await browser.close()

        # Step 5: 解析 HTML
        return self._parse_html(html, limit=self.RESULTS_PER_PAGE)

    # ── 百度学术兜底 ──────────────────────────────────

    async def _search_baidu_scholar(
        self,
        client: httpx.AsyncClient,
        query: str,
    ) -> List[Paper]:
        """百度学术搜索（中国最可靠的学术搜索兜底方案）。

        百度学术相比知网的优势：
        - 无需登录/Cookie，反爬更宽松
        - HTML 结构更简单稳定
        - 覆盖知网/万方/维普等多个中文数据库

        Args:
            client: httpx 客户端。
            query: 搜索关键词。

        Returns:
            Paper 列表。
        """
        from urllib.parse import quote

        await self._throttle()

        url = f"https://xueshu.baidu.com/s?wd={quote(query)}"
        resp = await client.get(
            url,
            headers={
                "Referer": "https://xueshu.baidu.com/",
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
        )

        if resp.status_code != 200:
            raise RuntimeError(f"百度学术返回 {resp.status_code}")

        self._save_debug_html("baidu_scholar", resp.text)
        return self._parse_baidu_html(resp.text)

    def _parse_baidu_html(self, html: str, limit: int = 20) -> List[Paper]:
        """解析百度学术搜索结果 HTML。

        百度学术结果结构：
        <div class="result sc_default_result">
            <h3><a class="title">论文标题</a></h3>
            <div class="sc_info">作者 · 期刊 · 年份</div>
            <div class="c_abstract">摘要...</div>
            <div class="sc_cite">被引量: N</div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        papers: List[Paper] = []

        for item in soup.select("div.result, div.sc_default_result"):
            if len(papers) >= limit:
                break
            try:
                # 标题
                title_tag = item.select_one("h3 a, a.title")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                # 链接
                url = title_tag.get("href", "")

                # 作者/期刊/年份信息
                info_tag = item.select_one(
                    "div.sc_info, div.info, div.author_wr, p.author_text"
                )
                authors = []
                year = 0
                journal = ""
                if info_tag:
                    info_text = info_tag.get_text(strip=True)
                    # 格式：作者1, 作者2. 期刊名, 2024
                    # 或者：Author1; Author2 - Journal - 2024
                    # 提取年份
                    ym = re.search(r"(19|20)\d{2}", info_text)
                    if ym:
                        year = int(ym.group(0))
                    # 提取作者（年份之前的部分）
                    if year:
                        pre_year = info_text[: info_text.find(str(year))]
                        # 清理分隔符
                        pre_year = re.sub(r"[\.\-\s]+$", "", pre_year)
                        parts = re.split(r"[,;，；]", pre_year)
                        authors = [p.strip() for p in parts if len(p.strip()) >= 2]
                    # 提取期刊（年份之后）
                    post_year = info_text[info_text.find(str(year)) + 4 :]
                    journal = re.sub(r"^[\s\-\.]+", "", post_year).strip()[:200]

                # 摘要
                abstract_tag = item.select_one("div.c_abstract, div.abstract, p.abstract")
                abstract = ""
                if abstract_tag:
                    abstract = abstract_tag.get_text(strip=True)[:1000]

                # 被引量
                cite_tag = item.select_one("div.sc_cite, span.cite, .cited")
                citation_count = 0
                if cite_tag:
                    ct = re.search(r"\d+", cite_tag.get_text())
                    if ct:
                        citation_count = int(ct.group(0))

                # 数据源链接中可能包含 DOI
                doi = ""
                doi_match = re.search(r"10\.\d{4,}/[^\s\"'<>]+", html)
                if doi_match:
                    doi = doi_match.group(0)

                papers.append(
                    Paper(
                        title=title,
                        authors=authors,
                        year=year,
                        abstract=abstract,
                        doi=doi,
                        url=url,
                        journal=journal,
                        citation_count=citation_count,
                        source="baidu_scholar",
                    )
                )
            except Exception as e:
                logger.debug(f"解析百度学术结果失败: {e}")
                continue

        logger.info(f"百度学术检索到 {len(papers)} 篇文献")
        return papers

    # ── 清理 ──────────────────────────────────────────

    async def close(self):
        """关闭 httpx 客户端。"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()
