// The only place the frontend calls FastAPI (AGENTS.md §7).
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}, timeout = 10_000) {
  let res;
  try {
    res = await fetch(`${API_URL}/api${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(timeout),
      ...options,
    });
  } catch {
    throw new ApiError(0, "The Policy Track API could not be reached.");
  }

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message = body?.error?.message ?? body?.detail;
    throw new ApiError(res.status, typeof message === "string" ? message : `Request failed (${res.status})`);
  }
  if (body === null) throw new ApiError(502, "The Policy Track API returned an invalid response.");
  return body;
}

export const getStateSenators = (stateCode) => request(`/states/${encodeURIComponent(stateCode)}/senators`);
export const getSenator = (bioguideId) => request(`/senators/${encodeURIComponent(bioguideId)}`);
export const getSenatorVotes = (bioguideId, params = {}) =>
  request(`/senators/${encodeURIComponent(bioguideId)}/votes?${new URLSearchParams(params)}`);
export const getVote = (voteId) => request(`/votes/${encodeURIComponent(voteId)}`);
export const getPolicy = (policyId) => request(`/policies/${encodeURIComponent(policyId)}`);
export const getPolicyArticles = (policyId) => request(`/policies/${encodeURIComponent(policyId)}/articles`);
export const getAiSummary = (body) => request("/ai/summary", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
}, 65_000);
