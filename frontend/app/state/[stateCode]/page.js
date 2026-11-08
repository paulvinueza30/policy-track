import Link from "next/link";
import { notFound } from "next/navigation";
import { DelegationExplorer, VoteCard } from "@/components/VoteLens";
import { ApiError, getSenatorVotes, getStateSenators } from "@/lib/api";
import { findState } from "@/lib/display";

export default async function StatePage({ params, searchParams }) {
  const { stateCode } = await params;
  const { senator } = await searchParams;
  const state = findState(stateCode);
  if (!state) notFound();

  const delegation = await getStateSenators(state.code).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    return error;
  });
  const senators = delegation instanceof ApiError ? null : delegation;
  const message = delegation instanceof ApiError ? {
    0: "VoteLens could not reach the FastAPI backend.",
    501: "This backend version does not provide Senate delegations.",
    503: "The backend is running, but its Senate data store is unavailable.",
  }[delegation.status] ?? "The delegation is unavailable right now. Try again later." : undefined;
  const active = senators?.find(({ bioguideId }) => bioguideId === senator) ?? senators?.[0];
  const votes = active ? await getSenatorVotes(active.bioguideId, { pageSize: 3 }).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    return null;
  }) : null;

  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/">United States Senate</Link></nav>
      <div className="intro compact">
        <p className="eyebrow">State delegation</p>
        <h1>{state.name}</h1>
      </div>
      <DelegationExplorer state={state} senators={senators} active={active} error={message} />
      {active && (
        <section className="section" id="voting-record">
          <div className="section-heading">
            <div><p className="eyebrow">Recent roll calls</p><h2>Voting Record: {active.name}</h2></div>
            <Link className="button" href={"/senator/" + encodeURIComponent(active.bioguideId)}>View full voting record →</Link>
          </div>
          {votes?.items.length ? (
            <div className="stack">{votes.items.slice(0, 3).map((vote) => <VoteCard key={vote.voteId} vote={vote} stateCode={state.code} />)}</div>
          ) : <p className="panel empty">{votes ? "No votes were returned for this senator." : "The voting record is unavailable right now."}</p>}
        </section>
      )}
    </main>
  );
}
