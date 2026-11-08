import Link from "next/link";
import StateMap from "./StateMap";
import DistrictMap from "./DistrictMap";
import ChamberToggle from "./ChamberToggle";
import Portrait from "./Portrait";
import MemberVotes from "./MemberVotes";
export { default as Portrait } from "./Portrait";
import StatePicker from "./StatePicker";
import states from "@/lib/states.json";

import { formatDate, voteHref, voteSubtitle, chamberLabel, districtLabel, memberTitle, partyTone, stateHref, memberHref } from "@/lib/display";

const stateOptions = states.map(({ code, name }) => ({ code, name }));
const tallyLabels = { yea: "Yea", nay: "Nay", present: "Present", notVoting: "Not Voting" };

export function DelegationExplorer({ state, members, active, error, chamber = "senate", district = null }) {
  const stateCode = state?.code ?? "";
  const visible = chamber === "house" ? members?.filter(member => member.district === district) : members;
  return <section className="panel explorer section" id="explore" aria-labelledby="explore-title">
    <div className="section-heading"><div><p className="eyebrow">Your representation</p><h2 id="explore-title">Explore by state</h2><p>Select a state to see its senators and representatives.</p></div>
      {state && <ChamberToggle stateCode={stateCode} chamber={chamber} />}
    </div>
    <div className="explore-grid">
      {state && chamber === "house" ? <DistrictMap key={stateCode} state={state} district={district} members={members ?? []} /> : <StateMap key={stateCode} states={states} stateCode={stateCode} />}
      <div className="delegation" id="delegation">
        <StatePicker key={stateCode} options={stateOptions} stateCode={stateCode} chamber={chamber} />
        {state ? <h3>{state.name} {chamber === "house" ? "House" : "Senate"} Delegation</h3> : <div className="explorer-welcome"><span className="eyebrow">Start with your state</span><h3>Meet the people who represent you.</h3><p>Explore senators statewide and representatives by congressional district.</p><div className="party-legend"><span className="party-democrat">Democrat</span><span className="party-republican">Republican</span><span className="party-independent">Independent</span></div></div>}
        {error && <p className="empty" role="status">{error}</p>}
        {chamber === "house" && district == null && <p className="empty">Select a district on the map.</p>}
        {!error && members?.length === 0 && <p className="empty">No {chamberLabel(chamber)} records are available for this state yet.</p>}
        {!error && district != null && members?.length > 0 && !visible?.length && <p className="empty">No member records are available for this district yet.</p>}
        {!!visible?.length && <ul className="senator-list member-list">{visible.map(member=><li key={member.bioguideId}>
          <Link className={"senator-link member-card party-" + partyTone(member.party)} href={stateHref(stateCode, chamber, district, member.bioguideId) + "#delegation"} aria-current={active?.bioguideId === member.bioguideId ? "true" : undefined}>
            <Portrait member={member} /><span><strong>{member.name}</strong><small>{member.party} · {member.inOfficeTo ? "Former" : "Current"} {memberTitle(member).toLowerCase()}</small>{chamber === "house" && <small>{districtLabel(member)}</small>}</span><span className="arrow" aria-hidden="true">{active?.bioguideId === member.bioguideId ? "✓" : "→"}</span>
          </Link></li>)}</ul>}
        {active && <div className={"active-senator party-" + partyTone(active.party)}><p className="eyebrow">Selected {memberTitle(active).toLowerCase()}</p><h3>{active.name}</h3><p>{districtLabel(active)} · {active.party}</p><Link className="button" href={memberHref(active)}>Open member profile →</Link></div>}
      </div>
    </div>
  </section>;
}

export function VoteBadge({ position }) {
  const tone = position === "Yea" ? "yea" : position === "Nay" ? "nay" : "neutral";
  return <span className={"vote-badge " + tone}>{position}</span>;
}

export function VoteCard({ vote, stateCode, member }) {
  return (
    <article className="panel vote-card">
      <div className="vote-meta">
        <VoteBadge position={vote.position} />
        <span>{chamberLabel(vote.chamber)} · Roll call {vote.voteNumber}</span>
        <time dateTime={vote.date}>{formatDate(vote.date)}</time>
      </div>
      <h3>{vote.title || vote.question}</h3>
      <p className="vote-subtitle">{voteSubtitle(vote)}</p>
      <div className="vote-footer">
        <span>{vote.result}</span>
        <Link href={voteHref(vote, stateCode, member)}>{vote.policyId ? "View vote and policy" : "View roll call"} →</Link>
      </div>
    </article>
  );
}

export function RollCall({ vote, state, positionsUnavailable }) {
  return <>
    <section className="policy-section"><h2>Roll-Call Tally</h2><div className="vote-meta"><span>{chamberLabel(vote.chamber)} · Roll call {vote.voteNumber}</span><time dateTime={vote.date}>{formatDate(vote.date)}</time><strong>{vote.result}</strong></div>
      <dl className="tallies">{Object.entries(tallyLabels).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{vote.tally[key]}</dd></div>)}</dl>
    </section>
    {positionsUnavailable ? <p>Individual positions are unavailable right now.</p> : <MemberVotes key={vote.voteId + (state?.code ?? "")} members={vote.memberVotes ?? []} chamber={vote.chamber} stateCode={state?.code} />}
  </>;
}
