import Link from "next/link";
import { notFound } from "next/navigation";
import { RollCall } from "@/components/VoteLens";
import { ApiError, getVote } from "@/lib/api";
import { findState, voteHref, voteSubtitle, chamberLabel, stateHref, readNavigationContext } from "@/lib/display";

export default async function VotePage({ params, searchParams }) {
  const { voteId } = await params;
  const query = await searchParams;
  const { state: stateCode } = query;
  const state = findState(stateCode);
  const vote = await getVote(voteId).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    if (error.status === 404) notFound();
    return null;
  });
  if (!vote) return <main className="frame page"><p className="panel empty">This roll call is unavailable right now.</p></main>;

  const context = readNavigationContext(query, vote.chamber);
  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">U.S. Congress</Link>
        {state && <><span aria-hidden="true">›</span><Link href={stateHref(state.code, context.chamber, context.district, context.bioguideId)}>{state.name} Delegation</Link></>}
      {context.bioguideId && <><span aria-hidden="true">›</span><Link href={"/member/" + context.bioguideId + "?chamber=" + context.chamber}>Member profile</Link></>}
      </nav>
      <article className="panel policy stack">
        <header><p className="eyebrow">{chamberLabel(vote.chamber)} roll call</p><h1>{vote.title || vote.question}</h1><p className="vote-subtitle">{voteSubtitle(vote)}</p></header>
        <RollCall vote={vote} state={state} />
        {vote.policyId && <Link href={voteHref(vote, state?.code, context)}>View related policy →</Link>}
      </article>
    </main>
  );
}
