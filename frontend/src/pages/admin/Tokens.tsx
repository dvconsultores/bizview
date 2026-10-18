import { Ban, KeyRound, Plus } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api/client";
import type { AccessToken } from "../../api/types";
import { Alert } from "../../components/Alert";
import { BackLink } from "../../components/BackLink";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { CodeChip } from "../../components/CodeChip";
import { CopyButton } from "../../components/CopyButton";
import { EmptyState } from "../../components/EmptyState";
import { IconButton } from "../../components/IconButton";
import { Input } from "../../components/Input";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { rich, useT } from "../../i18n";
import { formatDate, formatDateTime } from "../../lib/format";

export function Tokens() {
  const t = useT();
  const toast = useToast();
  const [items, setItems] = useState<AccessToken[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [days, setDays] = useState("90");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .get<{ items: AccessToken[] }>("/api/tokens")
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected));
  }, [t]);
  useEffect(load, [load]);

  const create = (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    api
      .post<AccessToken & { token: string }>("/api/tokens", {
        name,
        scopes: ["describe"],
        expires_days: Number(days) || 90,
      })
      .then((r) => {
        setCreated(r.token);
        setName("");
        load();
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t.common.unexpected))
      .finally(() => setBusy(false));
  };
  const revoke = (id: number) => {
    api
      .del(`/api/tokens/${id}`)
      .then(() => {
        toast(t.admin.tokens.revoked);
        load();
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t.common.unexpected));
  };

  return (
    <div className="space-y-4">
      <BackLink to="/admin" />
      <PageHeader
        title={t.admin.tokens.title}
        subtitle={rich(t.admin.tokens.subtitle, {
          name: <code>bizview describe</code>,
        })}
        badge={
          items ? (
            <Badge tone="accent">
              {t.admin.tokens.count(items.length)}
            </Badge>
          ) : null
        }
      />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {created ? (
        <Alert tone="success">
          <p className="font-semibold">{t.admin.tokens.copyNow}</p>
          <div className="mt-2 flex flex-wrap items-center">
            <code className="mr-2 break-all rounded-lg border border-line bg-surface px-2 py-1 font-mono text-sm font-semibold text-ink">
              {created}
            </code>
            <CopyButton text={created} />
          </div>
          <p className="mt-2 [overflow-wrap:anywhere]">
            {t.admin.tokens.onYourMachine}{" "}
            <code className="break-all">
              export BIZVIEW_URL={window.location.origin} BIZVIEW_TOKEN=…
            </code>
          </p>
        </Alert>
      ) : null}

      <Card tone="accent" className="p-4 sm:p-5">
        <h2 className="mb-3 text-base font-semibold text-ink">{t.admin.tokens.newToken}</h2>
        <form onSubmit={create} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input
            label={t.admin.tokens.nameLabel}
            required
            maxLength={60}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="sm:col-span-2"
            hint={t.admin.tokens.nameHint}
          />
          <Input
            label={t.admin.tokens.expiresLabel}
            type="number"
            min={1}
            max={365}
            required
            value={days}
            onChange={(e) => setDays(e.target.value)}
          />
          <div className="sm:col-span-3 sm:flex sm:justify-end">
            <Button
              type="submit"
              loading={busy}
              icon={<Plus className="h-5 w-5" aria-hidden />}
            >
              {t.admin.tokens.create}
            </Button>
          </div>
        </form>
      </Card>

      {items === null ? (
        <div role="status" className="flex justify-center py-8 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={<KeyRound className="h-7 w-7" aria-hidden />} title={t.admin.tokens.empty} />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-line">
            {items.map((tk) => (
              <li
                key={tk.id}
                className="flex flex-wrap items-center justify-between gap-3 p-4 sm:px-5"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                    <KeyRound className="h-5 w-5" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="font-semibold text-ink [overflow-wrap:anywhere]">{tk.name}</p>
                    <p className="mt-0.5 text-sm text-ink-muted">
                      {t.admin.tokens.expiresLastUsed(formatDate(tk.expires_at), formatDateTime(tk.last_used_at))}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {tk.scopes.map((scope) => (
                        <CodeChip key={scope}>{scope}</CodeChip>
                      ))}
                    </div>
                  </div>
                </div>
                {tk.active ? (
                  <div className="flex items-center gap-2">
                    <Badge tone="green">{t.admin.tokens.active}</Badge>
                    <IconButton
                      tone="danger"
                      aria-label={t.admin.tokens.revokeLabel(tk.name)}
                      icon={<Ban className="h-5 w-5" aria-hidden />}
                      onClick={() => revoke(tk.id)}
                    />
                  </div>
                ) : (
                  <Badge tone="gray">{tk.revoked_at ? t.admin.tokens.revokedBadge : t.admin.tokens.expiredBadge}</Badge>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
