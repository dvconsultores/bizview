import { Clock, KeyRound, ShieldOff, Unlink, User as UserIcon, UserCheck, UserX, Wand2 } from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { api, ApiError } from "../../api/client";
import type { Role, User, UserDashboard, UserDetail as Detail } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Alert } from "../../components/Alert";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { CopyButton, SecretBox } from "../../components/CopyButton";
import { EmptyState } from "../../components/EmptyState";
import { Input } from "../../components/Input";
import { PasswordRules } from "../../components/PasswordRules";
import { RoleTiles } from "../../components/RoleTiles";
import { Spinner } from "../../components/Spinner";
import { Switch } from "../../components/Switch";
import { useToast } from "../../components/Toast";
import { RoleBadge, StatusBadges } from "../../components/UserBadges";
import { View } from "../../components/View";
import { t, useT } from "../../i18n";
import { formatDate, formatDateTime, initials } from "../../lib/format";
import { generatePassword } from "../../lib/password";

const message = (err: unknown) => (err instanceof ApiError ? err.message : t.common.unexpected);
const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.indexOf(x) !== -1);
const grantedCodes = (ds: UserDashboard[]) => ds.filter((d) => d.granted).map((d) => d.code);

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-5 sm:p-6">
      <h2 className="mb-4 text-lg font-semibold text-ink">{title}</h2>
      {children}
    </Card>
  );
}

