import { Wand2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";
import { api, ApiError } from "../../api/client";
import type { Role, User } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Alert } from "../../components/Alert";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { CopyButton, SecretBox } from "../../components/CopyButton";
import { Input } from "../../components/Input";
import { PageHeader } from "../../components/PageHeader";
import { PasswordRules } from "../../components/PasswordRules";
import { RoleTiles } from "../../components/RoleTiles";
import { View } from "../../components/View";
import { useT } from "../../i18n";
import { generatePassword, passwordProblem } from "../../lib/password";

type FieldErrors = { full_name?: string; email?: string; temporary_password?: string };
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function UserForm() {
  const t = useT();
  const { user: me } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const nameRef = useRef<HTMLInputElement>(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("user");
  const [pw, setPw] = useState(() => generatePassword());
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<{ user: User; password: string } | null>(null);
  const [goToId, setGoToId] = useState<User["id"] | null>(null);

  useEffect(() => nameRef.current?.focus(), []);

  useEffect(() => {
    if (goToId !== null && !((location.state as { view?: string[] } | null)?.view?.length)) {
      navigate(`/admin/usuarios/${goToId}`, { replace: true });
    }
  }, [goToId, location.state, navigate]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting) return;
    const found: FieldErrors = {};
    if (!fullName.trim()) found.full_name = t.common.required;
    if (!email.trim()) found.email = t.common.required;
    else if (!EMAIL_RE.test(email.trim())) found.email = t.admin.userPages.invalidEmail;
    const problem = passwordProblem(pw, email);
    if (!pw) found.temporary_password = t.common.required;
    else if (problem) found.temporary_password = t.password.problems[problem];
    setErrors(found);
    if (found.full_name || found.email || found.temporary_password) return;

    setSubmitting(true);
    setFormError(null);
    try {
      const user = await api.post<User>("/api/admin/users", {
        email: email.trim(),
        full_name: fullName.trim(),
        role,
        temporary_password: pw,
      });
      setCreated({ user, password: pw });
    } catch (err) {
      if (!(err instanceof ApiError) || err.code === "network") {
        setFormError(t.errors.network);
      } else if (err.status === 409) {
        setErrors({ email: err.message });
      } else if (err.status === 422 && Object.keys(err.fields).length) {
        const mapped: FieldErrors = {};
        for (const [key, code] of Object.entries(err.fields)) {
          if (key === "temporary_password") mapped.temporary_password = t.password.problems[code] ?? err.message;
          else if (key === "email" || key === "full_name") mapped[key] = err.message;
        }
        setErrors(mapped);
        if (!Object.keys(mapped).length) setFormError(err.message);
      } else {
        setFormError(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const createAnother = () => {
    setCreated(null);
    setFullName("");
    setEmail("");
    setRole("user");
    setPw(generatePassword());
    setErrors({});
    window.setTimeout(() => nameRef.current?.focus(), 0);
  };

  const goToUser = () => {
    if (!created) return;
    // Clear created first so View pops its history entry, then navigate after the pop completes.
    setGoToId(created.user.id);
    setCreated(null);
  };

  return (
    <div>
      <Breadcrumbs back="/admin/usuarios" items={[{ label: t.nav.admin, to: "/admin" }, { label: t.nav.users, to: "/admin/usuarios" }, { label: t.admin.newUser }]} />
      <PageHeader title={t.admin.newUser} />

      <Card tone="accent" className="p-5 sm:p-6">
        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          {formError ? <Alert tone="error">{formError}</Alert> : null}
          <div className="space-y-5 xl:grid xl:grid-cols-2 xl:gap-5 xl:space-y-0">
            <Input
              ref={nameRef}
              label={t.admin.fullName}
              required
              autoComplete="off"
              value={fullName}
              maxLength={120}
              onChange={(e) => setFullName(e.target.value)}
              error={errors.full_name}
            />
            <Input
              label={t.admin.email}
              type="email"
              required
              inputMode="email"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={email}
              maxLength={254}
              onChange={(e) => setEmail(e.target.value)}
              error={errors.email}
            />
          </div>
          <RoleTiles
            value={role}
            onChange={setRole}
            adminDisabled={!me?.is_superuser}
            hint={me?.is_superuser ? undefined : t.admin.onlySuperAdmins}
          />
          <div className="space-y-2">
            <Input
              label={t.admin.tempPassword}
              type="text"
              required
              autoComplete="off"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              error={errors.temporary_password}
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
            <PasswordRules password={pw} email={email} />
          </div>
          <Button type="submit" loading={submitting} className="w-full sm:w-auto">
            {t.admin.create}
          </Button>
        </form>
      </Card>

      <View
        open={!!created}
        title={t.admin.created}
        onClose={goToUser}
        footer={
          <>
            <Button variant="secondary" onClick={createAnother}>
              {t.admin.userPages.createAnother}
            </Button>
            <Button onClick={goToUser}>{t.admin.userPages.viewUser}</Button>
          </>
        }
      >
        {created ? (
          <div className="space-y-3">
            <p className="break-all font-semibold text-ink">{created.user.email}</p>
            <SecretBox value={created.password} />
            <CopyButton text={created.password} />
            <p className="text-sm text-ink-soft">{t.admin.tempPasswordHint}</p>
          </div>
        ) : null}
      </View>
    </div>
  );
}
