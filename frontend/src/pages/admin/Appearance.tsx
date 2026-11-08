import { Check, Copy, Download, Palette, Plus, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { api, ApiError } from "../../api/client";
import type { ThemeLibrary, ThemeOrigin, ThemeRow } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Link } from "react-router";
import { BackLink } from "../../components/BackLink";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { IconButton } from "../../components/IconButton";
import { PageHeader } from "../../components/PageHeader";
import { CARD_GRID_3, CARD_PAD, PAGE_STACK } from "../../lib/layout";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { View } from "../../components/View";
import { useBrandingRefresh } from "../../config/BrandingContext";
import { useLocale, useT } from "../../i18n";
import { themeStyle } from "../../theme/palette";
import { LEGACY_THEME_IDS, OFFICIAL_THEME_IDS, type Theme, type ThemeMode } from "../../theme/themes";

const MODES: readonly ThemeMode[] = ["light", "dark"];

/** The eight series roles, as literal class names so the stylesheet builds them (no colour here). */
const BAR = [
  "bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4",
  "bg-chart-5", "bg-chart-6", "bg-chart-7", "bg-chart-8",
] as const;

interface Problem {
  path: string;
  code: string;
  message: string;
}

/** One theme in both modes (feature 051): the *whole* derivation, chrome band included, so a
 * preview cannot show something the application will not do. The variables are scoped to the card,
 * so the page keeps its own theme and no colour literal appears in the source. */
