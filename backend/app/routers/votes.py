import re

from fastapi import APIRouter, Depends, HTTPException

from app.db.repository import Repository
from app.deps import get_repo
from app.models import MemberVote, Vote

router = APIRouter(tags=["votes"])


@router.get("/votes/{vote_id}", summary="One roll-call vote with every member's position")
async def get_vote(vote_id: str, repo: Repository = Depends(get_repo)):
    vote_id = vote_id.lower()
    if not re.fullmatch(r"[sh]-\d+-\d-\d{5}", vote_id):
        raise HTTPException(status_code=400, detail="voteId must look like s-119-1-00042 or h-119-1-00042")
    data = await repo.get_vote(vote_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Vote {vote_id} not found")
    members = sorted((MemberVote.model_validate(m) for m in data.get("members", [])),
                     key=lambda m: (m.state or "", m.district or 0, m.name or ""))
    member_votes = [m.model_dump(by_alias=True, mode="json") for m in members]
    return {
        **Vote.model_validate(data).model_dump(by_alias=True, mode="json"),
        "memberVotes": member_votes,
        "senatorVotes": member_votes,  # deprecated alias until the frontend moves to memberVotes
    }
