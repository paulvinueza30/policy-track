"""All Firestore reads and writes go through Repository (AGENTS.md §5.1).

Documents are stored with camelCase fields, matching the API (AGENTS.md §5).
"""
import asyncio
import hashlib
import re
from datetime import datetime

from google.cloud.firestore_v1.async_transaction import async_transactional
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud import firestore

from app.models import AiSummary, Article, Member, MemberVote, Policy, Vote

BATCH_LIMIT = 500


FOLLOW_TRANSACTION_ATTEMPTS = 15  # the default of 5 fails under a burst of clicks

# One lock per bucket keeps memory bounded. It removes contention within this server; the transaction covers others.
_account_locks = [asyncio.Lock() for _ in range(64)]


def _account_lock(user_id: str) -> asyncio.Lock:
    return _account_locks[int(hashlib.sha1(user_id.encode()).hexdigest(), 16) % len(_account_locks)]


class FollowLimitReached(Exception):
    pass


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
        return {"state": None, "district": None, "following": [], **(snap.to_dict() or {})}

    async def save_preferences(self, user_id: str, preferences: dict) -> None:
        """Without a "following" key the saved follows are left alone, so a stale tab can't undo a follow."""
        ref = self.db.collection("accounts").document(user_id)
        await ref.set(preferences, merge=False if "following" in preferences else list(preferences))

    async def add_following(self, user_id: str, member_id: str, limit: int) -> list[str]:
        """Atomic, so quick clicks and other tabs can't overwrite each other. Raises FollowLimitReached."""
        ref = self.db.collection("accounts").document(user_id)

        @async_transactional
        async def run(transaction) -> list[str]:
            snap = await ref.get(transaction=transaction)
            following = (snap.to_dict() or {}).get("following", []) if snap.exists else []
            if member_id in following:
                return following
            if len(following) >= limit:
                raise FollowLimitReached
            updated = [*following, member_id]
            transaction.set(ref, {"following": updated}, merge=True)
            return updated

        async with _account_lock(user_id):
            return await run(self.db.transaction(max_attempts=FOLLOW_TRANSACTION_ATTEMPTS))

    async def remove_following(self, user_id: str, member_id: str) -> list[str]:
        ref = self.db.collection("accounts").document(user_id)

        @async_transactional
        async def run(transaction) -> list[str]:
            snap = await ref.get(transaction=transaction)
            following = (snap.to_dict() or {}).get("following", []) if snap.exists else []
            if member_id not in following:
                return following
            updated = [m for m in following if m != member_id]
            transaction.set(ref, {"following": updated}, merge=True)
            return updated

        async with _account_lock(user_id):
            return await run(self.db.transaction(max_attempts=FOLLOW_TRANSACTION_ATTEMPTS))

    def _revocation_ref(self, user_id: str):
        """Hashed, so no account identifier is left behind after an account is deleted."""
        return self.db.collection("sessionRevocations").document(hashlib.sha256(user_id.encode()).hexdigest())

    async def sessions_valid_after(self, user_id: str) -> int:
        snap = await self._revocation_ref(user_id).get()
        return int((snap.to_dict() or {}).get("validAfter", 0)) if snap.exists else 0

    async def revoke_sessions(self, user_id: str, valid_after_ms: int) -> None:
        await self._revocation_ref(user_id).set({"validAfter": valid_after_ms})

    async def delete_account(self, user_id: str, valid_after_ms: int) -> None:
        """One atomic write, so an account is never deleted while its sessions still work."""
        batch = self.db.batch()
        batch.set(self._revocation_ref(user_id), {"validAfter": valid_after_ms})
        batch.delete(self.db.collection("accounts").document(user_id))
        await batch.commit()

    async def get_member_news(self, member_ids: list[str]) -> dict[str, dict]:
        refs = [self.db.collection("memberNews").document(m) for m in member_ids]
        return {snap.id: snap.to_dict() async for snap in self.db.get_all(refs) if snap.exists}

    async def save_member_news(self, member_id: str, data: dict) -> None:
        await self.db.collection("memberNews").document(member_id).set(data, merge=True)

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
