"""Load members, Senate and House votes, and policies for the 4-year window into Firestore.

Run from backend/:
    python -m scripts.ingest                                # incremental: only votes newer than last run
    python -m scripts.ingest --dry-run --limit 5            # fetch + parse, write nothing
    python -m scripts.ingest --chamber house --congress 119 --limit 10
    python -m scripts.ingest --source voteview              # skip senate.gov and the House Clerk
    python -m scripts.ingest --full                         # re-ingest every vote in the window

Votes come from senate.gov and the House Clerk; if a site blocks us, that session falls back to Voteview.
Firestore cost note: each Senate vote is ~101 writes and each House vote is ~436. See AGENTS.md §5.1.
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.date_window import window_end, window_start
from app.models import Member, MemberVote, Policy, Tally, Vote
from app.services import house, senate, voteview
from app.services.congress import CongressApiError, CongressClient, congress_gov_url, display_number
from app.services.http import make_client
from app.services.legislators import MemberIndex, fetch_index
from app.services.vote_types import ParsedVote, congress_for_year, split_policy_id
from app.states import STATE_CODES

CHAMBERS = ("senate", "house")
WRITE_CHUNK = {"senate": 4, "house": 1}  # votes per Firestore batch (max 500 writes)
PHOTO_URL = "https://unitedstates.github.io/images/congress/225x275/{bioguide}.jpg"
BLOCKED = (senate.SenateBlockedError, house.HouseBlockedError)


def log(msg: str) -> None:
    print(f"[ingest {datetime.now():%H:%M:%S}] {msg}", flush=True)


def sessions_in_window(start: datetime, end: datetime) -> list[tuple[int, int]]:
    return sorted({congress_for_year(y) for y in range(start.year, end.year + 1)})


async def senate_session(client: httpx.AsyncClient, congress: int, session: int, after: int,
                         start: datetime) -> list[ParsedVote]:
    menu = await senate.fetch_vote_menu(client, congress, session)
    wanted = [n for n, day in menu if n > after and (day is None or day >= start - timedelta(days=1))]
    log(f"senate.gov {congress}-{session}: {len(wanted)} votes to fetch")
    sem = asyncio.Semaphore(3)

    async def one(n: int) -> ParsedVote:
        async with sem:
            vote = await senate.fetch_vote(client, congress, session, n)
            await asyncio.sleep(0.3)  # be polite
            return vote

    return list(await asyncio.gather(*(one(n) for n in wanted)))


async def official_session(client: httpx.AsyncClient, chamber: str, congress: int, session: int, after: int,
                           start: datetime, limit: int | None) -> list[ParsedVote]:
    if chamber == "senate":
        return await senate_session(client, congress, session, after, start)
    return await house.fetch_session(client, congress, session, after, start, limit)


async def voteview_session(client: httpx.AsyncClient, chamber: str, congress: int, session: int,
                           cache: dict[tuple[str, int], list[ParsedVote]]) -> list[ParsedVote]:
    if (chamber, congress) not in cache:
        log(f"voteview: downloading {chamber}, {congress}th Congress")
        cache[(chamber, congress)] = await voteview.fetch_congress(client, chamber, congress)
    return [v for v in cache[(chamber, congress)] if v.session == session]


def document_label(policy_id: str | None) -> str | None:
    """"119-hr-6938" -> "H.R. 6938"."""
    if not policy_id:
        return None
    _, ptype, number = split_policy_id(policy_id)
    return display_number(ptype, number)


def district_at_vote(member: Member, chamber: str) -> int | None:
    role = member.for_chamber(chamber)
    return role.district if role else None


def to_records(pv: ParsedVote, index: MemberIndex) -> tuple[Vote, list[MemberVote], int]:
    members, unknown = [], 0
    for p in pv.positions:
        bioguide = index.resolve(p.member_key)
        if not bioguide:
            # Delegates count toward the tally on some House votes but aren't listed as members (AGENTS.md §2).
            unknown += p.state in STATE_CODES
            continue
        m = index.members[bioguide]
        members.append(MemberVote(vote_id=pv.vote_id, bioguide_id=bioguide, position=p.position,
                                  name=m.name, party=m.party, state=m.state,
                                  district=district_at_vote(m, pv.chamber)))
    vote = Vote(vote_id=pv.vote_id, chamber=pv.chamber, congress=pv.congress, session=pv.session,
                vote_number=pv.vote_number, date=pv.date, question=pv.question, result=pv.result,
                policy_id=pv.policy_id, tally=Tally(**pv.tally()),
                title=pv.document_short_title or pv.document_title,
                document_label=document_label(pv.policy_id))
    return vote, members, unknown


def minimal_policy(policy_id: str, title: str | None, short_title: str | None) -> Policy:
    congress, ptype, number = split_policy_id(policy_id)
    return Policy(policy_id=policy_id, congress=congress, type=ptype, number=number,
                  title=title or display_number(ptype, number), short_title=short_title,
                  congress_gov_url=congress_gov_url(congress, ptype, number))


async def add_photos(client: httpx.AsyncClient, members: list[Member], congress_api: CongressClient | None) -> None:
    """Fill photo_url. Not every member has a photo, so it can stay None (AGENTS.md §4.6)."""
    sem = asyncio.Semaphore(10)

    async def one(m: Member) -> None:
        url = PHOTO_URL.format(bioguide=m.bioguide_id)
        async with sem:
            try:
                if (await client.head(url)).status_code == 200:
                    m.photo_url = url
                elif congress_api:
                    m.photo_url = await congress_api.get_member_photo(m.bioguide_id)
            except (CongressApiError, httpx.HTTPError) as e:
                log(f"photo failed for {m.bioguide_id}: {e}")

    await asyncio.gather(*(one(m) for m in members))
    log(f"photos found for {sum(1 for m in members if m.photo_url)} of {len(members)} members")


async def run(args: argparse.Namespace) -> int:
    start, end = window_start(), window_end()
    log(f"window {start:%Y-%m-%d} -> {end:%Y-%m-%d}{' (dry run)' if args.dry_run else ''}")

    repo = None
    if not args.dry_run:
        from app.db import get_db
        from app.db.repository import Repository
        repo = Repository(get_db())

    chambers = CHAMBERS if args.chamber == "both" else (args.chamber,)

    async with make_client(timeout=60.0) as client:
        congress_api = CongressClient(client, settings.congress_api_key) if settings.congress_api_key else None
        if congress_api and not await congress_api.reachable():
            log("Congress.gov is not responding: skipping its photos and policy details for this run")
            congress_api = None
        elif not congress_api:
            log("CONGRESS_API_KEY not set: skipping Congress.gov photos and policy details")

        # 1. Members
        index = await fetch_index(client, start, end)
        members = list(index.members.values())
        by_chamber = {c: sum(1 for m in members if m.for_chamber(c)) for c in CHAMBERS}
        both = sum(1 for m in members if m.for_chamber("senate") and m.for_chamber("house"))
        log(f"{len(members)} members in the window: {by_chamber['senate']} senators, "
            f"{by_chamber['house']} representatives, {both} served in both")
        if not args.skip_photos:
            await add_photos(client, members, congress_api)
        if repo:
            await repo.write_members(members)

        # 2. Votes, chamber by chamber and session by session
        policy_titles: dict[str, tuple[str | None, str | None]] = {}
        vv_cache: dict[tuple[str, int], list[ParsedVote]] = {}
        total_votes = 0
        meta = (await repo.get_meta("ingest")) if repo else {}
        for chamber in chambers:
            for congress, session in sessions_in_window(start, end):
                if args.congress and congress != args.congress:
                    continue
                key = f"{chamber}-{congress}-{session}"
                after = 0 if args.full else meta.get(key, {}).get("lastVoteNumber", 0)

                parsed: list[ParsedVote] = []
                source = args.source
                if source in ("auto", "official"):
                    try:
                        parsed = await official_session(client, chamber, congress, session, after, start, args.limit)
                        source = "official"
                    except BLOCKED as e:
                        if args.source == "official":
                            log(f"{chamber} source blocked: {e}")
                            return 1
                        log(f"{chamber} source blocked ({e}); falling back to Voteview for {key}")
                        source = "voteview"
                if source == "voteview":
                    parsed = await voteview_session(client, chamber, congress, session, vv_cache)

                parsed = sorted((v for v in parsed if v.vote_number > after and start <= v.date <= end),
                                key=lambda v: v.vote_number)
                if args.limit:
                    parsed = parsed[:args.limit]
                log(f"{key}: {len(parsed)} new votes in window (source: {source})")

                chunk_size = WRITE_CHUNK[chamber]
                for i in range(0, len(parsed), chunk_size):
                    chunk = parsed[i:i + chunk_size]
                    records = []
                    for pv in chunk:
                        vote, vote_members, unknown = to_records(pv, index)
                        if unknown:
                            log(f"{pv.vote_id}: {unknown} voters not matched to a member")
                        records.append((vote, vote_members))
                        if pv.policy_id:
                            policy_titles.setdefault(pv.policy_id, (pv.document_title, pv.document_short_title))
                    if repo:
                        await repo.write_vote_batch(records)
                        await repo.set_meta("ingest", {key: {
                            "lastVoteNumber": chunk[-1].vote_number, "source": source,
                            "updatedAt": datetime.now(timezone.utc)}})
                    total_votes += len(chunk)
                if args.dry_run and parsed:
                    v, m, _ = to_records(parsed[-1], index)
                    log(f"sample {v.vote_id} {v.date:%Y-%m-%d} {v.question!r} -> {v.result!r} | {v.title!r} "
                        f"| {v.document_label} | tally {v.tally.model_dump()} | {len(m)} members")

        # 3. Policies
        ids = sorted(policy_titles)
        if repo and not args.refresh_policies:
            existing = await repo.existing_policy_ids(ids)
            ids = [p for p in ids if p not in existing]
        log(f"{len(ids)} policies to load")
        sem = asyncio.Semaphore(4)

        async def load(pid: str):
            title, short = policy_titles[pid]
            policy = minimal_policy(pid, title, short)
            if congress_api:
                async with sem:
                    try:
                        policy = await congress_api.get_policy(pid, fallback_title=title)
                        policy.short_title = policy.short_title or short
                    except (CongressApiError, httpx.HTTPError) as e:
                        log(f"Congress.gov failed for {pid}: {e}; saving basic info")
            if repo:
                await repo.write_policy(policy)
            return policy

        policies = await asyncio.gather(*(load(p) for p in ids))
        if args.dry_run and policies:
            p = policies[0]
            log(f"sample policy {p.policy_id}: {p.title[:80]!r}, summary: {bool(p.crs_summary)}")

    log(f"done: {total_votes} votes, {len(ids)} policies")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse only; write nothing")
    ap.add_argument("--chamber", choices=["both", "senate", "house"], default="both")
    ap.add_argument("--source", choices=["auto", "official", "voteview"], default="auto",
                    help="official = senate.gov and the House Clerk")
    ap.add_argument("--congress", type=int, help="only this Congress (e.g. 119)")
    ap.add_argument("--limit", type=int, help="max votes per chamber per session (for testing)")
    ap.add_argument("--full", action="store_true", help="ignore last run and re-ingest all votes")
    ap.add_argument("--refresh-policies", action="store_true", help="re-fetch policies already stored")
    ap.add_argument("--skip-photos", action="store_true")
    sys.exit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
