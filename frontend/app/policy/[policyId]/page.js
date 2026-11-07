// Policy page: official info, how the state's senators voted, articles, AI summary.
// Data: GET /api/policies/{policyId}, /articles, POST /api/ai/summary (AGENTS.md §7)
export default async function PolicyPage({ params }) {
  const { policyId } = await params;
  return (
    <main>
      <h1>Policy {policyId}</h1>
      {/* TODO: policy details, votes, articles, AI summary */}
    </main>
  );
}
