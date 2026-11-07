"""Shared data model (AGENTS.md §5). JSON fields are camelCase via alias_generator."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Position = Literal["Yea", "Nay", "Present", "Not Voting"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Senator(CamelModel):
    bioguide_id: str
    lis_id: str | None = None
    name: str
    party: str
    state: str
    in_office_from: datetime | None = None
    in_office_to: datetime | None = None  # None if current
    photo_url: str | None = None


class Tally(CamelModel):
    yea: int = 0
    nay: int = 0
    present: int = 0
    not_voting: int = 0


class Vote(CamelModel):
    vote_id: str  # "119-1-00042"
    congress: int
    session: int
    vote_number: int
    date: datetime
    question: str
    result: str
    policy_id: str | None = None
    tally: Tally


class SenatorVote(CamelModel):
    vote_id: str
    bioguide_id: str
    position: Position
    # Optional display fields so the UI can list every senator without extra calls.
    name: str | None = None
    party: str | None = None
    state: str | None = None


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
    policy_id: str
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
