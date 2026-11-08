import { externalHref } from "@/lib/display";

/** The policy's summary from the official record. `summary` is null if the request failed. */
export default function RecordSummary({ summary, officialText }) {
  return (
    <section className="policy-section" aria-labelledby="summary-heading">
      <h2 id="summary-heading">Summary</h2>
      {summary ? (
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
        </div>
      ) : (
        <>
          <p>The summary is unavailable right now.</p>
          {officialText && <p>{officialText}</p>}
        </>
      )}
    </section>
  );
}
