"""News articles for a policy, from GNews (AGENTS.md §4.4).

Kept behind search_articles() so the provider can be swapped.
Stores only title, source, url, publishedAt and description; never full text.
"""
import re
from datetime import datetime

import httpx

from app.models import Article, Policy
from app.services.congress import display_number

GNEWS_URL = "https://gnews.io/api/v4/search"
MAX_ARTICLES = 10


class NewsError(Exception):
    pass


def build_query(policy: Policy) -> str:
    """Pick a search phrase: short title, else nominee name, else the first words of the title."""
    if policy.type == "pn":
        phrase = policy.title.split(",")[0]
        return f'"{_clean(phrase)}" Senate'
    phrase = policy.short_title or policy.title
    words = _clean(phrase).split()
    if len(words) > 8:  # long official titles ("To provide for...") match nothing
        return f'"{display_number(policy.type, policy.number)}" Congress'
    return f'"{" ".join(words)}"'


def _clean(text: str) -> str:
    return re.sub(r'["()]', "", text or "").strip()


async def search_articles(client: httpx.AsyncClient, api_key: str, policy: Policy,
                          since: datetime | None = None) -> list[Article]:
    if not api_key:
        raise NewsError("NEWS_API_KEY is not set")
    params = {"q": build_query(policy), "lang": "en", "country": "us", "max": MAX_ARTICLES,
              "sortby": "relevance", "apikey": api_key}
    if since:
        params["from"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        res = await client.get(GNEWS_URL, params=params)
    except httpx.HTTPError as e:
        raise NewsError(f"GNews request failed: {e}") from e
    if res.status_code >= 400:
        raise NewsError(f"GNews returned {res.status_code}")
    return [
        Article(
            policy_id=policy.policy_id,
            title=a.get("title", ""),
            source=(a.get("source") or {}).get("name", ""),
            url=a["url"],
            published_at=a.get("publishedAt"),
            description=a.get("description"),
        )
        for a in res.json().get("articles", []) if a.get("url")
    ]
