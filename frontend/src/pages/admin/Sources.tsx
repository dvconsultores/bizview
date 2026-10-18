import { BackLink } from "../../components/BackLink";
import { AlertTriangle, CheckCircle2, ChevronRight, Clock, Database, DatabaseZap, Globe, Network, Plus, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError } from "../../api/client";
import type { DataSource, SourceKind, SourceTypes } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { CodeChip } from "../../components/CodeChip";
import { EmptyState } from "../../components/EmptyState";
import { IconButton } from "../../components/IconButton";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";

export const KIND_ICONS: Record<SourceKind, typeof Database> = { postgresql: Database, soap: Network, rest: Globe, supabase: DatabaseZap };



function Status({ s }: { s: DataSource }) {
  const t = useT();
  const T = t.admin.sources;
  if (!s.enabled) return <Badge tone="gray">{T.disabled}</Badge>;
  if (s.imported) return <Badge tone="amber" icon={<AlertTriangle className="h-3.5 w-3.5" aria-hidden />}>{T.imported}</Badge>;
  if (!s.last_test) return <Badge tone="gray" icon={<Clock className="h-3.5 w-3.5" aria-hidden />}>{T.untested}</Badge>;
  return s.last_test.ok ? (
    <Badge tone="green" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>{T.ok}</Badge>
  ) : (
    <Badge tone="red" icon={<XCircle className="h-3.5 w-3.5" aria-hidden />}>{T.failed}</Badge>
  );
}

export function Sources() {
  const t = useT();
  const T = t.admin.sources;
  const navigate = useNavigate();
  const [items, setItems] = useState<DataSource[] | null>(null);
  const [types, setTypes] = useState<SourceTypes | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    Promise.all([api.get<{ items: DataSource[] }>("/api/sources"), api.get<SourceTypes>("/api/sources/types")])
      .then(([list, ty]) => {
        if (cancelled) return;
        setItems(list.items);
        setTypes(ty);
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  return (
    <div className="space-y-5">
      <BackLink to="/admin" />
      <PageHeader
        title={T.title}
        subtitle={T.subtitle}
        badge={
          items ? (
            <Badge tone="accent">
              {T.count(items.length)}
            </Badge>
          ) : null
        }
      />

      <Card className="p-4 sm:p-5">
        <div className="flex justify-end">
          <Button
            icon={<Plus className="h-5 w-5" aria-hidden />}
            onClick={() => navigate("/admin/fuentes/nueva")}
          >
            {T.add}
          </Button>
        </div>
      </Card>

      {error ? (
        <Alert tone="error" action={<Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>{t.common.retry}</Button>}>
          {error}
        </Alert>
      ) : items === null ? (
        <div role="status" className="flex justify-center py-12 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={<Database className="h-7 w-7" aria-hidden />} title={T.empty}>
          {T.emptyText}
        </EmptyState>
      ) : (
        <>
          <ul className="space-y-3 md:hidden">
            {items.map((s) => {
              const Icon = KIND_ICONS[s.kind] ?? Database;
              return (
                <li key={s.id}>
                  <Link
                    to={`/admin/fuentes/${s.id}`}
                    className="flex min-h-tap items-center rounded-card border border-line bg-surface p-4 hover:border-line-accent"
                  >
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                      <Icon className="h-5 w-5" aria-hidden />
                    </span>
                    <span className="ml-3 min-w-0 flex-1">
                      <span className="block truncate font-semibold text-ink">{s.name}</span>
                      <span className="block truncate text-sm text-ink-muted">{types?.[s.kind]?.label ?? s.kind}</span>
                      <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1.5">
                        <Status s={s} />
                        {s.direct_reports ? <Badge tone="blue">{t.directSources.badge}</Badge> : null}
                        {s.last_test ? (
                          <span className="text-xs text-ink-muted whitespace-nowrap">
                            {formatDateTime(s.last_test.at)}
                          </span>
                        ) : null}
                      </span>
                    </span>
                    <ChevronRight className="ml-2 h-5 w-5 shrink-0 text-ink-faint" aria-hidden />
                  </Link>
                </li>
              );
            })}
          </ul>

          <Card className="hidden overflow-hidden md:block">
            <table className="w-full">
              <thead className="bg-subtle">
                <tr>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {T.colName}
                  </th>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {T.colKind}
                  </th>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {T.colStatus}
                  </th>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {T.colLastTest}
                  </th>
                  <th scope="col" className="px-2 py-3">
                    <span className="sr-only">{T.colActions}</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {items.map((s) => {
                  const Icon = KIND_ICONS[s.kind] ?? Database;
                  return (
                    <tr
                      key={s.id}
                      onClick={() => navigate(`/admin/fuentes/${s.id}`)}
                      className="cursor-pointer hover:bg-subtle"
                    >
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                            <Icon className="h-5 w-5" aria-hidden />
                          </span>
                          <div className="min-w-0">
                            <Link
                              to={`/admin/fuentes/${s.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="block truncate font-semibold text-ink hover:text-accent"
                            >
                              {s.name}
                            </Link>
                            <div className="truncate text-sm text-ink-muted">
                              {types?.[s.kind]?.label ?? s.kind}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <CodeChip>{s.kind}</CodeChip>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Status s={s} />
                          {s.direct_reports ? <Badge tone="blue">{t.directSources.badge}</Badge> : null}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-sm text-ink-muted">
                        {s.last_test ? formatDateTime(s.last_test.at) : "—"}
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        <IconButton
                          to={`/admin/fuentes/${s.id}`}
                          tabIndex={-1}
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Abrir ${s.name}`}
                          icon={<ChevronRight className="h-5 w-5" aria-hidden />}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
