"use client";
import {useState} from "react";
import Link from "next/link";
import {sessionRequest} from "@/lib/api";
export default function FollowMember({id}) {
 const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);const [signin,setSignin]=useState(false);
 async function follow(){setBusy(true);setMessage("");try{const user=await sessionRequest("me");const following=[...new Set([...(user.preferences.following??[]),id])];await sessionRequest("preferences",{...user.preferences,following});setMessage("Following. This member’s votes are included in your personal feed.");}catch(e){if(e.status===401)setSignin(true);else setMessage(e.message);}finally{setBusy(false);}}
 return <div className="follow-control"><button className="button" disabled={busy} onClick={follow}>{busy?"Saving…":"Follow this member"}</button>{signin&&<Link href="/sign-in">Sign in to follow →</Link>}{message&&<p role="status">{message}</p>}<Link href="/feed">Open my feed →</Link></div>;
}
