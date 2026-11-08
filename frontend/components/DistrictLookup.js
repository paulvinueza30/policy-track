"use client";
import { useState } from "react";
import Link from "next/link";
import states from "@/lib/states.json";
import { getStateMembers, lookupZip } from "@/lib/api";
import { districtLabel, stateHref } from "@/lib/display";
export default function DistrictLookup({ onSelect, selected }) {
  const [zip,setZip]=useState(""); const [choices,setChoices]=useState([]); const [state,setState]=useState("");
  const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  async function lookup(event) {
    event.preventDefault(); setBusy(true); setError(""); setChoices([]);
    try { const result=await lookupZip(zip); setChoices(result.districts); if (!result.districts.length) setError("No matching districts. Choose your state below."); }
    catch(e){setError(e.message);} finally{setBusy(false);}
  }
  async function chooseState(code) {
    setState(code); setBusy(true);setChoices([]);setError("");
    try { const members=await getStateMembers(code,"house"); setChoices([...new Set(members.map(m=>m.district).filter(d=>d!=null))].sort((a,b)=>a-b).map(d=>({state:code,district:d}))); }
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="panel district-lookup"><p className="eyebrow">Your congressional district</p><h2>Find your representation</h2>
    <p>A ZIP code can cross district lines. Confirm your district before saving.</p>
    <form onSubmit={lookup} className="lookup-form"><label htmlFor="residential-zip">5-digit ZIP code</label><div className="picker-controls"><input id="residential-zip" inputMode="numeric" autoComplete="postal-code" pattern="[0-9]{5}" maxLength={5} required value={zip} onChange={e=>setZip(e.target.value)} /><button className="button" disabled={busy}>Look up</button></div></form>
    <label htmlFor="manual-state">Or choose your state</label><select id="manual-state" value={state} disabled={busy} onChange={e=>chooseState(e.target.value)}><option value="" disabled>Select state</option>{states.map(s=><option key={s.code} value={s.code}>{s.name}</option>)}</select>
    {busy && <p role="status">Finding districts…</p>}{error && <p role="alert">{error}</p>}
    {!!choices.length && <div className="district-results"><label htmlFor="district-confirm">Confirm your district</label><select id="district-confirm" value={selected ? selected.state+":"+selected.district : ""} onChange={e=>{const [state,district]=e.target.value.split(":");onSelect({state,district:Number(district)});}}><option value="" disabled>Select a district</option>{choices.map(choice=><option key={choice.state+":"+choice.district} value={choice.state+":"+choice.district}>{districtLabel(choice)}</option>)}</select></div>}
    {selected && <Link href={stateHref(selected.state,"house",selected.district)}>Explore {districtLabel(selected)} →</Link>}
    <a href="https://www.house.gov/representatives/find-your-representative" target="_blank" rel="noreferrer">Confirm your district on house.gov ↗</a>
  </section>;
}
