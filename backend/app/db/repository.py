"""All Firestore reads and writes go through Repository (AGENTS.md §5.1).

Documents are stored with camelCase fields, matching the API (AGENTS.md §5).
"""
import hashlib
import re
from datetime import datetime

from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud import firestore

from app.models import AiSummary, Article, Member, MemberVote, Policy, Vote

BATCH_LIMIT = 500


def article_doc_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:20]


def ai_summary_doc_id(policy_id: str, model: str) -> str:
    return re.sub(r"[:/]", "_", f"{policy_id}__{model}")


def _dump(model) -> dict:
    return model.model_dump(by_alias=True)


class Repository:
    def __init__(self, db: firestore.AsyncClient):
        self.db = db

    # ---------- reads (API) ----------

    async def members_by_state(self, state: str) -> list[dict]:
        q = self.db.collection("members").where(filter=FieldFilter("state", "==", state))
        return [d.to_dict() async for d in q.stream()]

    async def get_member(self, bioguide_id: str) -> dict | None:
        snap = await self.db.collection("members").document(bioguide_id).get()
        return snap.to_dict() if snap.exists else None

    async def member_votes(self, bioguide_id: str, start: datetime, end: datetime, chamber: str | None,
                           position: str | None, page: int, page_size: int) -> tuple[list[dict], int]:
        q = self.db.collection("members").document(bioguide_id).collection("votes")
        if chamber:
            q = q.where(filter=FieldFilter("chamber", "==", chamber))
        if position:
            q = q.where(filter=FieldFilter("position", "==", position))
        q = q.where(filter=FieldFilter("date", ">=", start)).where(filter=FieldFilter("date", "<=", end))
        total = (await q.count().get())[0][0].value
        page_q = (q.order_by("date", direction=firestore.Query.DESCENDING)
                   .order_by("voteNumber", direction=firestore.Query.DESCENDING)
                   .offset((page - 1) * page_size).limit(page_size))
        return [d.to_dict() async for d in page_q.stream()], int(total)

    async def get_vote(self, vote_id: str) -> dict | None:
        snap = await self.db.collection("votes").document(vote_id).get()
        return snap.to_dict() if snap.exists else None

    async def get_policy(self, policy_id: str) -> dict | None:
        snap = await self.db.collection("policies").document(policy_id).get()
        return snap.to_dict() if snap.exists else None

    async def policy_votes(self, policy_id: str) -> list[dict]:
        q = (self.db.collection("votes").where(filter=FieldFilter("policyId", "==", policy_id))
             .order_by("date", direction=firestore.Query.DESCENDING)
             .order_by("voteNumber", direction=firestore.Query.DESCENDING))
        # Votes saved before the House was added have no chamber and use old IDs.
        return [doc for d in [d async for d in q.stream()] if "chamber" in (doc := d.to_dict())]

    async def get_articles(self, policy_id: str) -> list[dict]:
        q = self.db.collection("policies").document(policy_id).collection("articles")
        return [d.to_dict() async for d in q.stream()]

    async def replace_articles(self, policy_id: str, articles: list[Article], fetched_at: datetime) -> None:
        policy_ref = self.db.collection("policies").document(policy_id)
        col = policy_ref.collection("articles")
        batch = self.db.batch()
        async for old in col.stream():
            batch.delete(old.reference)
        for a in articles:
            batch.set(col.document(article_doc_id(a.url)), {**_dump(a), "fetchedAt": fetched_at})
        batch.set(policy_ref, {"articlesFetchedAt": fetched_at}, merge=True)
        await batch.commit()

    async def touch_articles(self, policy_id: str, fetched_at: datetime) -> None:
        await self.db.collection("policies").document(policy_id).set({"articlesFetchedAt": fetched_at}, merge=True)

    async def get_ai_summary(self, policy_id: str, model: str) -> dict | None:
        snap = await self.db.collection("aiSummaries").document(ai_summary_doc_id(policy_id, model)).get()
        return snap.to_dict() if snap.exists else None

    async def save_ai_summary(self, summary: AiSummary) -> None:
        await self.db.collection("aiSummaries").document(
            ai_summary_doc_id(summary.policy_id, summary.model)).set(_dump(summary))

    # ---------- writes (ingest) ----------

    async def write_members(self, members: list[Member]) -> None:
        for i in range(0, len(members), BATCH_LIMIT):
            batch = self.db.batch()
            for m in members[i:i + BATCH_LIMIT]:
                batch.set(self.db.collection("members").document(m.bioguide_id), _dump(m), merge=True)
            await batch.commit()

    async def write_vote_batch(self, items: list[tuple[Vote, list[MemberVote]]]) -> None:
        """Write votes + each member's copy: 1 + ~100 writes (Senate) or 1 + ~435 (House) per vote."""
        batch, ops = self.db.batch(), 0
        for vote, members in items:
            if ops + 1 + len(members) > BATCH_LIMIT:
                await batch.commit()
                batch, ops = self.db.batch(), 0
            vote_data = _dump(vote)
            batch.set(self.db.collection("votes").document(vote.vote_id), {
                **vote_data,
                "positions": {m.bioguide_id: m.position for m in members},
                "members": [_dump(m) for m in members],
            })
            for m in members:
                ref = (self.db.collection("members").document(m.bioguide_id)
                       .collection("votes").document(vote.vote_id))
                batch.set(ref, {**vote_data, "position": m.position})
            ops += 1 + len(members)
        if ops:
            await batch.commit()

    async def existing_policy_ids(self, policy_ids: list[str]) -> set[str]:
        refs = [self.db.collection("policies").document(p) for p in policy_ids]
        found = set()
        for i in range(0, len(refs), 100):
            async for snap in self.db.get_all(refs[i:i + 100]):
                if snap.exists:
                    found.add(snap.id)
        return found

    async def write_policy(self, policy: Policy) -> None:
        await self.db.collection("policies").document(policy.policy_id).set(_dump(policy), merge=True)

    async def get_meta(self, key: str) -> dict:
        snap = await self.db.collection("meta").document(key).get()
        return snap.to_dict() or {} if snap.exists else {}

    async def set_meta(self, key: str, data: dict) -> None:
        await self.db.collection("meta").document(key).set(data, merge=True)

    # Private preferences are always addressed by the verified Google subject.
    async def get_preferences(self, user_id: str) -> dict:
        snap = await self.db.collection("accounts").document(user_id).get()
        return (snap.to_dict() or {}) if snap.exists else {"state": None, "district": None, "following": []}

    async def save_preferences(self, user_id: str, preferences: dict) -> None:
        await self.db.collection("accounts").document(user_id).set(preferences)

    async def feed_votes(self, member_ids: list[str] | None, start: datetime, end: datetime, count: int) -> list[dict]:
        import asyncio
        async def read(collection):
            query = (collection.where(filter=FieldFilter("date", ">=", start))
                     .where(filter=FieldFilter("date", "<=", end))
                     .order_by("date", direction=firestore.Query.DESCENDING)
                     .order_by("voteNumber", direction=firestore.Query.DESCENDING).limit(count))
            return [d.to_dict() async for d in query.stream()]
        if member_ids is None:
            groups = [await read(self.db.collection("votes"))]
        else:
            groups = await asyncio.gather(*(read(self.db.collection("members").document(mid).collection("votes")) for mid in member_ids[:20]))
        votes = {v["voteId"]: v for group in groups for v in group if "chamber" in v}
        return sorted(votes.values(), key=lambda v: (v["date"], v["voteNumber"], v["voteId"]), reverse=True)[:count]
