import Image from "next/image";
import Link from "next/link";
import SenateMap from "./SenateMap";
import StatePicker from "./StatePicker";
import states from "@/lib/states.json";
import { demoPolicies, demoSenators, formatDemoDate, getDemoDelegation } from "@/lib/demo";

const stateOptions = states.map(({ code, name }) => ({ code, name }));

export function DemoLabel({ children = "Demo content" }) {
  return <span className="demo-label">{children}</span>;
}

export function Portrait({ senator }) {
  return (
    <span className="portrait" aria-hidden="true">
      {senator.portrait
        ? <Image src={senator.portrait} alt="" width={112} height={112} />
        : senator.initials}
    </span>
  );
}

export function DelegationExplorer({ stateCode, senatorId }) {
  const selectedState = states.find(({ code }) => code === stateCode);
  const senators = getDemoDelegation(selectedState);
  const active = senators.find(({ id }) => id === senatorId) ?? senators[0];

  return (
    <section className="panel explorer section" id="explore" aria-labelledby="explore-title">
      <div className="section-heading">
        <div>
          <h2 id="explore-title">Explore by United States Senate Map</h2>
          <p>Select a state to explore its U.S. Senate delegation.</p>
        </div>
        <span className="tag">2 U.S. Senators per state</span>
      </div>
      <div className="explore-grid">
        <SenateMap key={stateCode} states={states} stateCode={stateCode} />
        <div className="delegation" id="delegation">
          <StatePicker key={stateCode} options={stateOptions} stateCode={stateCode} />
          <div className="delegation-heading">
            <h3>{selectedState.name} Senate Delegation</h3>
            <DemoLabel>Fictional profiles</DemoLabel>
          </div>
          <ul className="senator-list">
            {senators.map((senator) => (
              <li key={senator.id}>
                <Link className="senator-link" href={`/state/${stateCode}?senator=${senator.id}#delegation`}
                  aria-current={active.id === senator.id ? "true" : undefined}>
                  <Portrait senator={senator} />
                  <span><strong>{senator.name}</strong><small>{senator.seat}{senator.party && " · " + senator.party}</small></span>
                  <span className="arrow" aria-hidden="true">{active.id === senator.id ? "✓" : "→"}</span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="active-senator">
            <p className="eyebrow">Selected senator · Demo profile</p>
            <h3>{active.name}</h3>
            <p>{selectedState.name} statewide · {active.seat}</p>
            <Link className="button" href={"/senator/" + active.id}>Open senator dossier →</Link>
          </div>
        </div>
      </div>
    </section>
  );
}

export function VoteBadge({ position }) {
  const tone = position === "Yea" ? "yea" : position === "Nay" ? "nay" : "neutral";
  return <span className={"vote-badge " + tone}>{position}</span>;
}

export function DemoSummary({ policy }) {
  return (
    <div className="summary">
      <div className="inline-heading"><h3>AI Plain-English Summary</h3><DemoLabel>Demo AI response</DemoLabel></div>
      <p>{policy.summary}</p>
      <small>Source for this example · VoteLens fictional policy and vote record</small>
    </div>
  );
}

export function VoteCard({ policy, senatorIndex, expanded = false }) {
  return (
    <article className="panel vote-card">
      <div className="vote-meta">
        <VoteBadge position={policy.positions[senatorIndex]} />
        <DemoLabel>Demo vote</DemoLabel>
        <span>{policy.topic}</span>
        <time dateTime={policy.date}>{formatDemoDate(policy.date)}</time>
      </div>
      <h3>{policy.title}</h3>
      {expanded && <DemoSummary policy={policy} />}
      <div className="vote-footer">
        <span>Sample result · {policy.result}</span>
        <Link href={"/policy/" + policy.id}>View policy &amp; AI guide →</Link>
      </div>
    </article>
  );
}

export function FeaturedVoting({ senatorId }) {
  const senatorIndex = Math.max(0, demoSenators.findIndex(({ id }) => id === senatorId));
  const senator = demoSenators[senatorIndex];
  return (
    <section className="section" id="voting-record">
      <div className="section-heading">
        <div><p className="eyebrow">Texas · Sample roll calls</p><h2>Voting Record: {senator.name}</h2></div>
        <Link className="button" href={"/senator/" + senator.id}>View full voting record →</Link>
      </div>
      <div className="stack">
        {demoPolicies.map((policy) => <VoteCard key={policy.id} policy={policy} senatorIndex={senatorIndex} />)}
      </div>
    </section>
  );
}

export function DemoNews() {
  return (
    <section className="section" id="news">
      <div className="section-heading"><div><p className="eyebrow">Policy coverage</p><h2>Trending Policy News</h2></div></div>
      <div className="news-grid">
        {demoPolicies.map((policy) => (
          <article className="panel news-card" key={policy.id}>
            <DemoLabel>Demo headline</DemoLabel>
            <p className="eyebrow">{policy.topic}</p>
            <h3>{policy.headline}</h3>
            <Link href={"/policy/" + policy.id}>View sample policy →</Link>
          </article>
        ))}
      </div>
    </section>
  );
}
