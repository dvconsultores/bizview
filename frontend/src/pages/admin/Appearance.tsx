import { Check, Copy, Download, Palette, Plus, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { api, ApiError } from "../../api/client";
import type { ThemeLibrary, ThemeOrigin, ThemeRow } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { BackLink } from "../../components/BackLink";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { IconButton } from "../../components/IconButton";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { View } from "../../components/View";
import { useLocale, useT } from "../../i18n";
import { variablesForTokens } from "../../theme/palette";
import { deriveTokens, type Theme, type ThemeMode } from "../../theme/themes";

const MODES: readonly ThemeMode[] = ["light", "dark"];

interface Problem {
  path: string;
  code: string;
  message: string;
}

/** One theme in both modes. The variables are scoped to the card, so the page keeps its own
 * palette and no colour literal appears in the source. */
function ThemePreview({ tokens }: { tokens: Theme }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-2" data-theme="preview">
      {MODES.map((mode) => {
        const style = Object.fromEntries(
          Object.entries(variablesForTokens(deriveTokens(tokens, mode))).map(([name, value]) => [
            `--c-${name}`,
            value,
          ]),
        ) as CSSProperties;
        return (
          <div
            key={mode}
            style={style}
            className="rounded-lg border border-line bg-[var(--c-kpi-surface)] p-3"
            data-theme-preview={mode}
          >
            <div className="flex items-baseline gap-2">
              <span className="text-lg font-bold tabular-nums text-[var(--c-kpi-text)]">1.284</span>
              <span className="rounded-full bg-[var(--c-kpi-delta-bg-positive)] px-2 py-0.5 text-[10px] font-semibold text-[var(--c-chart-positive)]">
                +12,4 %
              </span>
            </div>
            <div className="mt-2 flex items-end gap-1" aria-hidden>
              {[14, 22, 18, 28, 24].map((height, index) => (
                <span
                  key={index}
                  className="w-3 rounded-sm"
                  style={{ height, backgroundColor: `var(--c-chart-${(index % 8) + 1})` }}
                />
              ))}
            </div>
            <svg viewBox="0 0 120 24" className="mt-1 h-6 w-full" aria-hidden>
              <polyline
                points="0,18 20,14 40,16 60,8 80,10 100,4 120,6"
                fill="none"
                stroke="var(--c-chart-2)"
                strokeWidth="2"
              />
            </svg>
            <p className="mt-1 text-[10px] text-[var(--c-chart-label)]">
              {mode === "light" ? t.appearance.lightPreview : t.appearance.darkPreview}
            </p>
          </div>
        );
      })}
    </div>
  );
}

/** Administración → Apariencia (030, widened by 047): the installation's theme library — the ones
 * the product ships, the ones uploaded here and the ones a project brought — plus the upload. */
export function Appearance() {
  const t = useT();
  const { locale } = useLocale();
  const toast = useToast();
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
      await api.put("/api/admin/settings/theme", { theme_id: row.id });
      toast(t.appearance.applied.replace("{name}", nameOf(row)));
      // The installation default changed: reload so every page applies it from /api/config.
      window.setTimeout(() => window.location.reload(), 600);
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

  const originLabel: Record<ThemeOrigin, string> = {
    builtin: t.appearance.originBuiltin,
    upload: t.appearance.originUpload,
    project: t.appearance.originProject,
  };

  return (
    <div className="max-w-4xl space-y-5">
      <BackLink to="/admin" />
      <PageHeader title={t.appearance.title} subtitle={t.appearance.subtitle} />

      {error ? <Alert tone="error">{error}</Alert> : null}

      {!library ? (
        <div role="status" className="flex justify-center py-12 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">{t.appearance.library}</h2>
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

          <div className="grid gap-4 sm:grid-cols-2" data-theme-grid>
            {library.themes.map((row) => {
              const installed = library.installation === row.id;
              return (
                <Card key={row.id} className={`p-4 ${installed ? "ring-2 ring-primary" : ""}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-ink">{nameOf(row)}</p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
                        <Badge tone={row.origin === "builtin" ? "gray" : "blue"}>
                          {originLabel[row.origin]}
                        </Badge>
                        <span>{t.appearance.version.replace("{version}", String(row.version))}</span>
                        <span className="font-mono text-[11px]">{row.id}</span>
                      </p>
                    </div>
                    {installed ? (
                      <span className="flex items-center gap-1 text-xs font-semibold text-primary">
                        <Check className="h-4 w-4" aria-hidden />
                        {t.appearance.current}
                      </span>
                    ) : null}
                  </div>

                  <div className="mt-3">
                    <ThemePreview tokens={row.tokens} />
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button
                      variant={installed ? "secondary" : "primary"}
                      loading={busy === row.id}
                      disabled={installed}
                      icon={<Palette className="h-4 w-4" aria-hidden />}
                      onClick={() => void apply(row)}
                    >
                      {t.appearance.apply}
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
            })}
          </div>
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
