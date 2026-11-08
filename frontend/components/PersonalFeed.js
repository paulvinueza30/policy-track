"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import DistrictLookup from "./DistrictLookup";
import Portrait from "./Portrait";
import { getStateMembers, getMember, sessionRequest } from "@/lib/api";
import { chamberLabel, districtLabel, formatDate, memberHref, partyTone, voteHref, voteSubtitle } from "@/lib/display";
export default function PersonalFeed() {
  const router=useRouter();const [user,setUser]=useState(null);const [signedOut,setSignedOut]=useState(false);
  const [scope,setScope]=useState("local");const [page,setPage]=useState(1);const [data,setData]=useState(null);
  const [members,setMembers]=useState([]);const [error,setError]=useState("");const [busy,setBusy]=useState(false);const [loading,setLoading]=useState(true);

  useEffect(()=>{sessionRequest("me").then(setUser).catch(e=>{if(e.status===401)setSignedOut(true);else setError(e.message);}).finally(()=>setLoading(false));},[]);
  useEffect(()=>{
    if(!user)return;let active=true;setLoading(true);setError("");setData(null);
    sessionRequest("feed?"+new URLSearchParams({scope,page})).then(value=>{if(active)setData(value);}).catch(e=>{if(active){setError(e.message);if(e.status===401)setSignedOut(true);}}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[user,scope,page]);
  useEffect(()=>{
    if(!user)return;let active=true;
    Promise.all([user.preferences.state ? getStateMembers(user.preferences.state) : Promise.resolve([]),Promise.all((user.preferences.following??[]).map(id=>getMember(id)))]).then(([delegation,followed])=>{if(active)setMembers([...new Map([...delegation.filter(m=>!m.inOfficeTo&&(m.chamber==="senate"||m.district===user.preferences.district)),...followed].map(m=>[m.bioguideId,m])).values()]);}).catch(e=>{if(active)setError(e.message);});
    return ()=>{active=false;};
  },[user]);
  async function save(preferences) {
    setBusy(true);setError("");
    try {const saved=await sessionRequest("preferences",preferences);setUser({...user,preferences:saved});setPage(1);}
    catch(e){setError(e.message);if(e.status===401)setSignedOut(true);}finally{setBusy(false);}
  }
  async function react(policyId,value) {
    const reactions={...(user.preferences.reactions??{})};
    if(reactions[policyId]===value)delete reactions[policyId];else reactions[policyId]=value;
    await save({...user.preferences,reactions});
  }
  async function follow(id) {
    const following=user.preferences.following??[];
    await save({...user.preferences,following:following.includes(id)?following.filter(value=>value!==id):[...following,id]});
  }

  if(signedOut)return <section className="panel sign-in"><p className="eyebrow">Personal feed</p><h1>Your Congress, in one place.</h1><p>Sign in to view your saved district and followed lawmakers.</p><Link className="button" href="/sign-in">Continue to sign in →</Link><Link href="/">Explore the public map</Link></section>;
  if(!user)return <p className="panel empty" role="status">{error || "Loading your account…"}</p>;
  return <><header className="feed-heading"><div><p className="eyebrow">Personal civic account</p><h1>Welcome back, {user.name}.</h1><p>Your district’s delegation and the congressional records you follow.</p></div><button className="button" onClick={async()=>{try{await sessionRequest("logout",{});router.replace("/sign-in");router.refresh();}catch(e){setError(e.message);}}}>Sign out</button></header>
    {error && <p className="panel empty" role="alert">{error}</p>}
    <div className="feed-layout"><section className="stack"><nav className="segments" aria-label="Feed views">{[["local","My district"],["national","National"],["following","Following"]].map(([value,label])=><button key={value} aria-pressed={scope===value} onClick={()=>{setScope(value);setPage(1);}}>{label}</button>)}</nav>
      <p className="account-note">{scope==="local" ? "Federal roll calls involving your district’s representative and state senators." : scope==="national" ? "Recorded votes across the U.S. Congress." : "Roll calls involving the members you follow."}</p>
      {loading && <p role="status">Loading your feed…</p>}
      {data && !data.items.length && <div className="panel empty">{data.needsDistrict ? "Choose your district to build this feed." : scope==="following" ? "Follow lawmakers to see their recorded votes here." : "No records are available for this view."}</div>}
      {data?.items.map(vote=><article className="panel vote-card" key={vote.voteId}><div className="vote-meta"><span className="tag">{chamberLabel(vote.chamber)}</span><time>{formatDate(vote.date)}</time><span>Roll call {vote.voteNumber}</span></div><h2><Link href={voteHref(vote,user.preferences.state)}>{vote.title || vote.question}</Link></h2><p className="vote-subtitle">{voteSubtitle(vote)}</p>{vote.policyId && <div className="segments" aria-label="Your policy reaction">{[["like","Support"],["dislike","Oppose"]].map(([value,label])=><button key={value} disabled={busy} aria-pressed={user.preferences.reactions?.[vote.policyId]===value} onClick={()=>react(vote.policyId,value)}>{label}</button>)}</div>}<div className="vote-footer"><span>{vote.result}</span><Link href={voteHref(vote,user.preferences.state)}>View record & policy →</Link></div></article>)}
      <nav className="vote-footer" aria-label="Feed pages"><button disabled={loading||page===1} onClick={()=>setPage(page-1)}>← Previous</button><span>Page {page}</span><button disabled={loading||!data?.hasMore} onClick={()=>setPage(page+1)}>Next →</button></nav>
    </section><aside className="stack"><DistrictLookup selected={user.preferences.state ? user.preferences : null} onSelect={choice=>save({...user.preferences,...choice})} />
      <section className="panel followed-members"><h2>Your lawmakers</h2><p>Follow up to 20 members to build your tracker.</p>{members.map(member=><div className={"follow-row party-"+partyTone(member.party)} key={member.bioguideId}><Portrait member={member}/><div><Link href={memberHref(member)}>{member.name}</Link><small>{member.party} · {districtLabel(member)}</small></div><button disabled={busy} aria-pressed={(user.preferences.following??[]).includes(member.bioguideId)} onClick={()=>follow(member.bioguideId)}>{(user.preferences.following??[]).includes(member.bioguideId)?"Unfollow":"Follow"}</button></div>)}
      <Link className="button" href="/">Find more lawmakers on the map →</Link></section>
    </aside></div></>;
}
