"use client";

import { useActionState } from "react";
import { externalHref, formatDate } from "@/lib/display";

const initialState = { summary: null, error: null };

export default function PolicySummary({ summarize }) {
  const [state, submit, pending] = useActionState(summarize, initialState);
  const summary = state.summary;

  return (
    <section className="policy-section" aria-labelledby="ai-heading">
      <h2 id="ai-heading">AI Plain-English Summary</h2>
      {summary && (
        <div className="summary">
          <p>{summary.summary}</p>
          {summary.keyPoints?.length > 0 && <ul>{summary.keyPoints.map((point, index) => <li key={index}>{point}</li>)}</ul>}
          {summary.sources?.length > 0 && (
            <>
              <h3>Sources</h3>
              <ul>{summary.sources.map((source, index) => {
                const url = externalHref(source);
                return <li key={index}>{url ? <a href={url}>{source}</a> : source}</li>;
              })}</ul>
            </>
          )}
          <small>{summary.model}{summary.generatedAt && " · " + formatDate(summary.generatedAt)}</small>
        </div>
      )}
      {pending && <p role="status">Loading the AI summary…</p>}
      {state.error && <p role="alert">{state.error}</p>}
      <form action={submit}>
        <button className="button" disabled={pending} type="submit" name="regenerate" value={summary ? "true" : "false"}>
          {summary ? "Regenerate summary" : "Load AI summary"}
        </button>
      </form>
    </section>
  );
}
