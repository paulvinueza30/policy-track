import Link from "next/link";
import { notFound } from "next/navigation";
import PolicySummary from "@/components/PolicySummary";
import { RollCall } from "@/components/VoteLens";
import { ApiError, getAiSummary, getPolicy, getPolicyArticles, getVote } from "@/lib/api";
import { externalHref, findState, formatDate, voteHref } from "@/lib/display";

export default async function PolicyPage({ params, searchParams }) {
  const { policyId } = await params;
  const { state: stateCode, vote: voteId } = await searchParams;
  const state = findState(stateCode);
  const policy = await getPolicy(policyId).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    if (error.status === 404) notFound();
    return null;
  });
  if (!policy) return <main className="frame page"><p className="panel empty">The policy details are unavailable right now.</p></main>;

  const selected = policy.votes.find((item) => item.voteId === voteId) ?? policy.votes[0];
  const [rollCall, articles] = await Promise.all([
    selected ? getVote(selected.voteId).catch((error) => {
      if (!(error instanceof ApiError)) throw error;
      return null;
    }) : null,
    getPolicyArticles(policy.policyId).catch((error) => {
      if (!(error instanceof ApiError)) throw error;
      return null;
    }),
  ]);

  const id = policy.policyId;
  const code = state?.code;
  async function summarize(previous, formData) {
    "use server";
    try {
      const summary = await getAiSummary({
        policyId: id,
        ...(code ? { stateCode: code } : {}),
        regenerate: formData.get("regenerate") === "true",
      });
      return { summary, error: null };
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      return { ...previous, error: "The AI summary is unavailable right now. Try again later." };
    }
  }

  const officialLink = externalHref(policy.congressGovUrl);
  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">U.S. Congress</Link>
        {state && <><span aria-hidden="true">›</span><Link href={"/state/" + code}>{state.name} Delegation</Link></>}
      </nav>
      <article className="panel policy stack">
        <header>
          <p className="eyebrow">Policy · {policy.congress}th Congress</p>
          <h1>{policy.title}</h1>
          {officialLink && <a href={officialLink}>View on Congress.gov →</a>}
          {policy.crsSummary && <p>{policy.crsSummary}</p>}
        </header>
        {policy.votes.length > 1 && (
          <section className="policy-section">
            <h2>Roll Calls on This Policy</h2>
            <ul className="roll-calls">
              {policy.votes.map((vote) => (
                <li key={vote.voteId}>
                  <Link href={voteHref(vote, code)} aria-current={vote.voteId === selected.voteId ? "page" : undefined}>{vote.question}</Link>
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
        <PolicySummary key={id + ":" + (code ?? "")} summarize={summarize} />
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
