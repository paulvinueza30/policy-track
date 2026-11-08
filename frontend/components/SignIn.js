"use client";
import Script from "next/script";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import DeleteAccount from "./DeleteAccount";
import DistrictLookup from "./DistrictLookup";
import { sessionRequest } from "@/lib/api";
import { districtLabel } from "@/lib/display";
import { resetFollowing } from "@/lib/following";

function AccountPanel({ user, onSignOut, busy, error }) {
  const preferences = user.preferences ?? {};
  return (
    <section className="panel sign-in account-panel" aria-labelledby="account-title">
      <p className="eyebrow">Your account</p>
      <h2 id="account-title">Signed in as {user.name}</h2>
      <p>{preferences.state ? <>Your saved district: <strong>{districtLabel(preferences)}</strong></> : "You haven’t saved a district yet."}</p>
      <div className="personal-actions">
        <Link className="button" href="/">Home</Link>
        <Link href="/feed">My feed →</Link>
        <button type="button" className="follow-button" aria-disabled={busy} onClick={onSignOut}>{busy ? "Signing out…" : "Sign out"}</button>
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export default function SignIn({ clientId }) {
  const router = useRouter();
  const button = useRef(null);
  const selection = useRef(null);
  const [session, setSession] = useState({ status: "checking", user: null });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const checkSession = useCallback(() => {
    setSession({ status: "checking", user: null });
    sessionRequest("me")
      .then((user) => setSession({ status: "signedIn", user }))
      .catch((e) => setSession({ status: e.status === 401 ? "signedOut" : "failed", user: null }));
  }, []);

  useEffect(() => { checkSession(); }, [checkSession]);

  function ready() {
    if (!window.google || !button.current) return;
    window.google.accounts.id.initialize({ client_id: clientId, callback: async (response) => {
      setBusy(true);
      setError("");
      try {
        const user = await sessionRequest("login", { credential: response.credential });
        if (selection.current) await sessionRequest("preferences", { ...user.preferences, ...selection.current });
        resetFollowing();
        router.replace("/");
        router.refresh();
      } catch (e) {
        setError(e.message);
      } finally {
        setBusy(false);
      }
    } });
    window.google.accounts.id.renderButton(button.current, { theme: "outline", size: "large", text: "continue_with", shape: "pill" });
  }

  async function signOut() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await sessionRequest("logout", {});
      resetFollowing();
      setSession({ status: "signedOut", user: null });
      router.refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveDistrict(choice) {
    const preferences = await sessionRequest("preferences", { ...session.user.preferences, ...choice });
    setSession((current) => ({ ...current, user: { ...current.user, preferences } }));
  }

  function followed(following) {
    setSession((current) => ({ ...current, user: { ...current.user, preferences: { ...current.user.preferences, following } } }));
  }

  const { status, user } = session;

  return (
    <div className="account-grid">
      <section className="account-intro">
        <p className="eyebrow">Your civic account</p>
        <h1>A clearer view of your Congress.</h1>
        <p>Follow your lawmakers and keep their recorded votes together in one personal feed.</p>
        <ul>
          <li>Explore your state’s delegation.</li>
          <li>Follow members across both chambers.</li>
          <li>Read official roll calls and source-linked policy explanations.</li>
        </ul>
        <Link href="/">← Back to the public map</Link>
      </section>
      <div className="stack">
        {status === "checking" && <section className="panel sign-in"><p role="status">Checking your account…</p></section>}
        {status === "failed" && (
          <section className="panel sign-in">
            <p role="alert">We couldn’t check your account right now. Please try again.</p>
            <button type="button" className="button" onClick={checkSession}>Try again</button>
          </section>
        )}
        {status === "signedOut" && (
          <section className="panel sign-in">
            <p className="eyebrow">Citizen sign in</p>
            <h2>Continue with Google</h2>
            <p>Your public map stays available without an account. Sign in to save your district and followed lawmakers.</p>
            {clientId
              ? <><Script src="https://accounts.google.com/gsi/client" onReady={ready} onError={() => setError("Google sign-in could not load. Please retry.")} /><div ref={button} aria-label="Google sign-in" /></>
              : <p className="empty" role="status">Google sign-in is awaiting configuration. You can still explore the public map and district lookup.</p>}
            {busy && <p role="status">Signing in…</p>}
            {error && <p role="alert">{error}</p>}
            <p className="account-note">Google verifies your identity. Your district and followed members are saved to your private account. Your ZIP is used for lookup and is not saved.</p>
          </section>
        )}
        {status === "signedIn" && <AccountPanel user={user} onSignOut={signOut} busy={busy} error={error} />}
        {status === "signedIn" && <DistrictLookup signedIn selected={user.preferences?.state ? user.preferences : null} onSave={saveDistrict} onFollowed={followed} />}
        {status === "signedOut" && <DistrictLookup onSelect={(value) => { selection.current = value; }} />}
        {status === "signedIn" && <DeleteAccount />}
      </div>
    </div>
  );
}
