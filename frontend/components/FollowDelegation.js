"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getStateMembers, sessionRequest } from "@/lib/api";
import { districtLabel } from "@/lib/display";
import { syncFollowing } from "@/lib/following";

/** Follows the current senators and representative for a saved district, skipping anyone already followed. */
export default function FollowDelegation({ district, onFollowed }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const button = useRef(null);
  const status = useRef(null);

  // This appears right after saving, in place of the Save button, so keep keyboard focus here.
  useEffect(() => { button.current?.focus(); }, []);
  useEffect(() => { if (result) status.current?.focus(); }, [result]);

  async function followAll() {
    if (busy) return;
    setBusy(true);
    setResult(null);
    try {
      const [members, user] = await Promise.all([getStateMembers(district.state), sessionRequest("me")]);
      const current = members.filter((m) => !m.inOfficeTo && (m.chamber === "senate" || m.district === district.district));
      let following = user.preferences?.following ?? [];
      const alreadyFollowing = current.filter((m) => following.includes(m.bioguideId));
      const followed = [];
      const failed = [];
      let stopReason = "";
      for (const member of current.filter((m) => !following.includes(m.bioguideId))) {
        if (stopReason) {
          failed.push(member.name);
          continue;
        }
        try {
          following = (await sessionRequest("follow", { bioguideId: member.bioguideId })).following;
          followed.push(member.name);
        } catch (error) {
          failed.push(member.name);
          if (error.status === 422 && /up to/i.test(error.message)) stopReason = error.message;
          else if (error.status === 401) stopReason = "Your sign-in expired. Please sign in again.";
        }
      }
      if (followed.length) {
        syncFollowing(following);
        onFollowed?.(following);
      }
      setResult({
        followed,
        alreadyFollowing: alreadyFollowing.map((m) => m.name),
        failed,
        stopReason,
        noRepresentative: !current.some((m) => m.chamber === "house"),
        senatorCount: current.filter((m) => m.chamber === "senate").length,
      });
    } catch (error) {
      setResult({ error: error.message || "Your lawmakers couldn’t be followed right now. Please try again." });
    } finally {
      setBusy(false);
    }
  }

  const finished = result && !result.error && !result.failed.length;

  return (
    <div className="follow-delegation">
      {!finished && (
        <button type="button" ref={button} className="button" aria-disabled={busy} onClick={followAll}>
          {busy ? "Following…" : "Follow your 2 senators and representative"}
        </button>
      )}
      {result?.error && <p role="alert" ref={status} tabIndex={-1}>{result.error}</p>}
      {result && !result.error && (
        <div role="status" ref={status} tabIndex={-1}>
          {result.followed.length > 0 && <p>Now following: {result.followed.join(", ")}.</p>}
          {result.alreadyFollowing.length > 0 && <p>Already following: {result.alreadyFollowing.join(", ")}.</p>}
          {result.noRepresentative && <p>No current representative was found for {districtLabel(district)}.</p>}
          {result.senatorCount < 2 && <p>Our records list {result.senatorCount === 1 ? "only 1 current senator" : "no current senators"} for {district.state}.</p>}
          {result.failed.length > 0 && <p role="alert">{(result.stopReason || "Some follows didn’t go through").replace(/\.?$/, ".")} Not followed: {result.failed.join(", ")}.</p>}
        </div>
      )}
      {result && !result.error && <Link href="/">Go to your home page →</Link>}
    </div>
  );
}
