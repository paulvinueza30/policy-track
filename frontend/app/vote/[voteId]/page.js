import Link from "next/link";
import { notFound } from "next/navigation";
import { RollCall } from "@/components/VoteLens";
import { ApiError, getVote } from "@/lib/api";
import { findState, voteHref, voteSubtitle, chamberLabel } from "@/lib/display";

export default async function VotePage({ params, searchParams }) {
  const { voteId } = await params;
  const { state: stateCode } = await searchParams;
  const state = findState(stateCode);
  const vote = await getVote(voteId).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    if (error.status === 404) notFound();
    return null;
  });
  if (!vote) return <main className="frame page"><p className="panel empty">This roll call is unavailable right now.</p></main>;

  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">U.S. Congress</Link>
        {state && <><span aria-hidden="true">›</span><Link href={"/state/" + state.code}>{state.name} Delegation</Link></>}
      </nav>
      <article className="panel policy stack">
        <header><p className="eyebrow">{chamberLabel(vote.chamber)} roll call</p><h1>{vote.title || vote.question}</h1><p className="vote-subtitle">{voteSubtitle(vote)}</p></header>
        <RollCall vote={vote} state={state} />
        {vote.policyId && <Link href={voteHref(vote, state?.code)}>View related policy →</Link>}
      </article>
    </main>
  );
}
