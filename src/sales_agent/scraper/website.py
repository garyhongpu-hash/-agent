from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

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


def _html_to_text(html: str) -> str:
    """Convert HTML to clean text, preserving structure."""
    soup = BeautifulSoup(html, "lxml")
    # Remove non-content tags
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _extract_title(html: str) -> str:
    """Extract page title from HTML."""
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True) if title_tag else ""


def _extract_priority_links_from_html(
    html: str, base_url: str, base_domain: str
) -> list[str]:
    """Extract priority internal links from HTML."""
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        absolute = urljoin(base_url, href)
        if absolute not in seen and _is_priority_link(absolute, base_domain):
            seen.add(absolute)
            links.append(absolute)
    return links


def _extract_priority_links(
    markdown: str, base_url: str, base_domain: str
) -> list[str]:
    """Extract priority internal links from markdown content."""
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", markdown):
        href = match.group(2).strip()
        absolute = urljoin(base_url, href)
        if absolute not in seen and _is_priority_link(absolute, base_domain):
            seen.add(absolute)
            links.append(absolute)
    return links


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SalesAgent/1.0; +https://github.com)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


async def _fetch_page(client: httpx.AsyncClient, url: str) -> PageContent | None:
    """Fetch a single page and extract text content."""
    try:
        resp = await client.get(url, follow_redirects=True, timeout=settings.crawl_timeout)
        resp.raise_for_status()
        html = resp.text
        return PageContent(
            url=url,
            title=_extract_title(html),
            markdown=_html_to_text(html),
        )
    except Exception:
        logger.warning("Failed to fetch %s", url, exc_info=True)
        return None


async def scrape_website(url: str) -> ScrapedContent:
    """Scrape a company website and return structured content.

    Uses httpx + BeautifulSoup for fast, lightweight scraping.
    Falls back to Crawl4AI if JS rendering is needed (when available).
    """
    base_domain = urlparse(url).netloc

    async with httpx.AsyncClient(headers=_HEADERS) as client:
        # 1. Fetch homepage
        resp = await client.get(url, follow_redirects=True, timeout=settings.crawl_timeout)
        resp.raise_for_status()
        homepage_html = resp.text

        homepage = PageContent(
            url=url,
            title=_extract_title(homepage_html),
            markdown=_html_to_text(homepage_html),
        )

        # 2. Discover priority pages from homepage links
        priority_links = _extract_priority_links_from_html(
            homepage_html, url, base_domain
        )
        links_to_crawl = priority_links[: settings.max_pages_to_crawl - 1]

        # 3. Fetch priority pages concurrently
        tasks = [_fetch_page(client, link) for link in links_to_crawl]
        results = await asyncio.gather(*tasks)
        pages = [p for p in results if p is not None]

        return ScrapedContent(homepage=homepage, pages=pages)