function DetailsForm({ user, canManage, canChangeRole, onSaved }: { user: User; canManage: boolean; canChangeRole: boolean; onSaved: (u: User) => void }) {
  const t = useT();
  const toast = useToast();
  const [fullName, setFullName] = useState(user.full_name);
  const [role, setRole] = useState<Role>(user.role);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setFullName(user.full_name);
    setRole(user.role);
  }, [user]);

  const changed = fullName.trim() !== user.full_name || role !== user.role;
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!changed || !fullName.trim()) return;
    const patch: { full_name?: string; role?: Role } = {};
    if (fullName.trim() !== user.full_name) patch.full_name = fullName.trim();
    if (role !== user.role) patch.role = role;
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.patch<User>(`/api/admin/users/${user.id}`, patch));
      toast(t.admin.saved);
    } catch (err) {
      setError(message(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      {error ? <Alert tone="error">{error}</Alert> : null}
      <Input
        label={t.admin.fullName}
        value={fullName}
        maxLength={120}
        disabled={!canManage}
        onChange={(e) => setFullName(e.target.value)}
        error={canManage && !fullName.trim() ? t.common.required : null}
      />
      <RoleTiles value={role} onChange={setRole} disabled={!canChangeRole} hint={canManage && !canChangeRole ? t.admin.onlySuperAdmins : undefined} />
      <Button type="submit" loading={saving} disabled={!canManage || !changed || !fullName.trim()} className="w-full sm:w-auto">
        {t.common.save}
      </Button>
    </form>
  );
}

function AccessForm({ userId, dashboards, canManage, onSaved }: { userId: number; dashboards: UserDashboard[]; canManage: boolean; onSaved: (d: UserDashboard[]) => void }) {
  const t = useT();
  const toast = useToast();
  const [codes, setCodes] = useState<string[]>(() => grantedCodes(dashboards));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setCodes(grantedCodes(dashboards)), [dashboards]);

  const changed = !sameSet(codes, grantedCodes(dashboards));
  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await api.put<{ dashboards: UserDashboard[] }>(`/api/admin/users/${userId}/dashboards`, { codes });
      onSaved(res.dashboards);
      toast(t.admin.accessSaved);
    } catch (err) {
      setError(message(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      {error ? (
        <div className="mb-3">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}
      <ul className="-my-1 divide-y divide-line-soft">
        {dashboards.map((d) => {
          const on = codes.indexOf(d.code) !== -1;
          return (
            <li key={d.code} className="flex min-h-[56px] items-center justify-between py-1">
              <span className="mr-3 min-w-0">
                <span className="block truncate font-medium text-ink">{d.name}</span>
                {d.status === "coming_soon" ? (
                  <span className="mt-1 inline-flex">
                    <Badge tone="amber" icon={<Clock className="h-3.5 w-3.5" aria-hidden />}>{t.home.comingSoon}</Badge>
                  </span>
                ) : null}
              </span>
              <Switch
                checked={on}
                label={d.name}
                disabled={!canManage}
                onChange={(v) => setCodes(v ? [...codes, d.code] : codes.filter((c) => c !== d.code))}
              />
            </li>
          );
        })}
      </ul>
      <Button onClick={save} loading={saving} disabled={!canManage || !changed} className="mt-4 w-full sm:w-auto">
        {t.common.save}
      </Button>
    </div>
  );
}

function ResetPasswordView({ user, open, onClose, onDone }: { user: User; open: boolean; onClose: () => void; onDone: () => void }) {
  const t = useT();
  const toast = useToast();
  const [pw, setPw] = useState("");
  const [done, setDone] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setPw(generatePassword());
      setDone(false);
      setError(null);
    }
  }, [open]);

  const close = () => {
    setPw("");
    setDone(false);
    setError(null);
    onClose();
  };

  const confirm = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (saving || !pw) return;
    setSaving(true);
    setError(null);
    try {
      await api.post(`/api/admin/users/${user.id}/password`, { temporary_password: pw });
      setDone(true);
      toast(t.admin.resetDone);
      onDone();
    } catch (err) {
      const code = err instanceof ApiError ? err.fields.temporary_password : undefined;
      setError(code ? t.password.problems[code] ?? message(err) : message(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <View
      open={open}
      title={t.admin.resetPassword}
      autoFocus
      onClose={close}
      footer={done ? <Button onClick={close}>{t.common.close}</Button> : undefined}
    >
      {done ? (
        <div className="space-y-3">
          <Alert tone="success">{t.admin.resetDone}</Alert>
          <p className="text-sm font-medium text-ink-3">{t.admin.tempPassword}</p>
          <SecretBox value={pw} />
          <div className="flex flex-wrap">
            <CopyButton text={pw} />
          </div>
          <p className="text-sm text-ink-soft">{t.admin.tempPasswordHint}</p>
        </div>
      ) : (
        <form onSubmit={confirm} noValidate className="space-y-4">
          <p>{t.admin.resetConfirm}</p>
          {error ? <Alert tone="error">{error}</Alert> : null}
          <Input
            label={t.admin.tempPassword}
            type="text"
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            hint={t.admin.tempPasswordHint}
            trailing={
              <button
                type="button"
                onClick={() => setPw(generatePassword())}
                className="inline-flex min-h-tap items-center rounded-lg px-3 text-sm font-semibold text-accent-strong hover:bg-accent-soft"
              >
                <Wand2 className="mr-1 h-4 w-4" aria-hidden />
                {t.admin.generate}
              </button>
            }
            className="[&_input]:pr-32 [&_input]:font-mono"
          />
          <PasswordRules password={pw} email={user.email} />
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={close}>{t.common.cancel}</Button>
            <Button type="submit" loading={saving} disabled={!pw}>{t.admin.resetPassword}</Button>
          </div>
        </form>
      )}
    </View>
  );
}

export function UserDetail() {
  const t = useT();
  const { id = "" } = useParams();
  const { user: me } = useAuth();
  const toast = useToast();
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [resetOpen, setResetOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [mfaOpen, setMfaOpen] = useState(false);
  const [tgOpen, setTgOpen] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .get<Detail>(`/api/admin/users/${encodeURIComponent(id)}`)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err : new ApiError(0, "error", t.common.unexpected)));
    return () => {
      cancelled = true;
    };
  }, [id, attempt]);

  if (error && !data) {
    return (
      <div>
        <Breadcrumbs back="/admin/usuarios" items={[]} />
        {error.status === 404 || error.status === 422 ? (
          <EmptyState icon={<UserIcon className="h-7 w-7" aria-hidden />} title={t.admin.userPages.notFound} />
        ) : (
          <Alert tone="error" action={<Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>{t.common.retry}</Button>}>
            {error.message}
          </Alert>
        )}
      </div>
    );
  }
  if (!data || !me) {
    return (
      <div className="flex justify-center py-16 text-accent" role="status">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  const u = data.user;
  // Mirrors the server rules (backend/app/services/users.py can_manage); the server re-checks.
  const isSelf = me.id === u.id;
  const canManage = !u.is_superuser && !isSelf && me.role === "admin" && (u.role === "user" || me.is_superuser);
  const canChangeRole = canManage && me.is_superuser;
  const setUser = (user: User) => setData((d) => (d ? { ...d, user } : d));
  const canResetMfa = canManage && me.is_superuser && u.mfa_enabled;

  const clearActionError = () => setActionError(null);

  const unlinkTelegram = async () => {
    setToggling(true);
    setActionError(null);
    try {
      await api.del(`/api/admin/users/${u.id}/telegram`);
      setTgOpen(false);
      toast(t.telegram.adminUnlinked);
      setAttempt((n) => n + 1);
    } catch (err) {
      setActionError(message(err));
    } finally {
      setToggling(false);
    }
  };

  const resetMfa = async () => {
    setToggling(true);
    setActionError(null);
    try {
      await api.post(`/api/admin/users/${u.id}/mfa/reset`);
      setMfaOpen(false);
      toast(t.mfa.resetDone);
      setAttempt((n) => n + 1);
    } catch (err) {
      setActionError(message(err));
    } finally {
      setToggling(false);
    }
  };

  const toggleActive = async () => {
    setToggling(true);
    setActionError(null);
    try {
      const updated = await api.patch<User>(`/api/admin/users/${u.id}`, { is_active: !u.is_active });
      setUser(updated);
      setConfirmOpen(false);
      toast(updated.is_active ? t.admin.reactivated : t.admin.deactivated);
    } catch (err) {
      setActionError(message(err));
    } finally {
      setToggling(false);
    }
  };

  return (
    <div className="space-y-5">
      <Breadcrumbs back="/admin/usuarios" items={[{ label: t.nav.admin, to: "/admin" }, { label: t.nav.users, to: "/admin/usuarios" }, { label: u.full_name }]} />

      <Card tone="accent" className="p-6 sm:p-8">
        <div className="flex items-center">
          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary-hover text-2xl font-bold text-on-primary" aria-hidden>
            {initials(u.full_name)}
          </span>
          <div className="ml-4 min-w-0">
            <h1 className="break-words text-2xl font-bold tracking-tight text-ink sm:text-3xl">{u.full_name}</h1>
            <p className="break-all text-ink-muted">{u.email}</p>
            <div className="-mt-0.5 flex flex-wrap">
              <span className="mr-1.5 mt-1.5 inline-flex">
                <RoleBadge user={u} />
              </span>
              <StatusBadges user={u} />
            </div>
          </div>
        </div>
        <dl className="mt-5 grid grid-cols-1 gap-3 border-t border-line pt-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-ink-soft">{t.admin.lastLogin}</dt>
            <dd className="font-medium text-ink">{u.last_login_at ? formatDateTime(u.last_login_at) : t.admin.never}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">{t.admin.createdAt}</dt>
            <dd className="font-medium text-ink">{formatDate(u.created_at)}</dd>
          </div>
        </dl>
      </Card>

      {isSelf ? (
        <Alert tone="info" action={<Link to="/perfil" className="font-semibold underline">{t.nav.profile}</Link>}>
          {t.admin.self}
        </Alert>
      ) : !canManage ? (
        <Alert tone="info">{t.admin.cannotManage}</Alert>
      ) : null}

      <Section title={t.admin.details}>
        <DetailsForm user={u} canManage={canManage} canChangeRole={canChangeRole} onSaved={setUser} />
      </Section>

      <Section title={t.admin.access}>
        {u.role === "admin" ? (
          <Alert tone="info">{t.admin.adminSeesAll}</Alert>
        ) : (
          <AccessForm
            userId={u.id}
            dashboards={data.dashboards}
            canManage={canManage}
            onSaved={(dashboards) => setData((d) => (d ? { ...d, dashboards } : d))}
          />
        )}
      </Section>

      {canManage ? (
        <Card className="p-5 sm:p-6">
          {actionError ? (
            <div className="mb-3">
              <Alert tone="error">{actionError}</Alert>
            </div>
          ) : null}
          <div className="space-y-3 sm:flex sm:space-x-3 sm:space-y-0">
            <Button variant="secondary" className="w-full sm:w-auto" icon={<KeyRound className="h-5 w-5" aria-hidden />} onClick={() => setResetOpen(true)}>
              {t.admin.resetPassword}
            </Button>
            {canResetMfa ? (
              <Button variant="secondary" className="w-full sm:w-auto" icon={<ShieldOff className="h-5 w-5" aria-hidden />} onClick={() => { clearActionError(); setMfaOpen(true); }}>
                {t.mfa.reset}
              </Button>
            ) : null}
            {canManage && data.telegram_linked ? (
              <Button variant="secondary" className="w-full sm:w-auto" icon={<Unlink className="h-5 w-5" aria-hidden />} onClick={() => { clearActionError(); setTgOpen(true); }}>
                {t.telegram.adminUnlink}
              </Button>
            ) : null}
            {u.is_active ? (
              <Button variant="danger" className="w-full sm:w-auto" icon={<UserX className="h-5 w-5" aria-hidden />} onClick={() => { clearActionError(); setConfirmOpen(true); }}>
                {t.admin.deactivate}
              </Button>
            ) : (
              <Button variant="secondary" className="w-full sm:w-auto" icon={<UserCheck className="h-5 w-5" aria-hidden />} onClick={() => { clearActionError(); setConfirmOpen(true); }}>
                {t.admin.reactivate}
              </Button>
            )}
          </div>
        </Card>
      ) : null}

      <View open={tgOpen} title={t.telegram.adminUnlink} onClose={() => { setTgOpen(false); clearActionError(); }}
        footer={
          <>
            <Button variant="secondary" onClick={() => { setTgOpen(false); clearActionError(); }}>{t.common.cancel}</Button>
            <Button variant="danger" onClick={unlinkTelegram} loading={toggling}>{t.telegram.adminUnlink}</Button>
          </>
        }>
        <div className="space-y-3">
          {actionError ? <Alert tone="error">{actionError}</Alert> : null}
          <p>{t.telegram.adminUnlinkConfirm}</p>
        </div>
      </View>

      <View open={mfaOpen} title={t.mfa.reset} onClose={() => { setMfaOpen(false); clearActionError(); }}
        footer={
          <>
            <Button variant="secondary" onClick={() => { setMfaOpen(false); clearActionError(); }}>{t.common.cancel}</Button>
            <Button variant="danger" onClick={resetMfa} loading={toggling}>{t.mfa.reset}</Button>
          </>
        }>
        <div className="space-y-3">
          {actionError ? <Alert tone="error">{actionError}</Alert> : null}
          <p>{t.mfa.resetConfirm}</p>
        </div>
      </View>

      <ResetPasswordView user={u} open={resetOpen} onClose={() => setResetOpen(false)} onDone={() => setAttempt((n) => n + 1)} />

      <View
        open={confirmOpen}
        title={u.is_active ? t.admin.deactivate : t.admin.reactivate}
        onClose={() => { setConfirmOpen(false); clearActionError(); }}
        footer={
          <>
            <Button variant="secondary" onClick={() => { setConfirmOpen(false); clearActionError(); }}>{t.common.cancel}</Button>
            <Button variant={u.is_active ? "danger" : "primary"} onClick={toggleActive} loading={toggling}>
              {u.is_active ? t.admin.deactivate : t.admin.reactivate}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {actionError ? <Alert tone="error">{actionError}</Alert> : null}
          <p>
            <span className="font-semibold">{u.full_name}</span>
            {u.is_active ? ` — ${t.admin.deactivateConfirm}` : ""}
          </p>
        </div>
      </View>
    </div>
  );
}
