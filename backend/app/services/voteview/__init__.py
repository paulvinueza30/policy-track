"""Voteview (UCLA) Senate roll-call CSVs: fallback when senate.gov blocks us.

Files are per Congress:
  rollcalls: one row per vote (date, clerk vote number, bill number, question, result)
  votes:     one row per senator per vote (icpsr id + cast code)
  members:   icpsr id -> bioguide id, name, state
"""
import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.services.vote_types import ParsedPosition, ParsedVote, normalize_policy_id

BASE = "https://voteview.com/static/data/out"
EASTERN = ZoneInfo("America/New_York")

# Voteview cast codes -> official positions. Paired/announced votes are not cast votes.
CAST_CODES = {"1": "Yea", "6": "Nay", "7": "Present", "8": "Present",
              "2": "Not Voting", "3": "Not Voting", "4": "Not Voting", "5": "Not Voting", "9": "Not Voting"}
PARTY_CODES = {"100": "D", "200": "R", "328": "I"}


def csv_url(kind: str, congress: int) -> str:
    return f"{BASE}/{kind}/S{congress}_{kind}.csv"


def split_bill_number(bill: str) -> tuple[str, str] | tuple[None, None]:
    """"SJRES10" -> ("SJRES", "10"); "PN1129" -> ("PN", "1129"); "" -> (None, None)."""
    bill = (bill or "").strip().upper()
    i = 0
    while i < len(bill) and bill[i].isalpha():
        i += 1
    if i == 0 or i == len(bill):
        return None, None
    return bill[:i], bill[i:]


def parse_congress(rollcalls_csv: str, votes_csv: str, members_csv: str) -> list[ParsedVote]:
    """Combine the three Voteview CSVs for one Congress into ParsedVotes keyed by bioguide id."""
    members = {}
    for row in csv.DictReader(io.StringIO(members_csv)):
        if row["chamber"] == "Senate" and row.get("bioguide_id"):
            members[row["icpsr"]] = row

    casts: dict[str, list[ParsedPosition]] = {}
    for row in csv.DictReader(io.StringIO(votes_csv)):
        member = members.get(row["icpsr"])
        position = CAST_CODES.get(row["cast_code"])
        if not member or not position:  # code 0 = not a member at the time
            continue
        casts.setdefault(row["rollnumber"], []).append(ParsedPosition(
            member_key=member["bioguide_id"],
            position=position,
            state=member["state_abbrev"],
            party=PARTY_CODES.get(member["party_code"]),
        ))

    votes = []
    for row in csv.DictReader(io.StringIO(rollcalls_csv)):
        congress = int(row["congress"])
        doc_type, number = split_bill_number(row.get("bill_number", ""))
        day = datetime.strptime(row["date"], "%Y-%m-%d")
        votes.append(ParsedVote(
            congress=congress,
            session=int(row["session"]),
            vote_number=int(row["clerk_rollnumber"]),
            # Voteview has no time of day; use noon Eastern so the date never shifts.
            date=day.replace(hour=12, tzinfo=EASTERN),
            question=row.get("vote_question", ""),
            result=row.get("vote_result", ""),
            policy_id=normalize_policy_id(doc_type, number, congress),
            document_title=row.get("vote_desc") or None,
            positions=casts.get(row["rollnumber"], []),
            source="voteview",
        ))
    return votes


async def fetch_congress(client: httpx.AsyncClient, congress: int) -> list[ParsedVote]:
    texts = []
    for kind in ("rollcalls", "votes", "members"):
        res = await client.get(csv_url(kind, congress))
        res.raise_for_status()
        texts.append(res.text)
    return parse_congress(*texts)
