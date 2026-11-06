import { useEffect, useState } from "react";
import { Link } from "react-router";
import { ArrowRight, Download, Sparkles } from "lucide-react";
import { api } from "../../api/client";
import { projectsApi } from "../../api/projects";
import type { DataSource } from "../../api/types";
import { Button } from "../Button";
import { Card } from "../Card";
import { useLocale, useT } from "../../i18n";

const inputClass =
  "min-h-tap w-full rounded-card border border-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export type StarterKind = "integration" | "direct";

/**
 * Feature 057: the starter pack the app writes for an author who is not going to open a terminal.
 *
 * An inline card, not a modal — the product has no modals (see `no-modals.test.ts`). The zip is
 * rendered by the server from the published pack, so what this panel downloads is the same folder
 * `bizview init project` writes and the same template the release publishes.
 */
export function StarterPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT();
  const { locale } = useLocale();
  const [name, setName] = useState("");
  const [source, setSource] = useState<string>("");
  const [lang, setLang] = useState<"es" | "en">(locale === "en" ? "en" : "es");
  const [kind, setKind] = useState<StarterKind>("integration");
  const [sources, setSources] = useState<DataSource[] | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api.get<{ items: DataSource[] }>("/api/sources")
      .then((r) => !cancelled && setSources(r.items))
      .catch(() => !cancelled && setSources([]));
    return () => { cancelled = true; };
  }, [open]);

  useEffect(() => {
    if (open) setLang(locale === "en" ? "en" : "es");
  }, [open, locale]);

  const ready = name.trim().length > 0;

  if (!open) return null;

  /** The endpoint answers an attachment; an anchor keeps the request authenticated by cookie. */
  const download = (href: string) => {
    const link = document.createElement("a");
    link.href = href;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <Card className="space-y-3 border-line-accent p-4 sm:p-5" role="status">
      <div>
        <h2 className="text-lg font-semibold text-ink">{t.projects.starter.title}</h2>
        <p className="mt-1 text-sm text-ink-muted">{t.projects.starter.intro}</p>
      </div>

      <label className="block space-y-1 text-sm font-semibold text-ink-2">
        <span>{t.projects.starter.name}</span>
        <input className={inputClass} value={name} autoFocus
               onChange={(e) => setName(e.target.value)} placeholder={t.projects.name} />
        <span className="block text-xs font-normal text-ink-muted">{t.projects.starter.nameHint}</span>
      </label>

      <label className="block space-y-1 text-sm font-semibold text-ink-2">
        <span>{t.projects.starter.source}</span>
        <select className={inputClass} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">{t.projects.starter.sourceNone}</option>
          {(sources ?? []).map((item) => (
            <option key={item.id} value={item.name}>{item.name}</option>
          ))}
        </select>
        <span className="block text-xs font-normal text-ink-muted">{t.projects.starter.sourceHint}</span>
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block space-y-1 text-sm font-semibold text-ink-2">
          <span>{t.projects.starter.lang}</span>
          <select className={inputClass} value={lang}
                  onChange={(e) => setLang(e.target.value === "en" ? "en" : "es")}>
            <option value="es">{t.projects.starter.langEs}</option>
            <option value="en">{t.projects.starter.langEn}</option>
          </select>
        </label>
        <label className="block space-y-1 text-sm font-semibold text-ink-2">
          <span>{t.projects.starter.kind}</span>
          <select className={inputClass} value={kind}
                  onChange={(e) => setKind(e.target.value === "direct" ? "direct" : "integration")}>
            <option value="integration">{t.projects.starter.kindIntegration}</option>
            <option value="direct">{t.projects.starter.kindDirect}</option>
          </select>
        </label>
      </div>
      <p className="text-xs text-ink-muted">
        {kind === "integration"
          ? t.projects.starter.kindIntegrationHint
          : t.projects.starter.kindDirectHint}
      </p>
      <p className="text-xs text-ink-muted">{t.projects.starter.note}</p>

      <div className="flex flex-wrap items-center gap-2">
        <Button icon={<Download className="h-5 w-5" aria-hidden />} disabled={!ready}
                onClick={() => download(projectsApi.starterUrl({
                  name: name.trim(), source: source || null, lang, kind,
                }))}>
          {t.projects.starter.download}
        </Button>
        <Button variant="secondary" icon={<Download className="h-5 w-5" aria-hidden />}
                onClick={() => download(projectsApi.starterTemplateUrl())}>
          {t.projects.starter.downloadTemplate}
        </Button>
        <Link to="/ayuda?tema=paquete-inicial"
              className="inline-flex min-h-tap items-center gap-1 text-sm font-semibold text-accent hover:underline">
          <Sparkles className="h-4 w-4" aria-hidden />
          {t.projects.starter.help}
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
        <Button variant="ghost" onClick={onClose}>{t.common.cancel}</Button>
      </div>
      <p className="text-xs text-ink-muted">{t.projects.starter.templateHint}</p>
    </Card>
  );
}
