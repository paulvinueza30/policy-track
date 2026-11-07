import { DelegationExplorer } from "@/components/VoteLens";

export default function HomePage() {
  return (
    <main className="frame page">
      <section className="intro">
        <p className="eyebrow">Nonpartisan legislative tracker</p>
        <h1>Understand how your U.S. Senators vote on what matters to you.</h1>
        <p>Explore your state’s Senate delegation, browse roll-call votes, and see policy explained in plain English.</p>
      </section>
      <DelegationExplorer />
    </main>
  );
}
