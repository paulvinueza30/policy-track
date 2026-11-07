// The ONLY place the frontend calls the backend (AGENTS.md §7, §9 rule 4).
// Never call Congress.gov, senate.gov, news APIs, Firestore or DeepSeek from the frontend.

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message = body?.error?.message || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body;
}

export const getStateSenators = (stateCode) => request(`/states/${stateCode}/senators`);
export const getSenator = (bioguideId) => request(`/senators/${bioguideId}`);
export const getSenatorVotes = (bioguideId, params = {}) =>
  request(`/senators/${bioguideId}/votes?${new URLSearchParams(params)}`);
export const getVote = (voteId) => request(`/votes/${voteId}`);
export const getPolicy = (policyId) => request(`/policies/${policyId}`);
export const getPolicyArticles = (policyId) => request(`/policies/${policyId}/articles`);
export const getAiSummary = (body) =>
  request(`/ai/summary`, { method: "POST", body: JSON.stringify(body) });
