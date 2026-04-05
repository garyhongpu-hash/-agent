from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

from sales_agent.config import settings

logger = logging.getLogger(__name__)

# Pages we actively look for (case-insensitive path matching)
PRIORITY_PATH_KEYWORDS = [
    "about",
    "product",
    "service",
    "team",
    "leadership",
    "contact",
    "news",
    "blog",
    "partner",
    "solution",
    "career",
    "investor",
]


@dataclass
class PageContent:
    url: str
    title: str
    markdown: str


@dataclass
class ScrapedContent:
    homepage: PageContent
    pages: list[PageContent] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Combine all scraped pages into a single context string for the LLM."""
        parts = [
            f"=== 首页: {self.homepage.url} ===",
            f"标题: {self.homepage.title}",
            self.homepage.markdown[:8000],
        ]
        for page in self.pages:
            parts.append(f"\n=== 页面: {page.url} ===")
            parts.append(f"标题: {page.title}")
            parts.append(page.markdown[:4000])
        return "\n".join(parts)


def _is_priority_link(href: str, base_domain: str) -> bool:
    """Check if a link is a priority page we want to crawl."""
    parsed = urlparse(href)
    if parsed.netloc and parsed.netloc != base_domain:
        return False
    path = parsed.path.lower()
    return any(kw in path for kw in PRIORITY_PATH_KEYWORDS)


def _extract_priority_links(
    markdown: str, base_url: str, base_domain: str
) -> list[str]:
    """Extract priority internal links from markdown content."""
    import re

    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", markdown):
        href = match.group(2).strip()
        absolute = urljoin(base_url, href)
        if absolute not in seen and _is_priority_link(absolute, base_domain):
            seen.add(absolute)
            links.append(absolute)
    return links


async def scrape_website(url: str) -> ScrapedContent:
    """Scrape a company website and return structured content."""
    base_domain = urlparse(url).netloc
    config = CrawlerRunConfig(
        word_count_threshold=50,
        excluded_tags=["nav", "footer", "header", "script", "style"],
    )

    async with AsyncWebCrawler() as crawler:
        # 1. Crawl homepage
        homepage_result = await asyncio.wait_for(
            crawler.arun(url=url, config=config),
            timeout=settings.crawl_timeout,
        )

        homepage = PageContent(
            url=url,
            title=homepage_result.metadata.get("title", "") if homepage_result.metadata else "",
            markdown=homepage_result.markdown or "",
        )

        # 2. Discover priority pages from homepage links
        priority_links = _extract_priority_links(
            homepage.markdown, url, base_domain
        )
        links_to_crawl = priority_links[: settings.max_pages_to_crawl - 1]

        # 3. Crawl priority pages concurrently
        pages: list[PageContent] = []

        async def _crawl_page(page_url: str) -> PageContent | None:
            try:
                result = await asyncio.wait_for(
                    crawler.arun(url=page_url, config=config),
                    timeout=settings.crawl_timeout,
                )
                return PageContent(
                    url=page_url,
                    title=result.metadata.get("title", "") if result.metadata else "",
                    markdown=result.markdown or "",
                )
            except Exception:
                logger.warning("Failed to crawl %s", page_url, exc_info=True)
                return None

        tasks = [_crawl_page(link) for link in links_to_crawl]
        results = await asyncio.gather(*tasks)
        pages = [p for p in results if p is not None]

        return ScrapedContent(homepage=homepage, pages=pages)
