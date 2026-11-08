"""News articles from GNews (AGENTS.md §4.4).

Kept behind search_articles() and fetch_feed() so the provider can be swapped.
Stores only title, source, url, publishedAt and description; never full text.
"""
import asyncio
import math
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.models import Article, Policy
from app.services.congress import display_number

GNEWS_URL = "https://gnews.io/api/v4/search"
MAX_ARTICLES = 10
REQUEST_SPACING_SECONDS = 1.2  # GNews allows about 1 request per second

# Home page feed. Established news organizations with national political reporting, matched on URL domain.
ALLOWED_NEWS_DOMAINS = frozenset({
    "apnews.com", "reuters.com", "npr.org", "pbs.org", "bbc.com", "bbc.co.uk", "abcnews.go.com", "abcnews.com",
    "cbsnews.com", "nbcnews.com", "usatoday.com", "wsj.com", "nytimes.com", "washingtonpost.com", "politico.com",
    "thehill.com", "axios.com", "rollcall.com", "bloomberg.com",
})
FEED_SIZE = 9
FEED_LOOKBACK = timedelta(days=7)
FEED_MAX_RESULTS = 25  # the outlet allowlist removes most results, so ask for as many as the plan returns
# Multi-word queries are all-terms matches, and some return nothing. Relevance surfaces far more major outlets than
# newest-first, which is mostly small sites.
FEED_QUERIES = ("Congress", "Senate", "Congress legislation", "federal policy Congress")

_OPINION_PATH = re.compile(r"/(?:opinions?|commentary|editorials?|letters)(?:/|$)", re.IGNORECASE)
_OPINION_TITLE = re.compile(r"^\s*(?:opinion|commentary|editorial|letters? to the editor)\s*[:|\-–—]"
                            r"|[|\-–—]\s*opinion\s*$", re.IGNORECASE)
_ON_TOPIC = re.compile(
    r"\b(?:congress(?:ional|man|woman|members?)?|senate|senators?|house of representatives|house speaker|"
    r"speaker of the house|house (?:republicans?|democrats?|committee|panel|bill|vote[sd]?|passe[sd]|gop)|"
    r"lawmakers?|legislation|appropriations?|filibuster|federal (?:policy|budget|funding|law|agency|agencies|"
    r"government|shutdown)|government shutdown)\b", re.IGNORECASE)
_OFF_TOPIC = re.compile(r"\b(?:snl|saturday night live|late[- ]night|kimmel|colbert|fallon|box office|celebrity|"
                        r"horoscope|nfl|nba|mlb|nhl|grammys?|oscars?|emmys?)\b", re.IGNORECASE)

_NAMED_ACT = re.compile(r"\bAct(?:\s+of\s+\d{4})?$", re.IGNORECASE)
_OFFICIAL_TITLE = re.compile(r"^(?:to|a bill|an act|providing|making|adopting|expressing|authorizing)\b", re.IGNORECASE)

_NAME_STOPWORDS = frozenset(_w.rstrip("s") for _w in "a an and act at by for from in of on or the to with".split())

_spacing_lock = asyncio.Lock()
_last_request = 0.0


class NewsError(Exception):
    pass


def build_query(policy: Policy) -> str:
    """Pick a search phrase: short title, else nominee name, else the first words of the title."""
    if policy.type == "pn":
        phrase = policy.title.split(",")[0]
        return f'"{_clean(phrase)}" Senate'
    if _is_long_title(policy):  # long official titles ("To provide for...") match nothing
        return f'"{display_number(policy.type, policy.number)}" Congress'
    return f'"{_search_name(policy)}"'


def fallback_query(policy: Policy) -> str | None:
    """A second try by bill number, for bills first searched by name. Nominee names need no fallback."""
    if policy.type == "pn" or _is_long_title(policy):
        return None
    return f'"{display_number(policy.type, policy.number)}" Congress'


def _policy_name(policy: Policy) -> str:
    return " ".join(_clean(policy.short_title or policy.title).split())


def _search_name(policy: Policy) -> str:
    return re.sub(r"\s+of\s+\d{4}$", "", _policy_name(policy))  # news rarely includes "of 2025"


def _is_long_title(policy: Policy) -> bool:
    """A popular name ending in "Act" is searchable at any length; other long titles are official descriptions."""
    name = _policy_name(policy)
    if _NAMED_ACT.search(name) and not _OFFICIAL_TITLE.match(name):
        return False
    return len(name.split()) > 8


def _clean(text: str) -> str:
    return re.sub(r'["()]', "", text or "").strip()


def congress_start(congress: int) -> datetime:
    return datetime(1787 + 2 * congress, 1, 3, tzinfo=timezone.utc)


def names_bill(article: Article, policy: Policy) -> bool:
    """True only if the headline or description cites this bill's number, written as H.R. 29, HR 29 or H.R.29."""
    letters = re.findall(r"[A-Za-z]+", display_number(policy.type, policy.number))
    prefix = r"\.?\s*".join(letters)
    pattern = rf"(?<![A-Za-z]){prefix}\.?\s*{re.escape(policy.number)}\b"
    return bool(re.search(pattern, f"{article.title} {article.description or ''}", re.IGNORECASE))


