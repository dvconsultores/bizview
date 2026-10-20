import { Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { projectsApi } from "../../api/projects";
import type { RunContract, RunProfile } from "../../api/types";
import { Alert } from "../../components/Alert";
import { BackLink } from "../../components/BackLink";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Input } from "../../components/Input";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { useT } from "../../i18n";

/** Feature 028 (US5): the saved run contracts. Using one still needs the step-up of a run. */
export function RunProfiles() {
  const t = useT();
  const toast = useToast();
  const [items, setItems] = useState<RunProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [applies, setApplies] = useState("1");
  const [previews, setPreviews] = useState("5");
  const [minutes, setMinutes] = useState("30");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    projectsApi
      .runProfiles()
      .then(setItems)
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected));
  }, [t]);
  useEffect(load, [load]);

  const create = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const contract: Partial<RunContract> = {
      stages: Number(applies) > 0 ? ["draft", "preview", "apply"] : ["draft", "preview"],
      limits: {
        tokens: 400000,
        previews: Number(previews) || 0,
        applies: Number(applies) || 0,
        wall_clock_seconds: Math.max(60, (Number(minutes) || 30) * 60),
      },
    };
    projectsApi
      .saveRunProfile({ name: name.trim(), contract })
      .then(() => {
        toast(t.assistant.runProfiles.saved);
        setName("");
        load();
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t.common.unexpected))
      .finally(() => setBusy(false));
  };

  const remove = (row: RunProfile) => {
    if (!window.confirm(t.assistant.runProfiles.confirmRemove.replace("{name}", row.name))) return;
    projectsApi
      .removeRunProfile(row.id)
      .then(() => {
        toast(t.assistant.runProfiles.removed);
        load();
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t.common.unexpected));
  };

  return (
    <div className="space-y-4">
      <BackLink to="/admin/ia" />
      <PageHeader
        title={t.assistant.runProfiles.title}
        subtitle={t.assistant.runProfiles.subtitle}
        badge={items ? <Badge tone="accent">{items.length}</Badge> : null}
      />
      {error ? <Alert tone="error">{error}</Alert> : null}

      <Card tone="accent" className="p-4 sm:p-5">
        <h2 className="mb-3 text-base font-semibold text-ink">
          {t.assistant.runProfiles.newProfile}
        </h2>
        <form onSubmit={create} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <Input
            label={t.assistant.runProfiles.name}
            required
            maxLength={60}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="sm:col-span-2"
          />
          <Input
            label={t.assistant.contract.applies}
            type="number"
            min={0}
            max={5}
            value={applies}
            onChange={(e) => setApplies(e.target.value)}
          />
          <Input
            label={t.assistant.contract.previews}
            type="number"
            min={0}
            max={20}
            value={previews}
            onChange={(e) => setPreviews(e.target.value)}
          />
          <Input
            label={t.assistant.contract.minutes}
            type="number"
            min={1}
            max={120}
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
          />
          <div className="sm:col-span-4 sm:flex sm:justify-end">
            <Button
              type="submit"
              loading={busy}
              disabled={!name.trim()}
              icon={<Plus className="h-5 w-5" aria-hidden />}
            >
              {t.assistant.runProfiles.newProfile}
            </Button>
          </div>
        </form>
      </Card>

      {items === null ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <EmptyState title={t.assistant.runProfiles.empty} />
      ) : (
        <ul className="divide-y divide-line rounded-2xl border border-line bg-surface">
          {items.map((row) => (
            <li key={row.id} className="flex items-center gap-3 px-4 py-3">
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
                {row.name}
              </span>
              <Button
                variant="danger-soft"
                size="sm"
                icon={<Trash2 className="h-4 w-4" aria-hidden />}
                onClick={() => remove(row)}
              >
                {t.assistant.runProfiles.remove}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
