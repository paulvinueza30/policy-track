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
