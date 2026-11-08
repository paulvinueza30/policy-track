"""House Clerk roll-call vote XML: fetch + parse (AGENTS.md §4.2a).

Callers should catch HouseBlockedError and fall back to Voteview (app.services.voteview).
"""
import asyncio
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.services.vote_types import ParsedPosition, ParsedVote, normalize_policy_id, session_year

BASE = "https://clerk.house.gov/evs"
EASTERN = ZoneInfo("America/New_York")
BATCH = 5  # files fetched at a time

_CAST_MAP = {"yea": "Yea", "aye": "Yea", "nay": "Nay", "no": "Nay", "present": "Present", "not voting": "Not Voting"}


class HouseBlockedError(Exception):
    """The Clerk's site refused the request or returned something that isn't vote XML."""


class VoteNotFound(Exception):
    """No file for this number: the end of the session's votes."""


def vote_url(year: int, vote_number: int) -> str:
    return f"{BASE}/{year}/roll{vote_number:03d}.xml"


def normalize_cast(cast: str) -> str:
    return _CAST_MAP.get(cast.strip().lower(), "Not Voting")


def split_legis_num(legis_num: str) -> tuple[str | None, str | None]:
    """"H R 35" -> ("H R", "35"); "H J RES 1" -> ("H J RES", "1"); "QUORUM" -> (None, None)."""
    m = re.fullmatch(r"([A-Za-z. ]+?)\s*(\d+)", (legis_num or "").strip())
    return (m.group(1), m.group(2)) if m else (None, None)


def _parse_date(day: str, time_etz: str | None) -> datetime:
    """("13-Feb-2025", "10:45") -> aware datetime (US Eastern)."""
    when = datetime.strptime(day.strip(), "%d-%b-%Y")
    if time_etz:
        hour, minute = time_etz.split(":")
        when = when.replace(hour=int(hour), minute=int(minute))
    return when.replace(tzinfo=EASTERN)


def parse_vote(content: bytes) -> ParsedVote | None:
    """Single roll-call XML -> ParsedVote keyed by bioguide id.

    Returns None for quorum calls and Speaker elections, which don't fit the vote model (AGENTS.md §2).
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise HouseBlockedError(f"clerk.house.gov did not return XML: {e}") from e
    meta = root.find("vote-metadata")
    if root.tag != "rollcall-vote" or meta is None:
        raise HouseBlockedError(f"Unexpected House vote root <{root.tag}>")

    def text(tag: str) -> str:
        return (meta.findtext(tag) or "").strip()

    question = text("vote-question")
    if text("vote-type").upper() == "QUORUM" or question == "Election of the Speaker":
        return None

    congress = int(text("congress"))
    doc_type, number = split_legis_num(text("legis-num"))
    time_el = meta.find("action-time")

    positions = []
    for rv in root.iter("recorded-vote"):
        leg = rv.find("legislator")
        if leg is None or not leg.get("name-id"):
            continue
        positions.append(ParsedPosition(
            member_key=leg.get("name-id"),
            position=normalize_cast(rv.findtext("vote") or ""),
            name=(leg.text or "").strip() or None,
            party=leg.get("party"),
            state=leg.get("state"),
        ))

    return ParsedVote(
        chamber="house",
        congress=congress,
        session=int(re.match(r"\d+", text("session")).group()),
        vote_number=int(text("rollcall-num")),
        date=_parse_date(text("action-date"), time_el.get("time-etz") if time_el is not None else None),
        question=question,
        result=text("vote-result"),
        policy_id=normalize_policy_id(doc_type, number, congress),
        document_title=html.unescape(text("vote-desc")) or None,
        positions=positions,
        source="clerk.house.gov",
    )


async def fetch_vote(client: httpx.AsyncClient, year: int, vote_number: int) -> ParsedVote | None:
    url = vote_url(year, vote_number)
    try:
        res = await client.get(url)
    except httpx.HTTPError as e:
        raise HouseBlockedError(f"clerk.house.gov request failed: {e}") from e
    if res.status_code == 404:
        raise VoteNotFound(url)
    if res.status_code in (401, 403, 429):
        raise HouseBlockedError(f"clerk.house.gov returned {res.status_code} for {url}")
    res.raise_for_status()
    return parse_vote(res.content)


async def fetch_session(client: httpx.AsyncClient, congress: int, session: int, after: int = 0,
                        start: datetime | None = None, limit: int | None = None) -> list[ParsedVote]:
    """Fetch votes numbered above `after`. There's no index file, so count up until a 404.

    Stops early once `limit` votes dated on or after `start` have been found.
    """
    year = session_year(congress, session)
    votes: list[ParsedVote] = []
    next_number = after + 1
    while True:
        numbers = range(next_number, next_number + BATCH)
        results = await asyncio.gather(*(fetch_vote(client, year, n) for n in numbers), return_exceptions=True)
        done = False
        for result in results:
            if isinstance(result, VoteNotFound):
                done = True
                break
            if isinstance(result, Exception):
                raise result
            if result is not None:
                votes.append(result)
        in_window = [v for v in votes if start is None or v.date >= start]
        if done or (limit and len(in_window) >= limit):
            return votes
        next_number += BATCH
        await asyncio.sleep(0.3)  # be polite
