import states from "./states.json";

export function findState(code) {
  return typeof code === "string" ? states.find((state) => state.code === code.toUpperCase()) : undefined;
}

export function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeZone: value.length === 10 ? "UTC" : "America/New_York",
  }).format(date);
}

// Plain-English vote types. Keep these factual: a Yea on a procedural vote is not
// necessarily support for the measure itself. Order matters (cloture comes first).
const VOTE_TYPES = [
  [/suspend the rules/i, "Fast-track vote (needs two-thirds)"],
  [/objections of the president/i, "Vote to override a veto"],
  [/previous question/i, "Vote to end debate and move to a vote"],
  [/motion to recommit|motion to commit/i, "Vote to send it back to committee"],
  [/motion to refer/i, "Vote to send it to a committee"],
  [/motion to concur/i, "Vote on the Senate's changes"],
  [/motion to instruct/i, "Vote to instruct negotiators"],
  [/motion to adjourn/i, "Vote to adjourn"],
  [/motion to reconsider/i, "Vote to reconsider"],
  [/consideration of the resolution/i, "Vote to start considering it"],
  [/agreeing to the resolution/i, "Vote to pass it"],
  [/cloture/i, "Vote to end debate"],
  [/motion to proceed/i, "Vote to start considering it"],
  [/motion to discharge/i, "Vote to pull it out of committee"],
  [/motion to table/i, "Vote to set it aside"],
  [/motion to recommit/i, "Vote to send it back to committee"],
  [/point of order/i, "Vote on a procedural objection"],
  [/decision of the chair/i, "Vote on the presiding officer's ruling"],
  [/nomination/i, "Confirmation vote"],
  [/amendment/i, "Vote on an amendment"],
  [/conference report/i, "Vote on the final House-Senate version"],
  [/passage|on the (joint |concurrent )?resolution|on the bill/i, "Vote to pass it"],
];

export function voteType(question) {
  return VOTE_TYPES.find(([pattern]) => pattern.test(question ?? ""))?.[1] ?? question;
}

// The second line of a vote label, e.g. "Vote to end debate · H.R. 6938".
export function voteSubtitle(vote) {
  return [voteType(vote.question), vote.documentLabel].filter(Boolean).join(" · ");
}

export function voteHref(vote, stateCode) {
  const params = new URLSearchParams();
  if (stateCode) params.set("state", stateCode);
  if (vote.policyId) params.set("vote", vote.voteId);
  const query = params.size ? "?" + params : "";
  return vote.policyId
    ? "/policy/" + encodeURIComponent(vote.policyId) + query
    : "/vote/" + encodeURIComponent(vote.voteId) + query;
}

export function externalHref(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export const chamberLabel = (chamber) => chamber === "house" ? "House" : chamber === "senate" ? "Senate" : "Congress";
export const memberTitle = (member) => member.chamber === "house" ? "Representative" : "Senator";
export const partyTone = (party) => /^(D|Democrat|Democratic)$/i.test(party ?? "") ? "democrat" : /^(R|Republican)$/i.test(party ?? "") ? "republican" : /^(I|Independent)$/i.test(party ?? "") ? "independent" : "other";
export function ordinal(number) {
  return number + ((number % 100 >= 11 && number % 100 <= 13) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[number % 10] ?? "th"));
}
export function districtLabel(member) {
  return member.district === 0 ? member.state + " · At-large" : member.district != null ? member.state + "-" + member.district + " · " + ordinal(member.district) + " District" : member.state + " · Statewide";
}
export function stateHref(code, chamber = "senate", district = null, member = null) {
  const query = new URLSearchParams({ chamber });
  if (chamber === "house" && district != null) query.set("district", district);
  if (member) query.set("member", member);
  return "/state/" + code + "?" + query;
}
