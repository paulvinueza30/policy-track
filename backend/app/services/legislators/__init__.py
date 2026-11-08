"""Members in the window + LIS -> bioguide mapping (AGENTS.md §4.3).

Source: unitedstates/congress-legislators (public domain).
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

from app.models import Member, MemberRole
from app.states import STATE_CODES

BASE = "https://unitedstates.github.io/congress-legislators"
FILES = ("legislators-current.json", "legislators-historical.json")
CHAMBERS = {"sen": "senate", "rep": "house"}


@dataclass
class MemberIndex:
    members: dict[str, Member]  # bioguide -> Member
    lis_to_bioguide: dict[str, str]

    def resolve(self, member_key: str) -> str | None:
        """LIS id or bioguide id -> bioguide id of a member in the window."""
        if member_key in self.members:
            return member_key
        return self.lis_to_bioguide.get(member_key)


def _to_dt(d: str) -> datetime:
    return datetime.combine(date.fromisoformat(d), datetime.min.time(), tzinfo=timezone.utc)


def _build_roles(terms: list[dict], now: datetime) -> list[MemberRole]:
    """Merge back-to-back terms in the same seat into one role."""
    roles: list[MemberRole] = []
    for t in terms:
        chamber, district = CHAMBERS[t["type"]], t.get("district") if t["type"] == "rep" else None
        start, end = _to_dt(t["start"]), _to_dt(t["end"])
        end_value = None if end > now else end
        previous = roles[-1] if roles else None
        if previous and (previous.chamber, previous.state, previous.district) == (chamber, t["state"], district):
            previous.end = end_value
            previous.party = t.get("party", previous.party)
        else:
            roles.append(MemberRole(chamber=chamber, state=t["state"], district=district,
                                    party=t.get("party", ""), start=start, end=end_value))
    return roles


def build_index(people: list[dict], start: datetime, end: datetime, now: datetime | None = None) -> MemberIndex:
    """Keep voting members of the 50 states with a term overlapping [start, end]."""
    now = now or datetime.now(timezone.utc)
    members, lis_map = {}, {}
    for p in people:
        terms = [t for t in p.get("terms", []) if t.get("type") in CHAMBERS and t.get("state") in STATE_CODES
                 and _to_dt(t["start"]) <= end and _to_dt(t["end"]) >= start]
        if not terms:
            continue
        ids, name = p["id"], p["name"]
        bioguide = ids["bioguide"]
        roles = _build_roles(terms, now)
        last = roles[-1]
        members[bioguide] = Member(
            bioguide_id=bioguide,
            lis_id=ids.get("lis"),
            name=name.get("official_full") or f"{name.get('first', '')} {name.get('last', '')}".strip(),
            party=last.party,
            state=last.state,
            chamber=last.chamber,
            district=last.district,
            in_office_from=roles[0].start,
            in_office_to=last.end,
            roles=roles,
        )
        if ids.get("lis"):
            lis_map[ids["lis"]] = bioguide
    return MemberIndex(members=members, lis_to_bioguide=lis_map)


async def fetch_index(client: httpx.AsyncClient, start: datetime, end: datetime) -> MemberIndex:
    people = []
    for f in FILES:
        res = await client.get(f"{BASE}/{f}")
        res.raise_for_status()
        people.extend(res.json())
    return build_index(people, start, end)
