from sales_agent.scraper.website import (
    PageContent,
    ScrapedContent,
    _extract_priority_links,
    _is_priority_link,
)


def test_is_priority_link_about():
    assert _is_priority_link("https://example.com/about", "example.com")


def test_is_priority_link_product():
    assert _is_priority_link("https://example.com/products/list", "example.com")


def test_is_priority_link_external():
    assert not _is_priority_link("https://other.com/about", "example.com")


def test_is_priority_link_irrelevant():
    assert not _is_priority_link("https://example.com/legal", "example.com")


def test_extract_priority_links():
    markdown = """
Check out our [About Us](https://example.com/about) page.
See our [Products](/products) listing.
Visit [Google](https://google.com/about) for more.
Read our [Terms](/terms).
"""
    links = _extract_priority_links(markdown, "https://example.com", "example.com")
    assert "https://example.com/about" in links
    assert "https://example.com/products" in links
    assert len(links) == 2  # google excluded, terms not priority


def test_scraped_content_to_context_string():
    scraped = ScrapedContent(
        homepage=PageContent(
            url="https://example.com",
            title="Example Corp",
            markdown="Welcome to Example Corp.",
        ),
        pages=[
            PageContent(
                url="https://example.com/about",
                title="About",
                markdown="We are a leading company.",
            )
        ],
    )
    context = scraped.to_context_string()
    assert "example.com" in context
    assert "Example Corp" in context
    assert "About" in context
