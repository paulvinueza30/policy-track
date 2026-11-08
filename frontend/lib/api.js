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

export const getStateMembers = (stateCode, chamber) => request(`/states/${encodeURIComponent(stateCode)}/members?${new URLSearchParams(chamber ? { chamber } : {})}`);
export const getMember = (id) => request(`/members/${encodeURIComponent(id)}`);
export const getMemberVotes = (id, params = {}) => request(`/members/${encodeURIComponent(id)}/votes?${new URLSearchParams(params)}`);
export const getVote = (voteId) => request(`/votes/${encodeURIComponent(voteId)}`);
export const getPolicy = (policyId) => request(`/policies/${encodeURIComponent(policyId)}`);
export const getPolicyArticles = (policyId) => request(`/policies/${encodeURIComponent(policyId)}/articles`);
const postAi = (path, body) => request(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
}, 65_000);
export const getAiSummary = (body) => postAi("/ai/summary", body);
export const askAboutPolicy = (body) => postAi("/ai/ask", body);

export const accountRequest = (path = "", options = {}) => request("/account" + path, options);
export const lookupZip = (zip) => request("/districts/zip/" + encodeURIComponent(zip));
// Browser account requests use the same-origin session bridge. Credentials stay in HttpOnly cookies.
export async function sessionRequest(action, body, method = body ? "POST" : "GET") {
  const response = await fetch("/api/session/" + action, { method, cache: "no-store",
    ...(body ? {headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {}) });
  const data = await response.json();
  if (!response.ok) throw new ApiError(response.status, data.error?.message || "Request failed");
  return data;
}
