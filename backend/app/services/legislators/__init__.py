"""Senators in the window + LIS/ICPSR -> bioguide mapping (AGENTS.md §4.3).

Source: unitedstates/congress-legislators (public domain).
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

from app.models import Senator

BASE = "https://unitedstates.github.io/congress-legislators"
FILES = ("legislators-current.json", "legislators-historical.json")


@dataclass
class SenatorIndex:
    senators: dict[str, Senator]  # bioguide -> Senator
    lis_to_bioguide: dict[str, str]

    def resolve(self, member_key: str) -> str | None:
        """LIS id or bioguide id -> bioguide id of a senator in the window."""
        if member_key in self.senators:
            return member_key
        return self.lis_to_bioguide.get(member_key)


def _to_dt(d: str) -> datetime:
    return datetime.combine(date.fromisoformat(d), datetime.min.time(), tzinfo=timezone.utc)


def build_index(people: list[dict], start: datetime, end: datetime, now: datetime | None = None) -> SenatorIndex:
    """Keep everyone with a Senate term overlapping [start, end]."""
    now = now or datetime.now(timezone.utc)
    senators, lis_map = {}, {}
    for p in people:
        terms = [t for t in p.get("terms", []) if t.get("type") == "sen"
                 and _to_dt(t["start"]) <= end and _to_dt(t["end"]) >= start]
        if not terms:
            continue
        ids, name, last = p["id"], p["name"], terms[-1]
        bioguide = ids["bioguide"]
        term_end = _to_dt(last["end"])
        senators[bioguide] = Senator(
            bioguide_id=bioguide,
            lis_id=ids.get("lis"),
            name=name.get("official_full") or f"{name.get('first', '')} {name.get('last', '')}".strip(),
            party=last.get("party", ""),
            state=last["state"],
            in_office_from=_to_dt(terms[0]["start"]),
            in_office_to=None if term_end > now else term_end,
        )
        if ids.get("lis"):
            lis_map[ids["lis"]] = bioguide
    return SenatorIndex(senators=senators, lis_to_bioguide=lis_map)


async def fetch_index(client: httpx.AsyncClient, start: datetime, end: datetime) -> SenatorIndex:
    people = []
    for f in FILES:
        res = await client.get(f"{BASE}/{f}")
        res.raise_for_status()
        people.extend(res.json())
    return build_index(people, start, end)
