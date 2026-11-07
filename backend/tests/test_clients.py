import httpx
import pytest

from app.models import Policy
from app.services.congress import CongressClient, congress_gov_url, ordinal
from app.services.news import build_query, search_articles


def mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_urls():
    assert ordinal(118) == "118th" and ordinal(101) == "101st" and ordinal(112) == "112th"
    assert congress_gov_url(118, "hr", "2") == "https://www.congress.gov/bill/118th-congress/house-bill/2"
    assert congress_gov_url(119, "pn", "12-3") == "https://www.congress.gov/nomination/119th-congress/12"


@pytest.mark.asyncio
async def test_congress_get_bill():
    def handler(req: httpx.Request):
        if req.url.path.endswith("/summaries"):
            return httpx.Response(200, json={"summaries": [
                {"updateDate": "2023-01-01", "text": "<p>Old</p>"},
                {"updateDate": "2023-05-01", "text": "<p>This bill <b>repeals</b> &amp; ends.</p>"}]})
        return httpx.Response(200, json={"bill": {"title": "Iraq AUMF Repeal",
                                                  "latestAction": {"actionDate": "2023-03-29", "text": "Passed Senate"}}})
    async with mock_client(handler) as c:
        p = await CongressClient(c, "key").get_policy("118-s-316")
    assert p.title == "Iraq AUMF Repeal"
    assert p.crs_summary == "This bill repeals & ends."
    assert p.latest_action.text == "Passed Senate"


@pytest.mark.asyncio
async def test_congress_missing_bill_uses_fallback_title():
    async with mock_client(lambda req: httpx.Response(404)) as c:
        p = await CongressClient(c, "key").get_policy("118-hr-9999", fallback_title="A bill")
    assert p.title == "A bill" and p.crs_summary is None


def test_news_query():
    short = Policy(policy_id="119-hr-1", congress=119, type="hr", number="1", title="One Big Beautiful Bill Act")
    long = Policy(policy_id="118-s-316", congress=118, type="s", number="316",
                  title="A bill to repeal the authorizations for use of military force against Iraq.")
    nom = Policy(policy_id="119-pn-1129", congress=119, type="pn", number="1129",
                 title="Keith Sonderling, of Florida, to be Secretary of Labor")
    assert build_query(short) == '"One Big Beautiful Bill Act"'
    assert build_query(long) == '"S. 316" Senate'
    assert build_query(nom) == '"Keith Sonderling" Senate'


@pytest.mark.asyncio
async def test_news_search():
    def handler(req: httpx.Request):
        assert req.url.params["apikey"] == "k"
        return httpx.Response(200, json={"articles": [
            {"title": "T", "description": "D", "content": "full text not stored", "url": "https://x.test/a",
             "publishedAt": "2025-07-01T12:00:00Z", "source": {"name": "X News"}}]})
    policy = Policy(policy_id="119-hr-1", congress=119, type="hr", number="1", title="One Big Beautiful Bill Act")
    async with mock_client(handler) as c:
        articles = await search_articles(c, "k", policy)
    assert len(articles) == 1 and articles[0].source == "X News"
    assert "content" not in articles[0].model_dump()
