"""Source-neutral vote records. senate.gov and Voteview parsers both produce these."""
import re
from dataclasses import dataclass, field
from datetime import datetime

BILL_TYPES = {"s", "hr", "sres", "hres", "sjres", "hjres", "sconres", "hconres"}
POSITIONS = ("Yea", "Nay", "Present", "Not Voting")


@dataclass
class ParsedPosition:
    member_key: str  # LIS id (senate.gov) or bioguide id (House Clerk, Voteview)
    position: str  # one of POSITIONS
    name: str | None = None
    party: str | None = None
    state: str | None = None


@dataclass
class ParsedVote:
    chamber: str  # "senate" or "house"
    congress: int
    session: int
    vote_number: int
    date: datetime
    question: str
    result: str
    policy_id: str | None
    document_title: str | None = None
    document_short_title: str | None = None
    positions: list[ParsedPosition] = field(default_factory=list)
    source: str = ""  # "senate.gov" or "voteview"

    @property
    def vote_id(self) -> str:
        return make_vote_id(self.chamber, self.congress, self.session, self.vote_number)

    def tally(self) -> dict[str, int]:
        counts = {p: 0 for p in POSITIONS}
        for p in self.positions:
            counts[p.position] += 1
        return {"yea": counts["Yea"], "nay": counts["Nay"],
                "present": counts["Present"], "notVoting": counts["Not Voting"]}


def make_vote_id(chamber: str, congress: int, session: int, vote_number: int) -> str:
    """Vote numbers restart per chamber and session: ("house", 119, 1, 42) -> "h-119-1-00042"."""
    return f"{chamber[0]}-{congress}-{session}-{vote_number:05d}"


def normalize_policy_id(doc_type: str | None, number: str | None, congress: int | str) -> str | None:
    """("H.R.", "2", 118) -> "118-hr-2"; ("PN", "123", 119) -> "119-pn-123".

    Returns None for votes with no bill/nomination (procedural votes, treaties, etc.).
    """
    if not doc_type or not number:
        return None
    t = re.sub(r"[^a-z]", "", doc_type.lower())
    num = re.sub(r"\s+", "", number).lower()
    if t in BILL_TYPES and num.isdigit():
        return f"{congress}-{t}-{int(num)}"
    if t == "pn" and re.fullmatch(r"\d+(-\d+)?", num):
        return f"{congress}-pn-{num}"
    return None


def split_policy_id(policy_id: str) -> tuple[int, str, str]:
    """"118-hr-2" -> (118, "hr", "2"). Raises ValueError if malformed."""
    m = re.fullmatch(r"(\d+)-([a-z]+)-(\d+(?:-\d+)?)", policy_id)
    if not m or (m.group(2) not in BILL_TYPES and m.group(2) != "pn"):
        raise ValueError(f"Invalid policyId: {policy_id}")
    return int(m.group(1)), m.group(2), m.group(3)


def congress_for_year(year: int) -> tuple[int, int]:
    """Calendar year -> (congress, session). 2025 -> (119, 1)."""
    congress = (year - 1789) // 2 + 1
    session = 1 if year % 2 == 1 else 2
    return congress, session


def session_year(congress: int, session: int) -> int:
    """(119, 1) -> 2025."""
    return 1789 + (congress - 1) * 2 + session - 1
