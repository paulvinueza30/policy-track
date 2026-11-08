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
