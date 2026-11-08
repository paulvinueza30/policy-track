import Link from "next/link";
import { notFound } from "next/navigation";
import RecordSummary from "@/components/RecordSummary";
import { RollCall } from "@/components/VoteLens";
import { ApiError, getPolicy, getPolicyArticles, getPolicySummary, getVote } from "@/lib/api";
import { externalHref, findState, formatDate, voteHref, chamberLabel, stateHref, readNavigationContext } from "@/lib/display";

export default async function PolicyPage({ params, searchParams }) {
  const { policyId } = await params;
  const query = await searchParams;
  const { state: stateCode, vote: voteId } = query;
  const state = findState(stateCode);
  const policy = await getPolicy(policyId).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    if (error.status === 404) notFound();
    return null;
  });
  if (!policy) return <main className="frame page"><p className="panel empty">The policy details are unavailable right now.</p></main>;

  const selected = policy.votes.find((item) => item.voteId === voteId) ?? policy.votes[0];
  const context = readNavigationContext(query, selected?.chamber ?? "senate");
  const [rollCall, articles, summary] = await Promise.all([
    selected ? getVote(selected.voteId).catch((error) => {
      if (!(error instanceof ApiError)) throw error;
      return null;
    }) : null,
    getPolicyArticles(policy.policyId).catch((error) => {
      if (!(error instanceof ApiError)) throw error;
      return null;
    }),
    getPolicySummary(policy.policyId, state?.code).catch((error) => {
      if (!(error instanceof ApiError)) throw error;
      return null;
    }),
  ]);

  const code = state?.code;
  const officialLink = externalHref(policy.congressGovUrl);
  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">U.S. Congress</Link>
        {state && <><span aria-hidden="true">›</span><Link href={stateHref(code, context.chamber, context.district, context.bioguideId)}>{state.name} Delegation</Link></>}
      {context.bioguideId && <><span aria-hidden="true">›</span><Link href={"/member/" + context.bioguideId + "?chamber=" + context.chamber}>Member profile</Link></>}
      </nav>
      <article className="panel policy stack">
        <header>
          <p className="eyebrow">Policy · {policy.congress}th Congress</p>
          <h1>{policy.title}</h1>
          {officialLink && <a href={officialLink}>View on Congress.gov →</a>}
        </header>
        <RecordSummary summary={summary} officialText={policy.crsSummary} />
        {policy.votes.length > 0 && (
          <section className="policy-section">
            <h2>Votes in Congress</h2>
            <ul className="roll-calls">
              {policy.votes.map((vote) => (
                <li key={vote.voteId}>
                  <Link href={voteHref(vote, code, context)} aria-current={vote.voteId === selected.voteId ? "page" : undefined}><span className="tag">{chamberLabel(vote.chamber)}</span> {vote.question}</Link>
                  <time dateTime={vote.date}>{formatDate(vote.date)}</time>
                </li>
              ))}
            </ul>
          </section>
        )}
        {selected && (
          <>
            <p>{selected.question}</p>
            <RollCall vote={rollCall ?? selected} state={state} positionsUnavailable={!rollCall} />
          </>
        )}
        <section className="policy-section" id="news">
          <h2>Related Policy News</h2>
          {articles === null ? <p>Related news is unavailable right now.</p>
            : articles.length ? (
              <div className="news-grid">
                {articles.map((item) => {
                  const url = externalHref(item.url);
                  return (
                    <article className="panel news-card" key={item.url}>
                      <p className="eyebrow">{item.source}</p>
                      <h3>{url ? <a href={url}>{item.title}</a> : item.title}</h3>
                      {item.publishedAt && <time dateTime={item.publishedAt}>{formatDate(item.publishedAt)}</time>}
                      {item.description && <p>{item.description}</p>}
                    </article>
                  );
                })}
              </div>
            ) : <p>No related articles were found.</p>}
        </section>
      </article>
    </main>
  );
}
