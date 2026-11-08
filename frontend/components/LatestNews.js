import { ApiError, getLatestNews } from "@/lib/api";
import { externalHref, formatDate } from "@/lib/display";

async function loadNews() {
  try {
    const articles = await getLatestNews();
    return Array.isArray(articles) ? articles : null;
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    return null;
  }
}

function NewsSection({ children }) {
  return (
    <section className="section" id="latest-news" aria-labelledby="latest-news-title">
      <div className="section-heading"><h2 id="latest-news-title">Latest from Congress</h2></div>
      {children}
    </section>
  );
}

export function LatestNewsLoading() {
  return <NewsSection><p className="panel empty" role="status">Loading the latest news…</p></NewsSection>;
}

export default async function LatestNews() {
  const articles = await loadNews();
  if (articles === null) return <NewsSection><p className="panel empty">Latest news is unavailable right now.</p></NewsSection>;
  if (!articles.length) return <NewsSection><p className="panel empty">No recent articles were found.</p></NewsSection>;
  return (
    <NewsSection>
      <div className="news-grid">
        {articles.map((item) => {
          const url = externalHref(item.url);
          return (
            <article className="panel news-card" key={item.url}>
              <p className="eyebrow">{item.source}</p>
              <h3>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{item.title}</a> : item.title}</h3>
              {item.publishedAt && <time dateTime={item.publishedAt}>{formatDate(item.publishedAt)}</time>}
              {item.description && <p>{item.description}</p>}
            </article>
          );
        })}
      </div>
    </NewsSection>
  );
}