function ThemePreview({ theme }: { theme: Theme }) {
  const t = useT();
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(7.5rem,1fr))] gap-2" data-theme="preview">
      {MODES.map((mode) => (
        <div
          key={mode}
          style={themeStyle(theme, mode) as CSSProperties}
          className="overflow-hidden rounded-[var(--radius-card)] bg-[var(--c-canvas)] ring-1 ring-[var(--c-line)]"
          data-theme-preview={mode}
        >
          {/* The band the header wears, so the identity reads at a glance. */}
          <div className="preview-band h-6 w-full" aria-hidden />
          <div className="p-2">
            <div className="rounded-[var(--radius-card)] border-[length:var(--card-border)] border-[var(--c-line)] bg-[var(--c-surface)] p-1.5">
              <div className="flex items-baseline gap-1.5">
                <span className="text-[length:var(--kpi-numeral-lg)] font-bold tabular-nums text-[var(--c-ink)]">
                  1.284
                </span>
                <span className="rounded-full bg-[var(--c-success-soft)] px-1.5 text-[10px] font-semibold text-[var(--c-success)]">
                  +12,4 %
                </span>
              </div>
              <div className="mt-1 flex items-center gap-1" aria-hidden>
                <span className="rounded-[var(--radius-button)] bg-[var(--c-primary)] px-1.5 py-0.5 text-[9px] font-semibold text-[var(--c-on-primary)]">
                  ▸
                </span>
                <span className="rounded-[var(--radius-button)] border border-[var(--c-line-strong)] px-1.5 py-0.5 text-[9px] text-[var(--c-ink-3)]">
                  ▸
                </span>
              </div>
            </div>
            <div className="mt-1.5 flex items-end gap-1" aria-hidden>
              {[10, 16, 13, 20, 17].map((height, index) => (
                <span key={index} className={`w-2 rounded-sm ${BAR[index % BAR.length]}`} style={{ height }} />
              ))}
            </div>
            <p className="mt-1 text-[10px] text-[var(--c-ink-muted)]">
              {mode === "light" ? t.appearance.lightPreview : t.appearance.darkPreview}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Administración → Apariencia (030, widened by 047): the installation's theme library — the ones
 * the product ships, the ones uploaded here and the ones a project brought — plus the upload. */
export function Appearance() {
  const t = useT();
  const { locale } = useLocale();
  const toast = useToast();
  const refreshBranding = useBrandingRefresh();
  const [library, setLibrary] = useState<ThemeLibrary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [yaml, setYaml] = useState("");
  const [problems, setProblems] = useState<Problem[]>([]);
  const [conflict, setConflict] = useState<{ id: string; version: number } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setLibrary(await api.get<ThemeLibrary>("/api/admin/themes"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const nameOf = (row: ThemeRow) => (locale === "en" ? row.name_en : row.name);

  const apply = async (row: ThemeRow) => {
    setBusy(row.id);
    setError(null);
    try {
      // Persist first, then repaint: the confirmation is shown only once the server has stored the
      // choice, and the whole application re-themes from the refreshed config with no reload.
      await api.put("/api/admin/settings/theme", { theme_id: row.id });
      await refreshBranding();
      await load();
      toast(t.appearance.applied.replace("{name}", nameOf(row)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    } finally {
      setBusy(null);
    }
  };

  const remove = async (row: ThemeRow) => {
    if (!window.confirm(t.appearance.deleteConfirm.replace("{name}", nameOf(row)))) return;
    setBusy(row.id);
    setError(null);
    try {
      await api.del(`/api/admin/themes/${encodeURIComponent(row.id)}`);
      toast(t.appearance.deleted);
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.code === "theme_in_use") {
        const used = (e.details.reports as string[] | undefined) ?? [];
        setError(t.appearance.deleteRefused.replace("{reports}", used.join(", ")));
      } else {
        setError(e instanceof ApiError ? e.message : t.common.unexpected);
      }
    } finally {
      setBusy(null);
    }
  };

  const openUpload = async (source?: ThemeRow) => {
    setProblems([]);
    setConflict(null);
    setUploadOpen(true);
    if (!source) {
      setYaml("");
      return;
    }
    // A duplicate starts from the author's own file (the download endpoint), so the edit is YAML
    // like any other theme; if the file cannot be read the tokens are still there as JSON.
    try {
      const response = await fetch(`/api/admin/themes/${source.id}/download`, {
        credentials: "same-origin",
      });
      setYaml(response.ok ? await response.text() : JSON.stringify(source.tokens, null, 2));
    } catch {
      setYaml(JSON.stringify(source.tokens, null, 2));
    }
  };

  const submit = async (replace: boolean) => {
    setSaving(true);
    setProblems([]);
    setError(null);
    try {
      const path = replace ? "/api/admin/themes?replace=true" : "/api/admin/themes";
      await api.post(path, { yaml });
      toast(t.appearance.uploaded);
      setUploadOpen(false);
      setYaml("");
      setConflict(null);
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.code === "theme_invalid") {
        setProblems((e.details.problems as Problem[] | undefined) ?? []);
      } else if (e instanceof ApiError && e.code === "theme_exists") {
        setConflict({ id: String(e.details.id ?? ""), version: Number(e.details.version ?? 1) });
      } else {
        setError(e instanceof ApiError ? e.message : t.common.unexpected);
      }
    } finally {
      setSaving(false);
    }
  };

  const chooseFile = async (file: File | undefined) => {
    if (!file) return;
    setYaml(await file.text());
    setProblems([]);
    setConflict(null);
  };

  /** The one-line identity of a theme the product ships; an uploaded one has none. */
  const identityOf = (row: ThemeRow): string | null => {
    const texts = t.palette as unknown as Record<string, string | undefined>;
    return texts[`${row.id}Text`] ?? null;
  };

  // The official order is the product's own (Clásico, Impacto, Elegante, Contraste), not the
  // alphabetical order the library endpoint returns.
  const rank = (id: string) => {
    const index = (OFFICIAL_THEME_IDS as readonly string[]).indexOf(id);
    return index === -1 ? OFFICIAL_THEME_IDS.length : index;
  };
  const official = (library?.themes ?? [])
    .filter((row) => (OFFICIAL_THEME_IDS as readonly string[]).includes(row.id))
    .sort((a, b) => rank(a.id) - rank(b.id));
  const legacy = (library?.themes ?? []).filter((row) =>
    !(OFFICIAL_THEME_IDS as readonly string[]).includes(row.id));
  const legacyHint = (LEGACY_THEME_IDS as readonly string[]).length > 0;

  const originLabel: Record<ThemeOrigin, string> = {
    builtin: t.appearance.originBuiltin,
    upload: t.appearance.originUpload,
    project: t.appearance.originProject,
  };

  const card = (row: ThemeRow) => {
    const installed = library?.installation === row.id;
    const identity = identityOf(row);
    return (
      <Card
        key={row.id}
        className={`flex h-full flex-col ${CARD_PAD} ${installed ? "ring-2 ring-primary" : ""}`}
        data-theme-card={row.id}
        data-installed={installed ? "true" : "false"}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{nameOf(row)}</p>
            <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
              <Badge tone={row.origin === "builtin" ? "gray" : "blue"}>{originLabel[row.origin]}</Badge>
              <span>{t.appearance.version.replace("{version}", String(row.version))}</span>
              <span className="font-mono text-[11px]">{row.id}</span>
            </p>
          </div>
          {installed ? (
            <span className="flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">
              <Check className="h-4 w-4" aria-hidden />
              {t.appearance.current}
            </span>
          ) : null}
        </div>

        {identity ? <p className="mt-2 text-xs leading-snug text-ink-muted">{identity}</p> : null}

        <div className="mt-3">
          <ThemePreview theme={row.tokens} />
        </div>

        <div className="mt-auto flex flex-wrap items-center gap-2 pt-3">
          <Button
            variant={installed ? "secondary" : "primary"}
            loading={busy === row.id}
            disabled={installed}
            icon={<Palette className="h-4 w-4" aria-hidden />}
            onClick={() => void apply(row)}
          >
            {installed ? t.appearance.inUse : t.appearance.apply}
          </Button>
          <IconButton
            aria-label={`${t.appearance.download} ${nameOf(row)}`}
            icon={<Download className="h-4 w-4" aria-hidden />}
            onClick={() => window.open(`/api/admin/themes/${row.id}/download`, "_blank")}
          />
          <IconButton
            aria-label={`${t.appearance.duplicate} ${nameOf(row)}`}
            icon={<Copy className="h-4 w-4" aria-hidden />}
            onClick={() => void openUpload(row)}
          />
          {row.origin === "builtin" ? null : (
            <IconButton
              aria-label={`${t.appearance.delete} ${nameOf(row)}`}
              icon={<Trash2 className="h-4 w-4" aria-hidden />}
              tone="danger"
              onClick={() => void remove(row)}
            />
          )}
        </div>
      </Card>
    );
  };

  return (
    <div className={PAGE_STACK}>
      <BackLink to="/admin" />
      <PageHeader title={t.appearance.title} subtitle={t.appearance.subtitle} />
      {/* Feature 061: the guide explains the file a theme is, so a person can ask their own AI for
          one instead of starting from an empty YAML. */}
      <p className="-mt-2 text-sm">
        <Link
          to="/ayuda?tema=temas"
          className="inline-flex min-h-tap items-center gap-1.5 font-semibold text-accent hover:underline"
        >
          {t.appearance.writeWithAi}
          <span aria-hidden>→</span>
        </Link>
      </p>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {!library ? (
        <div role="status" className="flex justify-center py-12 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-ink sm:text-lg">{t.appearance.library}</h2>
            <Button
              variant="primary"
              icon={<Upload className="h-5 w-5" aria-hidden />}
              onClick={() => void openUpload()}
            >
              {t.appearance.upload}
            </Button>
          </div>

          {library.themes.length === 0 ? (
            <EmptyState title={t.appearance.library}>{t.appearance.uploadHint}</EmptyState>
          ) : null}

          {/* Feature 051: the four identities first, then everything else the installation can
              still use — a report may name any of them, and a legacy choice keeps working. */}
          <section aria-labelledby="official-themes">
            <h3 id="official-themes" className="section-title mb-2 text-sm uppercase tracking-wide text-ink-muted">
              {t.appearance.officialGroup}
            </h3>
            {/* One column on a phone, two on a tablet, three when the container is wide enough to
                keep the preview readable. */}
            <div className={CARD_GRID_3} data-theme-grid>
              {official.map((row) => card(row))}
            </div>
          </section>

          {legacy.length > 0 ? (
            <section aria-labelledby="other-themes" className="mt-6">
              <h3 id="other-themes" className="section-title mb-1 text-sm uppercase tracking-wide text-ink-muted">
                {t.appearance.compatGroup}
              </h3>
              <p className="mb-2 text-xs text-ink-muted">
                {legacyHint ? t.appearance.compatHint : null}
              </p>
              <div className={CARD_GRID_3} data-theme-grid>
                {legacy.map((row) => card(row))}
              </div>
            </section>
          ) : null}
        </>
      )}

      <View
        open={uploadOpen}
        title={t.appearance.uploadTitle}
        onClose={() => setUploadOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setUploadOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              loading={saving}
              disabled={!yaml.trim() || !!conflict}
              icon={<Plus className="h-5 w-5" aria-hidden />}
              onClick={() => void submit(false)}
            >
              {t.appearance.upload}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">{t.appearance.uploadHint}</p>
          <label className="block text-sm font-semibold text-ink-2" htmlFor="theme-yaml">
            {t.appearance.pasteLabel}
          </label>
          <textarea
            id="theme-yaml"
            value={yaml}
            onChange={(event) => {
              setYaml(event.target.value);
              setProblems([]);
              setConflict(null);
            }}
            spellCheck={false}
            rows={12}
            className="w-full rounded-xl border border-transparent bg-field px-4 py-3 font-mono text-sm text-ink focus:outline-none focus:ring-2 focus:ring-field-focus"
          />
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-semibold text-accent">
            <Upload className="h-4 w-4" aria-hidden />
            {t.appearance.chooseFile}
            <input
              type="file"
              accept=".yaml,.yml,.json"
              className="sr-only"
              onChange={(event) => void chooseFile(event.target.files?.[0])}
            />
          </label>

          {conflict ? (
            <Alert tone="warning">
              <p>{t.appearance.replaceQuestion
                .replace("{id}", conflict.id)
                .replace("{version}", String(conflict.version))}</p>
              <div className="mt-2">
                <Button variant="danger" loading={saving} onClick={() => void submit(true)}>
                  {t.appearance.replace}
                </Button>
              </div>
            </Alert>
          ) : null}

          {problems.length > 0 ? (
            <Alert tone="error">
              <p className="font-semibold">{t.appearance.problems}</p>
              <ul className="mt-1 space-y-1 font-mono text-xs">
                {problems.map((problem) => (
                  <li key={`${problem.path}-${problem.code}`} data-theme-problem={problem.code}>
                    {problem.path}: {problem.message}
                  </li>
                ))}
              </ul>
            </Alert>
          ) : null}
        </div>
      </View>
    </div>
  );
}
