import Link from "next/link";
import { notFound } from "next/navigation";
import { DemoLabel, Portrait, VoteBadge, VoteCard } from "@/components/VoteLens";
import { demoPolicies, demoSenators, formatDemoDate } from "@/lib/demo";

const positions = ["Yea", "Nay", "Present", "Not Voting"];

export default async function SenatorPage({ params, searchParams }) {
  const { bioguideId } = await params;
  const { view, position, from, to } = await searchParams;
  const senatorIndex = demoSenators.findIndex(({ id }) => id === bioguideId);
  if (senatorIndex === -1) notFound();
  const senator = demoSenators[senatorIndex];
  const allVotes = view === "all";
  const selectedPosition = positions.includes(position) ? position : "";
  const start = typeof from === "string" && /^\d{4}-\d{2}-\d{2}$/.test(from) ? from : "";
  const end = typeof to === "string" && /^\d{4}-\d{2}-\d{2}$/.test(to) ? to : "";
  const filtered = demoPolicies.filter((policy) => (
    (!selectedPosition || policy.positions[senatorIndex] === selectedPosition) &&
    (!start || policy.date >= start) && (!end || policy.date <= end)
  ));

  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">United States Senate</Link><span aria-hidden="true">›</span><Link href="/state/TX">Texas Delegation</Link>
      </nav>
      <section className="panel profile">
        <Portrait senator={senator} />
        <div>
          <div className="inline-heading"><p className="eyebrow">U.S. Senate · Texas statewide</p><DemoLabel>Fictional profile</DemoLabel></div>
          <h1>{senator.name}</h1>
          <div className="profile-tags"><span className="party-tag">{senator.party}</span><span className="tag">{senator.seat}</span></div>
        </div>
        <a href="#recent-policies" className="button">View voting record ↓</a>
      </section>
      <section className="section" id="recent-policies">
        <div className="section-heading">
          <div><p className="eyebrow">Senator dossier</p><h2>Policy Votes</h2></div>
          <nav className="segments" aria-label="Vote record views">
            <Link href="?view=recent#recent-policies" aria-current={!allVotes ? "page" : undefined}>Three most recent</Link>
            <Link href="?view=all#recent-policies" aria-current={allVotes ? "page" : undefined}>All sample votes</Link>
          </nav>
        </div>
        {allVotes ? (
          <>
            <form action="#recent-policies" method="get" className="panel filters">
              <input type="hidden" name="view" value="all" />
              <label>Vote position<select name="position" defaultValue={selectedPosition}>
                <option value="">Any position</option>
                {positions.map((item) => <option key={item}>{item}</option>)}
              </select></label>
              <label>From<input type="date" name="from" defaultValue={start} /></label>
              <label>To<input type="date" name="to" defaultValue={end} /></label>
              <button className="button" type="submit">Filter votes</button>
            </form>
            {filtered.length ? (
              <ul className="panel roll-calls" aria-label="Sample roll calls">
                {filtered.map((policy) => (
                  <li key={policy.id}>
                    <div className="vote-meta"><VoteBadge position={policy.positions[senatorIndex]} /><DemoLabel>Demo vote</DemoLabel></div>
                    <Link href={"/policy/" + policy.id}>{policy.title}</Link>
                    <time dateTime={policy.date}>{formatDemoDate(policy.date)}</time>
                  </li>
                ))}
              </ul>
            ) : <p className="panel empty">No sample votes match these filters.</p>}
          </>
        ) : (
          <div className="stack">
            {demoPolicies.slice(0, 3).map((policy) => <VoteCard key={policy.id} policy={policy} senatorIndex={senatorIndex} expanded />)}
          </div>
        )}
      </section>
    </main>
  );
}
