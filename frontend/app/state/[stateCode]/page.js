// State page: lists the state's senators in the 4-year window.
// Data: GET /api/states/{stateCode}/senators (AGENTS.md §7)
export default async function StatePage({ params }) {
  const { stateCode } = await params;
  return (
    <main>
      <h1>Senators for {stateCode.toUpperCase()}</h1>
      {/* TODO: fetch with getStateSenators() from lib/api.js */}
    </main>
  );
}
