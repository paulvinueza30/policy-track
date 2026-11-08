"use client";
import Link from "next/link";
import { useState } from "react";
import { districtLabel, findState, partyTone } from "@/lib/display";

export default function MemberVotes({ members, chamber, stateCode = "" }) {
  const [state, setState] = useState(stateCode);
  const [position, setPosition] = useState("");
  const [party, setParty] = useState("");
  const states = [...new Set(members.map(m => m.state).filter(Boolean))].sort();
  const parties = [...new Set(members.map(m => m.party).filter(Boolean))].sort();
  const filtered = members.filter(m => (!state || m.state === state) && (!position || m.position === position) && (!party || m.party === party));
  const groups = Object.groupBy(filtered, member => member.state || "Unknown");
  return <section className="policy-section">
    <h2>{state ? "How " + (findState(state)?.name ?? state) + " Members Voted" : "How Members Voted"}</h2>
    <p className="eyebrow">{chamber === "house" ? "Representatives" : "Senators"}</p>
    <div className="filters rollcall-filters">
      <label>State<select value={state} onChange={e=>setState(e.target.value)}><option value="">All states</option>{states.map(s=><option key={s} value={s}>{findState(s)?.name ?? s}</option>)}</select></label>
      <label>Position<select value={position} onChange={e=>setPosition(e.target.value)}><option value="">All positions</option>{["Yea","Nay","Present","Not Voting"].map(p=><option key={p}>{p}</option>)}</select></label>
      <label>Party<select value={party} onChange={e=>setParty(e.target.value)}><option value="">All parties</option>{parties.map(p=><option key={p}>{p}</option>)}</select></label>
    </div>
    <p role="status">{filtered.length} of {members.length} recorded positions</p>
    {!filtered.length && <p>No positions match these filters.</p>}
    {Object.entries(groups).sort(([a],[b])=>a.localeCompare(b)).map(([code, rows])=><details className="vote-state-group" key={code} open={!!state || !!position || !!party}>
      <summary>{findState(code)?.name ?? code} <span>{rows.length} members</span></summary>
      <ul className="roll-calls policy-votes">{rows.map(member=><li key={member.bioguideId}>
        <Link href={"/member/" + encodeURIComponent(member.bioguideId)}><strong>{member.name || member.bioguideId}</strong><small className={"party-text party-" + partyTone(member.party)}>{member.party}{chamber === "house" && member.district != null ? " · " + districtLabel(member) : ""}</small></Link>
        <span className={"vote-badge " + (member.position === "Yea" ? "yea" : member.position === "Nay" ? "nay" : "neutral")}>{member.position}</span>
      </li>)}</ul>
    </details>)}
  </section>;
}
