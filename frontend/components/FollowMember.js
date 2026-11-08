"use client";
import { useState } from "react";
import Link from "next/link";
import { setFollowed, useFollowing } from "@/lib/following";

/** Follow/unfollow toggle. `compact` is the small version for member lists. */
export default function FollowMember({ id, name, compact = false }) {
  const { status, following } = useFollowing();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const label = name ? " " + name : "";
  const className = compact ? "follow-control compact" : "follow-control";

  if (status === "idle" || status === "loading") return <div className={className} aria-hidden="true" />;
  if (status === "signedOut") return <div className={className}><Link href="/sign-in" aria-label={"Sign in to follow" + label}>Sign in to follow →</Link></div>;
  if (status === "error") return null;

  const followed = following.includes(id);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      await setFollowed(id, !followed);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={className}>
      <button type="button" className={compact ? "follow-button" : "button"} aria-disabled={busy} aria-pressed={followed}
        aria-label={(followed ? "Unfollow" : "Follow") + (label || " this member")} onClick={toggle}>
        {busy ? "Saving…" : followed ? (compact ? "Following ✓" : "Following ✓ · Unfollow") : "Follow"}
      </button>
      {message && <p role="alert">{message}</p>}
      {!compact && followed && <Link href="/feed">Open my feed →</Link>}
    </div>
  );
}
