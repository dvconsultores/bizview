import { BackLink } from "../../components/BackLink";
import { ChevronRight, Plus, Search, UserPlus, Users as UsersIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError, qs } from "../../api/client";
import type { Page, User } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button, ButtonLink } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { IconButton } from "../../components/IconButton";
import { Input } from "../../components/Input";
import { PageHeader } from "../../components/PageHeader";
import { RoleBadge, StatusBadges } from "../../components/UserBadges";
import { useT } from "../../i18n";
import { formatDateTime, initials } from "../../lib/format";

type RoleFilter = "" | "admin" | "user";
type StatusFilter = "" | "active" | "inactive" | "locked";
const PAGE = 50;

function Chips<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0" role="group" aria-label={label}>
      <div className="flex space-x-2 whitespace-nowrap py-0.5">
        {options.map(([v, text]) => (
          <button
            key={v || "all"}
            type="button"
            aria-pressed={value === v}
            onClick={() => onChange(v)}
            className={`min-h-tap rounded-full px-4 text-sm font-medium transition-colors ${
              value === v
                ? "bg-primary text-on-primary shadow-sm"
                : "bg-field text-ink-2 hover:bg-subtle"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Users() {
  const t = useT();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [role, setRole] = useState<RoleFilter>("");
  const [status, setStatus] = useState<StatusFilter>("");
  const [items, setItems] = useState<User[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQ(q.trim()), 300);
    return () => window.clearTimeout(id);
  }, [q]);

  const url = (offset: number) => `/api/admin/users${qs({ q: debouncedQ, role, status, limit: PAGE, offset })}`;

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    setError(null);
    api
      .get<Page<User>>(url(0))
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, role, status, attempt]);

  const loadMore = async () => {
    if (!items) return;
    setLoadingMore(true);
    try {
      const data = await api.get<Page<User>>(url(items.length));
      setItems([...items, ...data.items]);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="pb-16 sm:pb-0">
      <BackLink to="/admin" />
      <PageHeader
        title={t.admin.usersTitle}
        subtitle={t.admin.usersSubtitle}
        badge={
          items ? (
            <span aria-live="polite">
              <Badge tone="accent">{t.admin.total(total)}</Badge>
            </span>
          ) : null
        }
      />

      <Link
        to="/admin/usuarios/nuevo"
        aria-label={t.admin.newUser}
        className="fixed bottom-24 right-4 z-20 inline-flex h-14 w-14 items-center justify-center rounded-full bg-primary text-on-primary shadow-raised hover:bg-primary-hover sm:hidden"
      >
        <Plus className="h-7 w-7" aria-hidden />
      </Link>

      <Card className="mb-5 p-4 sm:p-5">
        <div className="lg:flex lg:items-end lg:gap-4">
          <div className="lg:flex-1">
            <Input
              type="search"
              label={t.admin.search}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              autoComplete="off"
              enterKeyHint="search"
              trailing={<Search className="mr-3 h-5 w-5 text-ink-faint" aria-hidden />}
            />
          </div>
          <div className="hidden sm:mt-4 sm:flex sm:justify-end lg:mt-0">
            <ButtonLink
              to="/admin/usuarios/nuevo"
              icon={<UserPlus className="h-5 w-5" aria-hidden />}
            >
              {t.admin.newUser}
            </ButtonLink>
          </div>
        </div>
        <div className="mt-4 space-y-2 sm:flex sm:space-x-6 sm:space-y-0">
          <Chips<RoleFilter>
            label={t.admin.role}
            value={role}
            onChange={setRole}
            options={[["", t.admin.all], ["admin", t.roles.admin], ["user", t.roles.user]]}
          />
          <Chips<StatusFilter>
            label={t.admin.userPages.status}
            value={status}
            onChange={setStatus}
            options={[["", t.admin.all], ["active", t.status.active], ["inactive", t.status.inactive], ["locked", t.status.locked]]}
          />
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
        <EmptyState icon={<UsersIcon className="h-7 w-7" aria-hidden />} title={t.admin.none} />
      ) : (
        <>
          <ul className="space-y-3 md:hidden">
            {items.map((u) => (
              <li key={u.id}>
                <Link
                  to={`/admin/usuarios/${u.id}`}
                  className="flex min-h-tap items-center rounded-card border border-line bg-surface p-4 hover:border-line-accent"
                >
                  <span
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent"
                    aria-hidden
                  >
                    {initials(u.full_name)}
                  </span>
                  <span className="ml-3 min-w-0 flex-1">
                    <span className="block truncate font-semibold text-ink">{u.full_name}</span>
                    <span className="block truncate text-sm text-ink-muted">{u.email}</span>
                    <span className="-mt-0.5 flex flex-wrap">
                      <span className="mr-1.5 mt-1.5 inline-flex">
                        <RoleBadge user={u} />
                      </span>
                      <StatusBadges user={u} />
                    </span>
                  </span>
                  <ChevronRight className="ml-2 h-5 w-5 shrink-0 text-ink-faint" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>

          <Card className="hidden overflow-hidden md:block">
            <table className="w-full">
              <thead className="bg-subtle">
                <tr>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {t.admin.fullName}
                  </th>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {t.admin.role}
                  </th>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {t.admin.userPages.status}
                  </th>
                  <th scope="col" className="px-5 py-3 text-left text-xs font-semibold text-ink-muted">
                    {t.admin.lastLogin}
                  </th>
                  <th scope="col" className="px-2 py-3">
                    <span className="sr-only">{t.admin.userPages.actions}</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {items.map((u) => (
                  <tr
                    key={u.id}
                    onClick={() => navigate(`/admin/usuarios/${u.id}`)}
                    className="cursor-pointer hover:bg-subtle"
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent"
                          aria-hidden
                        >
                          {initials(u.full_name)}
                        </span>
                        <div className="min-w-0">
                          <Link
                            to={`/admin/usuarios/${u.id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="block truncate font-semibold text-ink hover:text-accent"
                          >
                            {u.full_name}
                          </Link>
                          <div className="max-w-[16rem] truncate text-sm text-ink-muted">{u.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <RoleBadge user={u} />
                    </td>
                    <td className="px-5 pb-3 pt-1.5">
                      <div className="flex flex-wrap">
                        <StatusBadges user={u} />
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-sm text-ink-muted">
                      {u.last_login_at ? formatDateTime(u.last_login_at) : t.admin.never}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <IconButton
                        to={`/admin/usuarios/${u.id}`}
                        tabIndex={-1}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Ver ${u.full_name}`}
                        icon={<ChevronRight className="h-5 w-5" aria-hidden />}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {items.length < total ? (
            <div className="mt-5 flex justify-center">
              <Button variant="secondary" onClick={loadMore} loading={loadingMore}>
                {t.admin.loadMore}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
