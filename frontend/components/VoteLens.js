import Link from "next/link";
import SenateMap from "./SenateMap";
import StatePicker from "./StatePicker";
import states from "@/lib/states.json";
import { ApiError, getStateSenators } from "@/lib/api";
import { formatDate, voteHref } from "@/lib/display";

const stateOptions = states.map(({ code, name }) => ({ code, name }));
const tallyLabels = { yea: "Yea", nay: "Nay", present: "Present", notVoting: "Not Voting" };

export function Portrait({ senator }) {
  const initials = senator.name.split(/\s+/).filter(Boolean).slice(0, 2).map((name) => name[0]).join("");
  return <span className="portrait" aria-hidden="true">{initials}</span>;
}

export function DelegationExplorer({ state, senators, active, error }) {
  const stateCode = state?.code ?? "";
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
          {state && <h3>{state.name} Senate Delegation</h3>}
          {error && <p className="empty" role="status">{error}</p>}
          {senators?.length === 0 && <p className="empty">No Senate records are available for this state yet.</p>}
          {active && (
            <>
              <ul className="senator-list">
                {senators.map((senator) => (
                  <li key={senator.bioguideId}>
                    <Link className="senator-link" href={`/state/${stateCode}?senator=${encodeURIComponent(senator.bioguideId)}#delegation`}
                      aria-current={active.bioguideId === senator.bioguideId ? "true" : undefined}>
                      <Portrait senator={senator} />
                      <span><strong>{senator.name}</strong><small>{senator.party} · {senator.inOfficeTo ? "Former senator" : "Current senator"}</small></span>
                      <span className="arrow" aria-hidden="true">{active.bioguideId === senator.bioguideId ? "✓" : "→"}</span>
                    </Link>
                  </li>
                ))}
              </ul>
              <div className="active-senator">
                <p className="eyebrow">Selected senator</p>
                <h3>{active.name}</h3>
                <p>{state.name} · {active.party}</p>
                <Link className="button" href={"/senator/" + encodeURIComponent(active.bioguideId)}>Open senator dossier →</Link>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

export function VoteBadge({ position }) {
  const tone = position === "Yea" ? "yea" : position === "Nay" ? "nay" : "neutral";
  return <span className={"vote-badge " + tone}>{position}</span>;
}

export function VoteCard({ vote, stateCode }) {
  return (
    <article className="panel vote-card">
      <div className="vote-meta">
        <VoteBadge position={vote.position} />
        <span>Roll call {vote.voteNumber}</span>
        <time dateTime={vote.date}>{formatDate(vote.date)}</time>
      </div>
      <h3>{vote.question}</h3>
      <div className="vote-footer">
        <span>{vote.result}</span>
        <Link href={voteHref(vote, stateCode)}>{vote.policyId ? "View vote and policy" : "View roll call"} →</Link>
      </div>
    </article>
  );
}

export async function RollCall({ vote, state, positionsUnavailable }) {
  const members = vote.senatorVotes ?? [];
  const needsDelegation = state && members.some((member) => !member.state);
  const delegation = needsDelegation ? await getStateSenators(state.code).catch((error) => {
    if (!(error instanceof ApiError)) throw error;
    return null;
  }) : [];
  const byId = new Map(delegation?.map((senator) => [senator.bioguideId, senator]));
  const positions = members.filter((member) => !state || (member.state ?? byId.get(member.bioguideId)?.state) === state.code);
  return (
    <>
      <section className="policy-section">
        <h2>Roll-Call Tally</h2>
        <div className="vote-meta">
          <span>Roll call {vote.voteNumber}</span>
          <time dateTime={vote.date}>{formatDate(vote.date)}</time>
          <strong>{vote.result}</strong>
        </div>
        <dl className="tallies">
          {Object.entries(tallyLabels).map(([key, label]) => (
            <div key={key}><dt>{label}</dt><dd>{vote.tally[key]}</dd></div>
          ))}
        </dl>
      </section>
      <section className="policy-section">
        <h2>{state ? `How ${state.name} Senators Voted` : "How Senators Voted"}</h2>
        {positionsUnavailable ? <p>Individual positions are unavailable right now.</p>
          : positions?.length ? (
            <ul className="roll-calls policy-votes">
              {positions.map((member) => (
                <li key={member.bioguideId}>
                  <Link href={"/senator/" + encodeURIComponent(member.bioguideId)}>
                    {member.name || byId.get(member.bioguideId)?.name || member.bioguideId}{!state && member.state ? ` · ${member.state}` : ""}
                  </Link>
                  <VoteBadge position={member.position} />
                </li>
              ))}
            </ul>
          ) : <p>No individual positions were returned for this roll call.</p>}
        {needsDelegation && !delegation && <p>Some positions could not be matched to this state.</p>}
      </section>
    </>
  );
}
