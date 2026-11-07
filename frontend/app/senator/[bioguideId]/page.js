// Senator page: their votes, newest first, filterable by date range and position.
// Data: GET /api/senators/{bioguideId} and /api/senators/{bioguideId}/votes (AGENTS.md §7)
export default async function SenatorPage({ params }) {
  const { bioguideId } = await params;
  return (
    <main>
      <h1>Senator {bioguideId}</h1>
      {/* TODO: senator info, vote filters, vote list */}
    </main>
  );
}
