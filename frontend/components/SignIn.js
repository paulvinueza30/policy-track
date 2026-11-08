"use client";
import Script from "next/script";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import DistrictLookup from "./DistrictLookup";
import { sessionRequest } from "@/lib/api";
export default function SignIn({ clientId }) {
  const router=useRouter();const button=useRef(null);const selection=useRef(null);
  const [district,setDistrict]=useState(null);const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  function ready() {
    if (!window.google || !button.current) return;
    window.google.accounts.id.initialize({client_id:clientId,callback:async response=>{
      setBusy(true);setError("");
      try {
        const user=await sessionRequest("login",{credential:response.credential});
        if(selection.current) await sessionRequest("preferences",{...user.preferences,...selection.current});
        router.replace("/feed");router.refresh();
      }catch(e){setError(e.message);}finally{setBusy(false);}
    }});
    window.google.accounts.id.renderButton(button.current,{theme:"outline",size:"large",text:"continue_with",shape:"pill"});
  }
  return <div className="account-grid">
    <section className="account-intro"><p className="eyebrow">Your civic account</p><h1>A clearer view of your Congress.</h1><p>Follow your lawmakers and keep their recorded votes together in one personal feed.</p><ul><li>Explore your state’s delegation.</li><li>Follow members across both chambers.</li><li>Read official roll calls and source-linked policy explanations.</li></ul><Link href="/">← Back to the public map</Link></section>
    <div className="stack"><section className="panel sign-in"><p className="eyebrow">Citizen sign in</p><h2>Continue with Google</h2><p>Your public map stays available without an account. Sign in to save your district and followed lawmakers.</p>
      {clientId ? <><Script src="https://accounts.google.com/gsi/client" onReady={ready} onError={()=>setError("Google sign-in could not load. Please retry.")} /><div ref={button} aria-label="Google sign-in" /></> : <p className="empty" role="status">Google sign-in is awaiting configuration. You can still explore the public map and district lookup.</p>}
      {busy && <p role="status">Signing in and opening your feed…</p>}{error && <p role="alert">{error}</p>}
      <p className="account-note">Google verifies your identity. Your district and followed members are saved to your private account. Your ZIP is used for lookup and is not saved.</p>
    </section><DistrictLookup selected={district} onSelect={value=>{selection.current=value;setDistrict(value);}} /></div>
  </div>;
}
