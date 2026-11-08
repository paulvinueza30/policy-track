"""Shared data model (AGENTS.md §5). JSON fields are camelCase via alias_generator."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Position = Literal["Yea", "Nay", "Present", "Not Voting"]
Chamber = Literal["senate", "house"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MemberRole(CamelModel):
    """One stretch of service: a chamber, state and (for the House) district."""
    chamber: Chamber
    state: str
    district: int | None = None
    party: str = ""
    start: datetime | None = Field(default=None, alias="from")
    end: datetime | None = Field(default=None, alias="to")  # None if current


class Member(CamelModel):
    bioguide_id: str
    lis_id: str | None = None  # senators only
    name: str
    party: str
    state: str
    chamber: Chamber  # current or most recent
    district: int | None = None  # 0 = at-large; None for senators
    in_office_from: datetime | None = None
    in_office_to: datetime | None = None  # None if current
    photo_url: str | None = None
    roles: list[MemberRole] = []

    def for_chamber(self, chamber: Chamber) -> "Member | None":
        """A copy describing this person's service in one chamber, or None if they never served there."""
        roles = [r for r in self.roles if r.chamber == chamber]
        if not roles:
            return None
        last = roles[-1]
        return self.model_copy(update={
            "chamber": chamber, "district": last.district, "party": last.party or self.party, "state": last.state,
            "in_office_from": roles[0].start, "in_office_to": last.end,
        })


class Tally(CamelModel):
    yea: int = 0
    nay: int = 0
    present: int = 0
    not_voting: int = 0


class Vote(CamelModel):
    vote_id: str  # "s-119-1-00042" or "h-119-1-00042"
    chamber: Chamber
    congress: int
    session: int
    vote_number: int
    date: datetime
    question: str
    result: str
    policy_id: str | None = None
    tally: Tally
    title: str | None = None  # what the vote was about, e.g. the bill title or nominee
    document_label: str | None = None  # e.g. "H.R. 6938" or "PN 373"


class MemberVote(CamelModel):
    vote_id: str
    bioguide_id: str
    position: Position
    # Optional display fields so the UI can list every senator without extra calls.
    name: str | None = None
    party: str | None = None
    state: str | None = None
    district: int | None = None


class LatestAction(CamelModel):
    date: str  # YYYY-MM-DD
    text: str


class Policy(CamelModel):
    policy_id: str  # "118-hr-2"
    congress: int
    type: str
    number: str
    title: str
    short_title: str | None = None
    crs_summary: str | None = None
    congress_gov_url: str | None = None
    latest_action: LatestAction | None = None


class Article(CamelModel):
    policy_id: str | None = None  # None for the home page feed
    title: str
    source: str
    url: str
    published_at: datetime | None = None
    description: str | None = None


class AiSummary(CamelModel):
    policy_id: str
    model: str
    generated_at: datetime
    summary: str
    key_points: list[str] = []
    sources: list[str] = []


class AiAnswer(CamelModel):
    policy_id: str
    model: str
    generated_at: datetime
    question: str
    answer: str
    sources: list[str] = []
