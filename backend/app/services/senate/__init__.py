"""senate.gov roll-call vote XML: fetch + parse (AGENTS.md §4.2).

senate.gov sometimes blocks automated requests (HTTP 403). Callers should catch
SenateBlockedError and fall back to Voteview (app.services.voteview).
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.services.vote_types import ParsedPosition, ParsedVote, normalize_policy_id

BASE = "https://www.senate.gov/legislative/LIS"
EASTERN = ZoneInfo("America/New_York")

_CAST_MAP = {
    "yea": "Yea",
    "nay": "Nay",
    "present": "Present",
    "not voting": "Not Voting",
    # Impeachment trial wording, recorded as the matching yes/no position.
    "guilty": "Yea",
    "not guilty": "Nay",
}


class SenateBlockedError(Exception):
    """senate.gov refused the request or returned something that isn't vote XML."""


def menu_url(congress: int, session: int) -> str:
    return f"{BASE}/roll_call_lists/vote_menu_{congress}_{session}.xml"


def vote_url(congress: int, session: int, vote_number: int) -> str:
    return (f"{BASE}/roll_call_votes/vote{congress}{session}/"
            f"vote_{congress}_{session}_{vote_number:05d}.xml")


def _text(el: ET.Element | None, path: str) -> str:
    found = el.find(path) if el is not None else None
    return (found.text or "").strip() if found is not None and found.text else ""


def _parse_xml(content: bytes) -> ET.Element:
    try:
        return ET.fromstring(content)
    except ET.ParseError as e:  # e.g. an HTML "Unauthorized" page
        raise SenateBlockedError(f"senate.gov did not return XML: {e}") from e


def normalize_cast(cast: str) -> str:
    c = cast.strip().lower()
    if c in _CAST_MAP:
        return _CAST_MAP[c]
    if c.startswith("present"):  # e.g. "Present, Giving Live Pair"
        return "Present"
    return "Not Voting"


def parse_vote_date(raw: str) -> datetime:
    """"January 3, 2023,  03:21 PM" -> aware datetime (US Eastern)."""
    clean = re.sub(r"\s+", " ", raw.strip())
    for fmt in ("%B %d, %Y, %I:%M %p", "%B %d, %Y"):
        try:
            return datetime.strptime(clean, fmt).replace(tzinfo=EASTERN)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized senate.gov vote date: {raw!r}")


def parse_vote_menu(content: bytes) -> list[tuple[int, datetime | None]]:
    """Vote menu XML -> [(vote number, vote day or None)] for that session, oldest first."""
    root = _parse_xml(content)
    if root.tag != "vote_summary":
        raise SenateBlockedError(f"Unexpected vote menu root <{root.tag}>")
    year = _text(root, "congress_year")
    out = []
    for v in root.iter("vote"):
        num = _text(v, "vote_number")
        if not num:
            continue
        day = None
        try:  # menu dates look like "03-Jan"
            day = datetime.strptime(f"{_text(v, 'vote_date')}-{year}", "%d-%b-%Y").replace(tzinfo=EASTERN)
        except ValueError:
            pass
        out.append((int(num), day))
    return sorted(out)


def parse_vote(content: bytes) -> ParsedVote:
    """Single roll-call vote XML -> ParsedVote (positions keyed by LIS member id)."""
    root = _parse_xml(content)
    if root.tag != "roll_call_vote":
        raise SenateBlockedError(f"Unexpected vote root <{root.tag}>")

    congress = int(_text(root, "congress"))
    doc = root.find("document")
    doc_congress = _text(doc, "document_congress") or str(congress)
    policy_id = normalize_policy_id(_text(doc, "document_type"), _text(doc, "document_number"), doc_congress)

    positions = []
    for m in root.iter("member"):
        lis = _text(m, "lis_member_id")
        if not lis:
            continue
        positions.append(ParsedPosition(
            member_key=lis,
            position=normalize_cast(_text(m, "vote_cast")),
            name=" ".join(filter(None, [_text(m, "first_name"), _text(m, "last_name")])) or None,
            party=_text(m, "party") or None,
            state=_text(m, "state") or None,
        ))

    return ParsedVote(
        congress=congress,
        session=int(_text(root, "session")),
        vote_number=int(_text(root, "vote_number")),
        date=parse_vote_date(_text(root, "vote_date")),
        question=_text(root, "vote_question_text") or _text(root, "question"),
        result=_text(root, "vote_result_text") or _text(root, "vote_result"),
        policy_id=policy_id,
        document_title=_text(doc, "document_title") or _text(root, "vote_title") or None,
        document_short_title=_text(doc, "document_short_title") or None,
        positions=positions,
        source="senate.gov",
    )


async def _get(client: httpx.AsyncClient, url: str) -> bytes:
    try:
        res = await client.get(url)
    except httpx.HTTPError as e:
        raise SenateBlockedError(f"senate.gov request failed: {e}") from e
    if res.status_code in (401, 403, 429):
        raise SenateBlockedError(f"senate.gov returned {res.status_code} for {url}")
    res.raise_for_status()
    return res.content


async def fetch_vote_menu(client: httpx.AsyncClient, congress: int, session: int) -> list[tuple[int, datetime | None]]:
    return parse_vote_menu(await _get(client, menu_url(congress, session)))


async def fetch_vote(client: httpx.AsyncClient, congress: int, session: int, vote_number: int) -> ParsedVote:
    return parse_vote(await _get(client, vote_url(congress, session, vote_number)))
