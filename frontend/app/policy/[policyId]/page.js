import Link from "next/link";
import { notFound } from "next/navigation";
import { DemoLabel, DemoSummary, VoteBadge } from "@/components/VoteLens";
import { demoPolicies, demoSenators, formatDemoDate } from "@/lib/demo";

export default async function PolicyPage({ params }) {
  const { policyId } = await params;
  const policy = demoPolicies.find(({ id }) => id === policyId);
  if (!policy) notFound();

  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">United States Senate</Link><span aria-hidden="true">›</span><Link href="/state/TX">Texas Delegation</Link>
      </nav>
      <article className="panel policy stack">
        <header>
          <div className="vote-meta"><DemoLabel>Demo vote</DemoLabel><span>{policy.topic}</span>
            <time dateTime={policy.date}>{formatDemoDate(policy.date)}</time></div>
          <h1>{policy.title}</h1>
          <p>Sample result · {policy.result}</p>
        </header>
        <section className="policy-section">
          <h2>Roll-Call Tally</h2>
          <dl className="tallies">
            {Object.entries(policy.tally).map(([position, count]) => (
              <div key={position}><dt>{position}</dt><dd>{count}</dd></div>
            ))}
          </dl>
        </section>
        <section className="policy-section">
          <h2>How the Texas Demo Delegation Voted</h2>
          <ul className="roll-calls policy-votes">
            {demoSenators.map((senator, index) => (
              <li key={senator.id}>
                <Link href={"/senator/" + senator.id}>{senator.name}</Link><VoteBadge position={policy.positions[index]} />
              </li>
            ))}
          </ul>
        </section>
        <section className="policy-section" id="ai-guide">
          <h2>AI Policy Guide</h2>
          <DemoSummary policy={policy} />
        </section>
        <section className="policy-section">
          <h2>Related Policy News</h2>
          <div className="inline-heading"><DemoLabel>Demo headline</DemoLabel><p>{policy.headline}</p></div>
        </section>
      </article>
    </main>
  );
}
