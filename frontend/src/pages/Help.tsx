import { ArrowLeft, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { GuideIndex, GuideTopic } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { MarkdownView } from "../components/ide/MarkdownView";
import { useLocale, useT } from "../i18n";
import { resolveAppLink } from "../lib/appLinks";
import { PANEL_MAX_H, PANEL_SCROLL, SPLIT_COLS } from "../lib/layout";

function fold(text: string): string {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** Ayuda (feature 023): the guide topics the viewer's role may read, searchable by title and
 * summary; a topic opens in a view of the same page (`?tema=<id>`), never a dialog. */
export function Help() {
  const t = useT();
  const { locale } = useLocale();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const topicId = params.get("tema");
  const [index, setIndex] = useState<GuideIndex | null>(null);
  const [topic, setTopic] = useState<GuideTopic | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(false);
    api.get<GuideIndex>("/api/guide")
      .then((data) => { if (!cancelled) setIndex(data); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [locale]);

  useEffect(() => {
    if (!topicId) { setTopic(null); return; }
    let cancelled = false;
    setError(false);
    api.get<GuideTopic>(`/api/guide/topics/${encodeURIComponent(topicId)}`)
      .then((data) => { if (!cancelled) setTopic(data); })
      .catch(() => { if (!cancelled) { setTopic(null); setError(true); } });
    return () => { cancelled = true; };
  }, [topicId, locale]);

  const groups = useMemo(() => {
    if (!index) return [];
    const q = fold(query);
    const topics = index.topics.filter(
      (item) => !q || fold(item.title).includes(q) || fold(item.summary).includes(q));
    return index.sections
      .map((section) => ({ section, topics: topics.filter((item) => item.section === section.id) }))
      .filter((group) => group.topics.length > 0);
  }, [index, query]);

  const openTopic = (id: string) => setParams({ tema: id });
  const back = () => setParams({});
  const resolveLink = (to: string) => resolveAppLink(to, user ?? null);

  const list = (
    <section aria-label={t.help.title}
             className={`space-y-4 lg:min-h-0 lg:overflow-y-auto lg:pr-1 ${topicId ? "hidden lg:block" : ""}`}>
      <label className="relative block">
        <span className="sr-only">{t.help.search}</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" aria-hidden />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t.help.searchPlaceholder}
          className="min-h-tap w-full rounded-card border border-line bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        />
      </label>
      {index && groups.length === 0 && (
        <p className="text-sm text-ink-muted">{t.help.noMatch(query)}</p>
      )}
      {groups.map(({ section, topics }) => (
        <div key={section.id} className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">{section.title}</h2>
          <ul className="space-y-1">
            {topics.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => openTopic(item.id)}
                  aria-current={item.id === topicId ? "page" : undefined}
                  className={`flex min-h-tap w-full flex-col items-start rounded-card px-3 py-2 text-left hover:bg-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                    item.id === topicId ? "bg-accent-soft" : ""
                  }`}
                >
                  <span className="text-sm font-semibold text-ink">{item.title}</span>
                  <span className="text-xs text-ink-muted">{item.summary}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );

  return (
    <div>
      <PageHeader title={t.help.title} subtitle={t.help.subtitle} />
      {error && <div className="mb-4"><Alert tone="error">{t.help.loadFailed}</Alert></div>}
      {/* Two bounded panes from `lg` up: the topic list keeps its place while the article scrolls,
          and the page itself does not scroll (feature 050, evidence 5 and 6). Below `lg` the list is
          the first view and a topic replaces it, with Back to return to the same search. */}
      <div className={`${SPLIT_COLS} ${PANEL_MAX_H}`}>
        {list}
        {topicId && topic && (
          <article aria-labelledby="help-topic"
                   className={`flex min-w-0 flex-col rounded-card border border-line bg-surface ${PANEL_SCROLL}`}>
            <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-t-card border-b border-line bg-surface p-3">
              <Button variant="ghost" icon={<ArrowLeft className="h-4 w-4" aria-hidden />}
                      onClick={back} aria-label={t.help.backToList}>
                {t.help.back}
              </Button>
              <h2 id="help-topic" className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
                {topic.title}
              </h2>
            </div>
            <div className="min-w-0 p-4">
              <MarkdownView text={topic.body} resolveLink={resolveLink} />
            </div>
            {topic.related.length > 0 && (
              <nav aria-label={t.help.related} className="mt-auto space-y-2 border-t border-line p-4">
                <h3 className="text-sm font-semibold text-ink">{t.help.related}</h3>
                <ul className="flex flex-wrap gap-2">
                  {topic.related.map((rel) => (
                    <li key={rel.id}>
                      <button
                        type="button"
                        onClick={() => openTopic(rel.id)}
                        className="min-h-tap rounded-full border border-line px-3 text-sm text-ink hover:border-line-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      >
                        {rel.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </nav>
            )}
          </article>
        )}
      </div>
    </div>
  );
}