async def _wait_for_slot() -> None:
    """Space every GNews call in this process, across all requests."""
    global _last_request
    async with _spacing_lock:
        delay = _last_request + REQUEST_SPACING_SECONDS - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        _last_request = time.monotonic()


async def _request(client: httpx.AsyncClient, api_key: str, params: dict) -> list[dict]:
    """Raises NewsError on any failure, so a rate limit is never mistaken for 'no articles'."""
    if not api_key:
        raise NewsError("NEWS_API_KEY is not set")
    await _wait_for_slot()
    try:
        res = await client.get(GNEWS_URL, params={"max": MAX_ARTICLES, **params, "lang": "en", "country": "us",
                                                  "apikey": api_key})
    except httpx.HTTPError as e:
        raise NewsError("the news provider could not be reached") from e  # the error text can include the key
    if res.status_code >= 400:
        raise NewsError(f"GNews returned {res.status_code}")
    try:
        body = res.json()
    except ValueError as e:
        raise NewsError("GNews returned an invalid response") from e
    if body.get("errors"):
        raise NewsError("GNews reported an error")
    return body.get("articles", [])


def _to_articles(raw: list[dict], policy_id: str | None) -> list[Article]:
    return [Article(policy_id=policy_id, title=a.get("title", ""), source=(a.get("source") or {}).get("name", ""),
                    url=a["url"], published_at=a.get("publishedAt"), description=a.get("description"))
            for a in raw if a.get("url")]


def _since_param(since: datetime) -> str:
    return since.strftime("%Y-%m-%dT%H:%M:%SZ")


async def search_articles(client: httpx.AsyncClient, api_key: str, policy: Policy,
                          since: datetime | None = None) -> list[Article]:
    # Names and numbers both repeat across Congresses, so search only from the start of this bill's Congress.
    start = max(since, congress_start(policy.congress)) if since else congress_start(policy.congress)
    params = {"sortby": "relevance", "from": _since_param(start)}
    articles = _to_articles(await _request(client, api_key, {**params, "q": build_query(policy)}), policy.policy_id)
    fallback = fallback_query(policy)
    if articles or not fallback:
        return articles
    found = await _request(client, api_key, {**params, "q": fallback})
    return [a for a in _to_articles(found, policy.policy_id) if names_bill(a, policy)]


def is_allowed_source(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in ALLOWED_NEWS_DOMAINS)


def is_opinion(article: Article) -> bool:
    return bool(_OPINION_PATH.search(urlparse(article.url).path) or _OPINION_TITLE.search(article.title))


def is_on_topic(article: Article) -> bool:
    text = f"{article.title} {article.description or ''}"
    return bool(_ON_TOPIC.search(text)) and not _OFF_TOPIC.search(text)


def belongs_in_feed(article: Article) -> bool:
    return is_allowed_source(article.url) and not is_opinion(article) and is_on_topic(article)


def _terms(text: str) -> list[str]:
    """Lowercase words with apostrophes and trailing s removed, so "women's" matches "women"."""
    return [word.rstrip("s") for word in re.findall(r"[a-z0-9]+", re.sub(r"['’]", "", text.lower()))]


def is_about_policy(article: Article, policy: Policy) -> bool:
    """True if the headline or description cites the bill number, or uses most of the words in its name."""
    if names_bill(article, policy):
        return True
    if policy.type != "pn" and _is_long_title(policy):
        return False  # the words of a long official title are too generic to prove anything
    name = policy.title.split(",")[0] if policy.type == "pn" else _search_name(policy)
    wanted = set(_terms(name)) - _NAME_STOPWORDS
    needed = min(len(wanted), max(2, math.ceil(len(wanted) * 0.6)))
    return bool(wanted) and len(wanted & set(_terms(f"{article.title} {article.description or ''}"))) >= needed


def belongs_on_policy_page(article: Article, policy: Policy) -> bool:
    """Any publisher may appear here. Opinion pieces and articles about something else may not."""
    return not is_opinion(article) and is_about_policy(article, policy)


def _title_key(article: Article) -> str:
    return re.sub(r"\W+", " ", article.title).strip().lower()


async def fetch_feed(client: httpx.AsyncClient, api_key: str) -> list[Article]:
    """Vetted, newest-first news about Congress. Stops querying once the feed is full."""
    since = datetime.now(timezone.utc) - FEED_LOOKBACK
    kept: dict[str, Article] = {}
    for index, query in enumerate(FEED_QUERIES):
        try:
            raw = await _request(client, api_key, {"q": query, "sortby": "relevance", "max": FEED_MAX_RESULTS,
                                                   "from": _since_param(since)})
        except NewsError:
            if index == 0 or not kept:
                raise
            break  # what the earlier queries found is still good
        for article in _to_articles(raw, None):
            if belongs_in_feed(article):
                kept.setdefault(_title_key(article), article)
        if len(kept) >= FEED_SIZE:
            break
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(kept.values(), key=lambda a: a.published_at or oldest, reverse=True)[:FEED_SIZE]
