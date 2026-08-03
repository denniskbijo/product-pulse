from app.providers.discovery.bestsellers_html import parse_bestsellers_html

SAMPLE_HTML = """
<html><body>
  <div id="gridItemRoot" data-asin="B0AAAAAAA1">
    <a href="/dp/B0AAAAAAA1">Product 1</a>
  </div>
  <div class="zg-grid-general-faceout">
    <a href="/Kitchen-Gadget/dp/B0AAAAAAA2/ref=zg_bs">Product 2</a>
  </div>
  <div data-asin="B0AAAAAAA3"><span>Product 3</span></div>
  <a href="/dp/B0AAAAAAA4">Loose link 4</a>
  <a href="/dp/B0AAAAAAA1">Duplicate</a>
</body></html>
"""


def test_parse_bestsellers_extracts_ranked_asins():
    entries = parse_bestsellers_html(SAMPLE_HTML, top_n=10)
    asins = [e.asin for e in entries]
    assert asins[:3] == ["B0AAAAAAA1", "B0AAAAAAA2", "B0AAAAAAA3"]
    assert entries[0].rank == 1
    assert "B0AAAAAAA1" in asins
    assert asins.count("B0AAAAAAA1") == 1


def test_parse_bestsellers_respects_top_n():
    entries = parse_bestsellers_html(SAMPLE_HTML, top_n=2)
    assert len(entries) == 2
    assert [e.rank for e in entries] == [1, 2]
