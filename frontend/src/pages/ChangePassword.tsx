import { ArrowLeft, LogOut } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Logo } from "../components/Logo";
import { PasswordField } from "../components/PasswordField";
import { PasswordRules } from "../components/PasswordRules";
import { useToast } from "../components/Toast";
import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";
import { passwordProblem } from "../lib/password";
import { SourceFooter } from "../components/SourceFooter";

type FieldErrors = { current?: string; newPw?: string; confirm?: string };

export function ChangePassword() {
  const t = useT();
  const { user, refresh, logout } = useAuth();
  const { product_name } = useBranding();
  const navigate = useNavigate();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<{ tone: "error" | "warning"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!user) return null;
  const forced = user.must_change_password;

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting) return;
    const found: FieldErrors = {};
    if (!current) found.current = t.common.required;
    if (!newPw) found.newPw = t.common.required;
    else {
      const problem = passwordProblem(newPw, user.email, current);
      if (problem) found.newPw = t.password.problems[problem];
    }
    if (!confirm) found.confirm = t.common.required;
    else if (confirm !== newPw) found.confirm = t.password.mismatch;
    setErrors(found);
    if (found.current || found.newPw || found.confirm) return;

    setSubmitting(true);
    setFormError(null);
    try {
      await api.post("/api/me/password", { current_password: current, new_password: newPw });
      await refresh();
      toast(t.password.success);
      navigate("/", { replace: true });
    } catch (err) {
      if (!(err instanceof ApiError) || err.code === "network") {
        setFormError({ tone: "error", text: t.errors.network });
      } else if (err.status === 401 && err.code === "invalid_credentials") {
        setErrors({ current: err.message });
      } else if (err.status === 423) {
        setFormError({ tone: "warning", text: err.message });
      } else if (err.status === 422 && err.fields.new_password) {
        setErrors({ newPw: t.password.problems[err.fields.new_password] ?? err.message });
      } else {
        setFormError({ tone: "error", text: err.message });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-canvas">
      <header className="bg-brand-gradient pt-safe text-white shadow-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex min-w-0 items-center">
            <Logo inverted className="h-8 w-8 shrink-0" />
            <span className="ml-3 truncate font-semibold">{product_name}</span>
          </div>
          {forced ? (
            <button
              type="button"
              onClick={() => void logout()}
              className="inline-flex min-h-tap items-center rounded-lg px-2 font-medium text-white hover:bg-white/10"
            >
              <LogOut className="mr-2 h-5 w-5" aria-hidden />
              {t.nav.signOut}
            </button>
          ) : (
            <Link to="/perfil" className="inline-flex min-h-tap items-center rounded-lg px-2 font-medium text-white hover:bg-white/10">
              <ArrowLeft className="mr-2 h-5 w-5" aria-hidden />
              {t.common.back}
            </Link>
          )}
        </div>
      </header>

      <main className="px-4 pb-10 pt-6">
        <Card tone="accent" className="mx-auto max-w-md p-6 shadow-raised sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">{forced ? t.password.forcedTitle : t.password.title}</h1>
          {forced ? (
            <div className="mt-3">
              <Alert tone="info">{t.password.forcedSubtitle}</Alert>
            </div>
          ) : null}
          {formError ? (
            <div className="mt-4">
              <Alert tone={formError.tone}>{formError.text}</Alert>
            </div>
          ) : null}

          <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
            <PasswordField
              label={forced ? t.password.currentTemporary : t.password.current}
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              error={errors.current}
            />
            <div className="space-y-2">
              <PasswordField
                label={t.password.new}
                autoComplete="new-password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                error={errors.newPw}
              />
              <PasswordRules password={newPw} email={user.email} current={current || undefined} />
            </div>
            <PasswordField
              label={t.password.confirm}
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              error={errors.confirm}
            />
            <Button type="submit" block loading={submitting}>
              {submitting ? t.common.saving : t.password.submit}
            </Button>
          </form>
        </Card>
      </main>
      <SourceFooter className="pb-safe px-4 pb-6" />
    </div>
  );
}
