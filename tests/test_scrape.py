"""Tests para etl.scrape — unit tests con HTML mock."""

import pytest

from etl.scrape import RateLimiter, extract_data

SAMPLE_HTML = """
<html>
<body>
    <div class="products">
        <div class="product">
            <h2 class="title">Laptop Pro</h2>
            <span class="price">$1299</span>
            <span class="stock">In Stock</span>
        </div>
        <div class="product">
            <h2 class="title">Mouse RGB</h2>
            <span class="price">$45</span>
            <span class="stock">Out of Stock</span>
        </div>
        <div class="product">
            <h2 class="title">Teclado Mecánico</h2>
            <span class="price">$89</span>
            <span class="stock">In Stock</span>
        </div>
    </div>
</body>
</html>
"""


class TestExtractData:
    def test_extract_single_selector(self):
        results = extract_data(SAMPLE_HTML, ["h2.title"], "http://test.com", "test.com")
        assert len(results) == 3
        assert results[0]["title"] == "Laptop Pro"
        assert results[1]["title"] == "Mouse RGB"

    def test_extract_multiple_selectors(self):
        results = extract_data(SAMPLE_HTML, ["h2.title", ".price", ".stock"], "http://test.com", "test.com")
        assert len(results) == 3
        assert results[0]["title"] == "Laptop Pro"
        assert results[0]["price"] == "$1299"
        assert results[0]["stock"] == "In Stock"

    def test_source_metadata(self):
        results = extract_data(SAMPLE_HTML, ["h2.title"], "http://test.com/products", "test.com")
        assert results[0]["_source_url"] == "http://test.com/products"
        assert results[0]["_source_domain"] == "test.com"

    def test_empty_html(self):
        results = extract_data("<html><body></body></html>", ["h2.title"], "http://test.com", "test.com")
        assert results == []

    def test_selector_no_match(self):
        results = extract_data(SAMPLE_HTML, [".nonexistent"], "http://test.com", "test.com")
        assert results == []

    def test_mismatched_selector_counts(self):
        html = """<html><body>
            <h2 class="title">A</h2><h2 class="title">B</h2>
            <span class="price">$10</span>
        </body></html>"""
        results = extract_data(html, ["h2.title", ".price"], "http://t.com", "t.com")
        assert len(results) == 2
        assert results[0]["price"] == "$10"
        assert results[1]["price"] == ""


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_request_no_wait(self):
        import asyncio

        rl = RateLimiter(delay=1.0)
        start = asyncio.get_event_loop().time()
        await rl.wait("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self):
        import asyncio

        rl = RateLimiter(delay=0.2)
        await rl.wait("example.com")
        start = asyncio.get_event_loop().time()
        await rl.wait("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.15

    @pytest.mark.asyncio
    async def test_different_domains_independent(self):
        import asyncio

        rl = RateLimiter(delay=0.5)
        await rl.wait("a.com")
        start = asyncio.get_event_loop().time()
        await rl.wait("b.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1
