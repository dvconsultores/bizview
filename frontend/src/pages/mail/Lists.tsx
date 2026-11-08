import { useEffect, useState } from "react";
import { List, Lock, Pencil, Plus, RefreshCw, Search } from "lucide-react";
import { mail } from "../../api/mail";
import type { MailList, MailListsPage } from "../../api/types";
import { useT } from "../../i18n";
import { errorText } from "../../lib/sharing";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Input } from "../../components/Input";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { ListEditor } from "./ListEditor";

const DEFAULT_MAX_MEMBERS = 1000;

/**
 * Feature 058: the lists page. `/mis-listas` shows the lists the user may use — theirs plus the
 * shared ones, read-only when they cannot edit them; `/admin/listas-de-correo` shows every list and
 * is where shared and role lists are created.
 */
export function Lists({ admin = false }: { admin?: boolean }) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [data, setData] = useState<MailListsPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ list: MailList | null } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(id);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    mail
      .listLists("all", debouncedQuery || undefined)
      .then((page) => {
        if (cancelled) return;
        setData(page);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(errorText(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, attempt]);

  const maxMembers = data?.max_members ?? DEFAULT_MAX_MEMBERS;

  const onSaved = (saved: MailList) => {
    setEditing(null);
    setData((current) =>
      current
        ? {
            ...current,
            items: [
              ...current.items.filter((item) => item.id !== saved.id),
              saved,
            ].sort((a, b) => a.name.localeCompare(b.name)),
          }
        : current,
    );
    setAttempt((n) => n + 1);
  };

  const onDeleted = (id: number) => {
    setEditing(null);
    setData((current) =>
      current ? { ...current, items: current.items.filter((item) => item.id !== id) } : current,
    );
  };

  return (
    <div className="pb-16 sm:pb-0">
      {/* Feature 061: the same back control every other page of the app carries. */}
      <Breadcrumbs
        back={admin ? "/admin" : "/"}
        items={
          admin
            ? [{ label: t.nav.admin, to: "/admin" }, { label: t.mailLists.adminTitle }]
            : [{ label: t.mailLists.title }]
        }
      />
      <PageHeader
        title={admin ? t.mailLists.adminTitle : t.mailLists.title}
        subtitle={admin ? t.mailLists.adminSubtitle : t.mailLists.subtitle}
        action={
          data && !editing ? (
            <Button
              variant="primary"
              icon={<Plus className="h-5 w-5" aria-hidden />}
              onClick={() => setEditing({ list: null })}
            >
              {t.mailLists.newList}
            </Button>
          ) : null
        }
      />

      <div className="space-y-5">
        <Input
          label={t.mailLists.search}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        {editing && (
          <ListEditor
            key={editing.list?.id ?? "new"}
            list={editing.list}
            maxMembers={maxMembers}
            canShare={data?.can_share ?? false}
            onSaved={onSaved}
            onDeleted={onDeleted}
            onCancel={() => setEditing(null)}
          />
        )}

        {error && (
          <Alert
            tone="error"
            action={
              <Button
                variant="secondary"
                icon={<RefreshCw className="h-5 w-5" aria-hidden />}
                onClick={() => setAttempt((n) => n + 1)}
              >
                {t.common.retry}
              </Button>
            }
          >
            {error}
          </Alert>
        )}

        {loading && !data ? (
          <div role="status" className="flex justify-center py-8 text-accent">
            <Spinner className="h-8 w-8" />
            <span className="sr-only">{t.common.loading}</span>
          </div>
        ) : data && data.items.length === 0 ? (
          <EmptyState icon={<List className="h-6 w-6" aria-hidden />} title={t.mailLists.empty}>
            {t.mailLists.emptyHint}
          </EmptyState>
        ) : (
          <ul className="space-y-3">
            {(data?.items ?? []).map((item) => (
              <li key={item.id}>
                <Card className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="min-w-0 break-words font-semibold text-ink">
                          {item.name}
                        </p>
                        <Badge tone={item.visibility === "compartida" ? "accent" : "gray"}>
                          {item.visibility === "compartida"
                            ? t.mailLists.shared
                            : t.mailLists.personal}
                        </Badge>
                        {item.kind === "role" && (
                          <Badge tone="blue">
                            {t.mailLists.roleKind(
                              t.roles[item.role ?? "user"] ?? item.role ?? "",
                            )}
                          </Badge>
                        )}
                        {!item.editable && (
                          <Badge tone="gray" icon={<Lock className="h-3.5 w-3.5" aria-hidden />}>
                            {t.mailLists.readOnly}
                          </Badge>
                        )}
                      </div>
                      {item.description && (
                        <p className="mt-1 text-sm text-ink-muted">{item.description}</p>
                      )}
                      <p className="mt-1 text-sm text-ink-muted">
                        {t.mailLists.count(item.count, maxMembers)}
                        {item.paused > 0 && ` · ${t.mailLists.pausedCount(item.paused)}`}
                        {" · "}
                        {t.mailLists.owner(item.owner.name)}
                      </p>
                    </div>
                    <Button
                      variant="secondary"
                      icon={
                        item.editable ? (
                          <Pencil className="h-5 w-5" aria-hidden />
                        ) : (
                          <Search className="h-5 w-5" aria-hidden />
                        )
                      }
                      onClick={() => setEditing({ list: item })}
                    >
                      {item.editable ? t.mailLists.open : t.common.show}
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
