import Link from "next/link";
import { notFound } from "next/navigation";
import { Portrait, VoteBadge, VoteCard } from "@/components/VoteLens";
import { ApiError, getMember, getMemberVotes } from "@/lib/api";
import { findState, formatDate, voteHref, voteSubtitle, chamberLabel, districtLabel, memberTitle, partyTone, stateHref } from "@/lib/display";

const positions = ["Yea", "Nay", "Present", "Not Voting"];
const pageSize = 25;
const filterDate = (value) => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";

export default async function MemberPage({ params, searchParams }) {
  const { bioguideId } = await params;
  const query = await searchParams;
  const allVotes = query.view === "all";
  const selectedPosition = positions.includes(query.position) ? query.position : "";
  const from = filterDate(query.from);
  const to = filterDate(query.to);
  const requestedPage = Number(query.page);
  const page = allVotes && Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const filters = {};
  const chamber = ["senate", "house"].includes(query.chamber) ? query.chamber : "";
  if (chamber) filters.chamber = chamber;
  if (allVotes) {
    if (selectedPosition) filters.position = selectedPosition;
    if (from) filters.from = from;
    if (to) filters.to = to;
  }

  const [profile, record] = await Promise.allSettled([
    getMember(bioguideId),
    getMemberVotes(bioguideId, { ...filters, page, pageSize: allVotes ? pageSize : 3 }),
  ]);
  if (profile.status === "rejected") {
    if (!(profile.reason instanceof ApiError)) throw profile.reason;
    if (profile.reason.status === 404) notFound();
    return <main className="frame page"><p className="panel empty">The member profile is unavailable right now.</p></main>;
  }
  if (record.status === "rejected" && !(record.reason instanceof ApiError)) throw record.reason;
  const member = profile.value;
  const state = findState(member.state);
  const chambers = [...new Set((member.roles ?? []).map(role => role.chamber))];
  const voteHeading = chambers.length > 1 ? "Votes in Congress" : chamberLabel(member.chamber) + " Votes";
  const recordView = (view) => "?" + new URLSearchParams({view, ...(chamber ? {chamber} : {})}) + "#recent-policies";
  const votes = record.status === "fulfilled" ? record.value : null;
  const items = votes?.items.slice(0, allVotes ? pageSize : 3);
  const totalPages = votes ? Math.ceil(votes.total / (votes.pageSize ?? pageSize)) : 0;
  const votePage = (number) => "?" + new URLSearchParams({ ...filters, view: "all", page: number }) + "#recent-policies";

  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">U.S. Congress</Link>
        {state && <><span aria-hidden="true">›</span><Link href={stateHref(state.code, member.chamber, member.district, member.bioguideId) + "#delegation"}>{state.name} Delegation</Link></>}
      </nav>
      <section className={"panel profile party-" + partyTone(member.party)}>
        <Portrait member={member} />
        <div>
          <p className="eyebrow">U.S. {chamberLabel(member.chamber)} · {member.chamber === "house" ? districtLabel(member) : state?.name ?? member.state}</p>
          <h1>{member.name}</h1>
          <div className="profile-tags">
            {member.party && <span className="tag">{member.party}</span>}
            <span className="tag">{member.inOfficeTo ? "Former " + memberTitle(member).toLowerCase() : "Current " + memberTitle(member).toLowerCase()}</span>
          </div>
          {member.inOfficeFrom && <p>In office from {formatDate(member.inOfficeFrom)}{member.inOfficeTo ? " to " + formatDate(member.inOfficeTo) : ""}</p>}
        </div>
        <a href="#recent-policies" className="button">View voting record ↓</a>
      </section>
      <section className="section" id="recent-policies">
        <div className="section-heading">
          <div><p className="eyebrow">Member dossier</p><h2>{voteHeading}</h2></div>
          <nav className="segments" aria-label="Vote record views">
            <Link href={recordView("recent")} aria-current={!allVotes ? "page" : undefined}>Three most recent</Link>
            <Link href={recordView("all")} aria-current={allVotes ? "page" : undefined}>All votes</Link>
          </nav>
        </div>
        {chambers.length > 1 && <div className="panel role-history"><h3>Service in Congress</h3>{member.roles.map((role,index)=><p key={index}>{chamberLabel(role.chamber)} · {districtLabel(role)} · {formatDate(role.from)} – {role.to ? formatDate(role.to) : "Present"}</p>)}<nav className="segments" aria-label="Filter by chamber">{[["","All"],["senate","Senate"],["house","House"]].map(([value,label])=><Link key={value} href={"?" + new URLSearchParams({...filters,view:allVotes ? "all" : "recent",chamber:value})} aria-current={chamber === value ? "page" : undefined}>{label}</Link>)}</nav></div>}
        {allVotes && (
          <form action="#recent-policies" method="get" className="panel filters" key={JSON.stringify(filters)}>
            <input type="hidden" name="view" value="all" /><input type="hidden" name="chamber" value={chamber} />
            <label>Vote position<select name="position" defaultValue={selectedPosition}>
              <option value="">Any position</option>
              {positions.map((position) => <option key={position}>{position}</option>)}
            </select></label>
            <label>From<input type="date" name="from" defaultValue={from} /></label>
            <label>To<input type="date" name="to" defaultValue={to} /></label>
            <button className="button" type="submit">Filter votes</button>
          </form>
        )}
        {votes === null && <p className="panel empty">{record.reason.status === 400 || record.reason.status === 422 ? "Check that the dates are valid and that From is on or before To." : "The voting record is unavailable right now."}</p>}
        {votes && !items.length && <p className="panel empty">No votes match this view.</p>}
        {items?.length > 0 && (allVotes ? (
          <ul className="panel roll-calls" aria-label="Congressional roll calls">
            {items.map((vote) => (
              <li key={vote.voteId}>
                <VoteBadge position={vote.position} />
                <div className="vote-label">
                  <Link href={voteHref(vote, state?.code)}>{vote.title || vote.question}</Link>
                  <span className="vote-subtitle">{chamberLabel(vote.chamber)} · {voteSubtitle(vote)}</span>
                </div>
                <time dateTime={vote.date}>{formatDate(vote.date)}</time>
              </li>
            ))}
          </ul>
        ) : <div className="stack">{items.map((vote) => <VoteCard key={vote.voteId} vote={vote} stateCode={state?.code} />)}</div>)}
        {allVotes && votes && (page > 1 || page < totalPages) && (
          <nav className="vote-footer" aria-label="Vote pages">
            {page > 1 && <Link href={votePage(page - 1)}>← Previous page</Link>}
            <span>Page {page}</span>
            {page < totalPages && <Link href={votePage(page + 1)}>Next page →</Link>}
          </nav>
        )}
      </section>
    </main>
  );
}
