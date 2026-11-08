"""DeepSeek summary and single-policy Q&A (AGENTS.md §6)."""
import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from google.api_core.exceptions import GoogleAPIError
from pydantic import StringConstraints

from app.config import settings
from app.db.repository import Repository
from app.deps import get_repo
from app.models import AiSummary, Article, CamelModel, MemberVote, Policy, Vote
from app.routers.policies import _load_policy
from app.services.ai import AiUnavailable, answer_question, generate_summary, record_summary
from app.services.ai.prompts import PolicyContext, StateVote, newest_per_chamber, state_vote_point
from app.states import normalize_state

router = APIRouter(tags=["ai"])
logger = logging.getLogger(__name__)

CACHE_WRITE_SECONDS = 5.0
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class SummaryRequest(CamelModel):
    policy_id: str
    state_code: str | None = None
    regenerate: bool = False


class AskRequest(CamelModel):
    policy_id: str
    question: Question
    state_code: str | None = None


def _state(code: str | None) -> str | None:
    if not code:
        return None
    state = normalize_state(code)
    if not state:
        raise HTTPException(status_code=400, detail="stateCode must be one of the 50 state codes")
    return state


async def _votes(policy_id: str, repo: Repository) -> list[Vote]:
    return [Vote.model_validate(v) for v in await repo.policy_votes(policy_id)]


async def _state_votes(state: str | None, votes: list[Vote], repo: Repository) -> list[StateVote]:
    """The state's members on the newest roll call in each chamber."""
    if not state:
        return []
    out = []
    for vote in newest_per_chamber(votes):
        doc = await repo.get_vote(vote.vote_id) or {}
        members = [MemberVote.model_validate(m) for m in doc.get("members", []) if m.get("state") == state]
        if members:
            out.append(StateVote(vote=vote, members=members))
    return out


async def _context(policy: Policy, repo: Repository, state: str | None = None,
                   votes: list[Vote] | None = None) -> PolicyContext:
    votes = await _votes(policy.policy_id, repo) if votes is None else votes
    # Only articles that are already cached, so generating text never spends the GNews quota.
    articles = [Article.model_validate(a) for a in await repo.get_articles(policy.policy_id)]
    articles.sort(key=lambda a: a.published_at.timestamp() if a.published_at else 0, reverse=True)
    return PolicyContext(policy=policy, votes=votes, articles=articles, state_code=state,
                         state_votes=await _state_votes(state, votes, repo))


async def _save_quietly(summary: AiSummary, repo: Repository) -> None:
    """A failed cache write must not throw away a summary that took the GPU a minute to write."""
    try:
        await asyncio.wait_for(repo.save_ai_summary(summary), timeout=CACHE_WRITE_SECONDS)
    except (GoogleAPIError, TimeoutError) as e:
        logger.warning("Could not cache the AI summary for %s: %s", summary.policy_id, e)


@router.post("/ai/summary", summary="DeepSeek summary for a policy (cached; state votes come from the record)")
async def ai_summary(body: SummaryRequest, repo: Repository = Depends(get_repo)):
    policy_id = body.policy_id.lower()
    state = _state(body.state_code)
    policy = Policy.model_validate(await _load_policy(policy_id, repo))

    # The cached text is state-neutral, so one state's view is never served to another.
    cached = None
    if policy.crs_summary and settings.deepseek_model and not body.regenerate:
        cached = await repo.get_ai_summary(policy_id, settings.deepseek_model)
    if cached:
        summary = AiSummary.model_validate(cached)
    elif not policy.crs_summary:
        summary = record_summary(await _context(policy, repo))
    else:
        try:
            summary = await generate_summary(await _context(policy, repo))
        except AiUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        await _save_quietly(summary, repo)

    if state:
        points = [state_vote_point(state, s) for s in await _state_votes(state, await _votes(policy_id, repo), repo)]
        summary = summary.model_copy(update={"key_points": [*summary.key_points, *points]})
    return summary.model_dump(by_alias=True, mode="json")


@router.post("/ai/ask", summary="Answer a question about one policy from its grounded context")
async def ai_ask(body: AskRequest, repo: Repository = Depends(get_repo)):
    policy_id = body.policy_id.lower()
    state = _state(body.state_code)
    policy = Policy.model_validate(await _load_policy(policy_id, repo))
    try:
        answer = await answer_question(await _context(policy, repo, state), body.question)
    except AiUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return answer.model_dump(by_alias=True, mode="json")
