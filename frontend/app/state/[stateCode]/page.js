import Link from "next/link";
import { notFound } from "next/navigation";
import { DelegationExplorer, VoteCard } from "@/components/VoteLens";
import { ApiError, getMemberVotes, getStateMembers } from "@/lib/api";
import { findState, memberHref } from "@/lib/display";

export default async function StatePage({ params, searchParams }) {
  const { stateCode } = await params;
  const query = await searchParams;
  const chamber = query.chamber === "house" ? "house" : "senate";
  const memberId = query.member ?? query.senator;
  const atLarge = ["AK", "DE", "ND", "SD", "VT", "WY"].includes(stateCode.toUpperCase());
  const requestedDistrict = typeof query.district === "string" && /^\d{1,2}$/.test(query.district) ? Number(query.district) : null;
  const district = chamber === "house" ? (atLarge ? 0 : requestedDistrict) : null;
  const state = findState(stateCode);
  if (!state) notFound();

  const delegation = await getStateMembers(state.code, chamber).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    return error;
  });
  const members = delegation instanceof ApiError ? null : delegation;
  const message = delegation instanceof ApiError ? {
    0: "RealNews could not reach the FastAPI backend.",
    501: "This backend version does not provide member delegations.",
    503: "The backend is running, but its member data store is unavailable.",
  }[delegation.status] ?? "The delegation is unavailable right now. Try again later." : undefined;
  const visible = chamber === "house" ? members?.filter(member => member.district === district) : members;
  const active = visible?.find(({ bioguideId }) => bioguideId === memberId) ?? visible?.find(member => !member.inOfficeTo) ?? visible?.[0];
  const votes = active ? await getMemberVotes(active.bioguideId, { pageSize: 3, chamber }).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    return null;
  }) : null;

  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/">U.S. Congress</Link></nav>
      <div className="intro compact">
        <p className="eyebrow">State delegation</p>
        <h1>{state.name}</h1>
      </div>
      <DelegationExplorer state={state} members={members} active={active} error={message} chamber={chamber} district={district} />
      {active && (
        <section className="section" id="voting-record">
          <div className="section-heading">
            <div><p className="eyebrow">Recent roll calls</p><h2>Voting Record: {active.name}</h2></div>
            <Link className="button" href={memberHref(active)}>View full voting record →</Link>
          </div>
          {votes?.items.length ? (
            <div className="stack">{votes.items.slice(0, 3).map((vote) => <VoteCard key={vote.voteId} vote={vote} stateCode={state.code} member={active} />)}</div>
          ) : <p className="panel empty">{votes ? "No votes were returned for this member." : "The voting record is unavailable right now."}</p>}
        </section>
      )}
    </main>
  );
}
