import { cookies } from "next/headers";
import { Suspense } from "react";
import LatestNews, { LatestNewsLoading } from "@/components/LatestNews";
import PersonalHome from "@/components/PersonalHome";
import { DelegationExplorer } from "@/components/VoteLens";

export default async function HomePage() {
  const signedIn = (await cookies()).has("realnews_session");
  return (
    <main className="frame page">
      <section className="intro">
        <p className="eyebrow">Nonpartisan legislative tracker</p>
        <h1>Understand how your members of Congress vote on what matters to you.</h1>
        <p>Explore your state’s senators and representatives, browse roll-call votes, and see policy explained in plain English.</p>
      </section>
      {signedIn && <PersonalHome />}
      <DelegationExplorer />
      {/* Streams in separately so the map and state picker never wait on the news. */}
      <Suspense fallback={<LatestNewsLoading />}>
        <LatestNews />
      </Suspense>
    </main>
  );
}
