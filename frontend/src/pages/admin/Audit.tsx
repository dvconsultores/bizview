import { BackLink } from "../../components/BackLink";
import { History, KeyRound, LayoutDashboard, Lock, LogOut, ShieldCheck, User as UserIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, qs } from "../../api/client";
import type { AuditItem } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { CodeChip } from "../../components/CodeChip";
import { EmptyState } from "../../components/EmptyState";
import { PageHeader } from "../../components/PageHeader";
import { Select } from "../../components/Select";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";

const DANGER = ["login_failed", "login_locked", "user_deactivated", "dashboard_revoked"];

function iconFor(kind: string) {
  if (kind === "login_locked") return Lock;
  if (kind === "logout") return LogOut;
  if (kind.indexOf("login_") === 0 || kind.indexOf("password_") === 0) return KeyRound;
  if (kind.indexOf("user_") === 0 || kind === "role_changed") return UserIcon;
  if (kind.indexOf("dashboard_") === 0) return LayoutDashboard;
  if (kind.indexOf("superuser_") === 0) return ShieldCheck;
  return History;
}

function show(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

interface AuditPage {
  items: AuditItem[];
  next_before: number | null;
}

export function Audit() {
  const t = useT();
  const [kind, setKind] = useState("");
  const [items, setItems] = useState<AuditItem[] | null>(null);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    setError(null);
    api
      .get<AuditPage>(`/api/admin/audit${qs({ kind, limit: 50 })}`)
      .then((page) => {
        if (cancelled) return;
        setItems(page.items);
        setNextBefore(page.next_before);
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
  }, [kind, attempt]);

  const loadMore = async () => {
    if (!items || nextBefore === null) return;
    setLoadingMore(true);
    try {
      const page = await api.get<AuditPage>(`/api/admin/audit${qs({ kind, limit: 50, before: nextBefore })}`);
      setItems([...items, ...page.items]);
      setNextBefore(page.next_before);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div>
      <BackLink to="/admin" />
      <PageHeader title={t.admin.auditTitle} subtitle={t.admin.auditSubtitle} />

      <Card className="mb-5 p-4 sm:p-5">
        <div className="sm:max-w-xs">
          <Select label={t.admin.auditKind} value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">{t.admin.all}</option>
            {Object.keys(t.audit).map((k) => (
              <option key={k} value={k}>
                {t.audit[k]}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {error ? (
        <Alert tone="error" action={<Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>{t.common.retry}</Button>}>
          {error}
        </Alert>
      ) : items === null ? (
        <div role="status" className="space-y-3">
          <span className="sr-only">{t.common.loading}</span>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-card bg-fill/70" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={<History className="h-7 w-7" aria-hidden />} title={t.admin.auditEmpty} />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-line">
            {items.map((item) => {
              const Icon = iconFor(item.kind);
              const danger = DANGER.indexOf(item.kind) !== -1;
              const detail = Object.keys(item.detail ?? {});
              return (
                <li key={item.id} className="flex gap-3 p-4 sm:px-5">
                  <span
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                      danger ? "bg-danger-soft text-danger" : "bg-accent-soft text-accent"
                    }`}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                      <p className="font-semibold text-ink">{t.audit[item.kind] ?? item.kind}</p>
                      <p className="text-xs text-ink-muted whitespace-nowrap">
                        {formatDateTime(item.occurred_at)}
                      </p>
                    </div>
                    <p className="mt-1 break-all text-sm text-ink-muted">
                      {item.actor?.email ?? t.admin.systemActor}
                      {item.target && item.target.email !== item.actor?.email ? ` → ${item.target.email}` : ""}
                    </p>
                    {item.ip ? (
                      <div className="mt-1.5">
                        <CodeChip>{item.ip}</CodeChip>
                      </div>
                    ) : null}
                    {detail.length ? (
                      <dl className="mt-2 rounded-xl bg-subtle px-3 py-2 text-xs text-ink-soft break-all">
                        {detail.map((key) => (
                          <div key={key}>
                            <dt className="inline font-medium">{key}: </dt>
                            <dd className="inline">{show(item.detail[key])}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      {items && nextBefore !== null && !error ? (
        <div className="mt-5 flex justify-center">
          <Button variant="secondary" onClick={loadMore} loading={loadingMore}>
            {t.admin.loadMore}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
