import Link from "next/link";
import { notFound } from "next/navigation";
import { DelegationExplorer, FeaturedVoting } from "@/components/VoteLens";
import states from "@/lib/states.json";

export default async function StatePage({ params, searchParams }) {
  const { stateCode } = await params;
  const { senator } = await searchParams;
  const code = stateCode.toUpperCase();
  const state = states.find((item) => item.code === code);
  if (!state) notFound();

  return (
    <main className="frame page">
      <nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/">United States Senate</Link></nav>
      <div className="intro compact">
        <p className="eyebrow">State delegation</p>
        <h1>{state.name}</h1>
      </div>
      <DelegationExplorer stateCode={code} senatorId={senator} />
      {code === "TX" && <FeaturedVoting senatorId={senator} />}
    </main>
  );
}
