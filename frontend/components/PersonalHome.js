"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import Portrait from "./Portrait";
import { getMember, sessionRequest } from "@/lib/api";
import { districtLabel, externalHref, formatDate, memberHref, partyTone, stateHref } from "@/lib/display";
import { setFollowed, useFollowing } from "@/lib/following";

// While the server is still gathering news: show what's cached and ask again, then stop.
const NEWS_RETRY_DELAY_MS = 2000;
const NEWS_MAX_REPEATS = 5;

function LawmakerGroup({ title, members, onUnfollow, busyId }) {
  if (!members.length) return null;
  return (
    <section aria-label={title}>
      <h3>{title}</h3>
      <ul className="lawmaker-list">
        {members.map((member) => (
          <li key={member.bioguideId} className={"follow-row party-" + partyTone(member.party)}>
            <Portrait member={member} />
            <div>
              <Link href={memberHref(member)}>{member.name}</Link>
              <small>{member.party} · {districtLabel(member)}</small>
            </div>
            <button type="button" disabled={busyId === member.bioguideId} aria-label={"Unfollow " + member.name}
              onClick={() => onUnfollow(member.bioguideId)}>
              {busyId === member.bioguideId ? "Saving…" : "Unfollow"}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PersonalNews({ members, following }) {
  const [news, setNews] = useState({ items: [], pending: false, status: "loading" });
  const followingKey = following.join(",");
  const names = useMemo(() => new Map(members.map((m) => [m.bioguideId, m.name])), [members]);

  useEffect(() => {
    let active = true;
    let timer;
    async function fetchNews(attempt) {
      try {
        const data = await sessionRequest("news");
        if (!active) return;
        setNews({ items: data.items ?? [], pending: !!data.pending, status: "ready" });
        if (data.pending && attempt < NEWS_MAX_REPEATS) timer = setTimeout(() => fetchNews(attempt + 1), NEWS_RETRY_DELAY_MS);
        else if (data.pending) setNews((current) => ({ ...current, pending: false }));
      } catch {
        if (active) setNews((current) => ({ ...current, pending: false, status: current.items.length ? "ready" : "failed" }));
      }
    }
    fetchNews(0);
    return () => { active = false; clearTimeout(timer); };
  }, [followingKey]);

  const items = news.items.filter((item) => (item.memberIds ?? []).some((id) => following.includes(id)));

  return (
    <section className="personal-news" aria-labelledby="personal-news-title">
      <h3 id="personal-news-title">News about them</h3>
      {news.status === "loading" && <p className="empty" role="status">Loading news about your lawmakers…</p>}
      {news.status === "failed" && <p className="empty">News about your lawmakers is unavailable right now.</p>}
      {news.pending && <p className="account-note" role="status">Looking for more articles…</p>}
      {news.status === "ready" && !items.length && !news.pending && <p className="empty">No recent articles were found about your lawmakers.</p>}
      {items.length > 0 && (
        <div className="news-grid">
          {items.map((item) => {
            const url = externalHref(item.url);
            const about = (item.memberIds ?? []).filter((id) => following.includes(id)).map((id) => names.get(id)).filter(Boolean);
            return (
              <article className="panel news-card" key={item.url}>
                {about.length > 0 && <span className="tag news-about">About {about.join(", ")}</span>}
                <p className="eyebrow">{item.source}</p>
                <h3>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{item.title}</a> : item.title}</h3>
                {item.publishedAt && <time dateTime={item.publishedAt}>{formatDate(item.publishedAt)}</time>}
                {item.description && <p>{item.description}</p>}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function PersonalHome() {
  const { status, following, user } = useFollowing();
  const [members, setMembers] = useState(null);
  const [failed, setFailed] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState("");
  const loaded = useRef(new Map());
  const followingKey = following.join(",");

  useEffect(() => {
    if (status !== "ready") return undefined;
    let active = true;
    const ids = followingKey ? followingKey.split(",") : [];
    Promise.allSettled(ids.map((id) => loaded.current.get(id) ?? getMember(id))).then((results) => {
      if (!active) return;
      const found = results.filter((r) => r.status === "fulfilled").map((r) => r.value);
      found.forEach((member) => loaded.current.set(member.bioguideId, member));
      setMembers(found);
      setFailed(found.length < ids.length);
    });
    return () => { active = false; };
  }, [status, followingKey]);

  // An expired cookie looks like signed out, so the page falls back to the public view.
  if (status === "signedOut" || status === "error") return null;
  if (status !== "ready" || members === null) {
    return <section className="panel personal-home section"><p className="empty" role="status">Loading your lawmakers…</p></section>;
  }

  async function unfollow(id) {
    setBusyId(id);
    setMessage("");
    try {
      await setFollowed(id, false);
      // The row is gone, so move keyboard focus somewhere stable.
      setTimeout(() => (document.getElementById("personal-title") ?? document.getElementById("choose-lawmakers"))?.focus(), 0);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusyId(null);
    }
  }

  if (!following.length) {
    const homeState = user?.preferences?.state;
    return (
      <section className="panel personal-home section" aria-labelledby="choose-lawmakers">
        <p className="eyebrow">Your account</p>
        <h2 id="choose-lawmakers" tabIndex={-1}>Choose your lawmakers</h2>
        <p>Follow your senators and representatives to see them here, along with news about them.</p>
        <div className="personal-actions">
          {homeState && <Link className="button" href={stateHref(homeState, "house", user.preferences.district)}>Go to my state →</Link>}
          <a className={homeState ? undefined : "button"} href="#explore">Find them on the map ↓</a>
        </div>
      </section>
    );
  }

  const visible = members.filter((member) => following.includes(member.bioguideId));
  return (
    <section className="panel personal-home section" aria-labelledby="personal-title">
      <div className="section-heading">
        <div><p className="eyebrow">Your account</p><h2 id="personal-title" tabIndex={-1}>Your lawmakers</h2></div>
        <Link href="/feed">See their votes →</Link>
      </div>
      {message && <p role="alert">{message}</p>}
      {failed && <p className="empty">Some lawmakers couldn’t be loaded right now.</p>}
      <div className="lawmaker-groups">
        <LawmakerGroup title="Your Senators" members={visible.filter((m) => m.chamber === "senate")} onUnfollow={unfollow} busyId={busyId} />
        <LawmakerGroup title="Your House Reps" members={visible.filter((m) => m.chamber === "house")} onUnfollow={unfollow} busyId={busyId} />
      </div>
      <PersonalNews members={visible} following={following} />
    </section>
  );
}
