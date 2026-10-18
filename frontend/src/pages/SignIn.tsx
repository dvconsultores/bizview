import { Send } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { ApiError } from "../api/client";
import type { User } from "../api/types";
import { MFA_SETUP_PATH, safeNext, useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { Logo } from "../components/Logo";
import { PasswordField } from "../components/PasswordField";
import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";
import { SourceFooter } from "../components/SourceFooter";
import { TelegramSignInPanel } from "../components/TelegramSignInPanel";

type FieldErrors = { email?: string; password?: string };

export function SignIn() {
  const t = useT();
  const { user, loading, login, completeMfa, refresh, setUser } = useAuth();
  const { product_name, organization_name, telegram_sign_in } = useBranding();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");
  const navigate = useNavigate();
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<{ tone: "error" | "warning"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<"password" | "code" | "telegram">("password");

  useEffect(() => {
    if (!loading && !user) emailRef.current?.focus();
  }, [loading, user]);

  if (!loading && user) {
    return <Navigate to={user.must_change_password ? "/cambiar-clave" : safeNext(next)} replace />;
  }

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting) return;
    const found: FieldErrors = {};
    if (!email.trim()) found.email = t.common.required;
    if (!password) found.password = t.common.required;
    setErrors(found);
    if (found.email || found.password) {
      (found.email ? emailRef : passwordRef).current?.focus();
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const signedIn = await login(email.trim(), password);
      if (signedIn === "mfa") {
        setPassword("");
        setStep("code");
        return;
      }
      navigate(signedIn.must_change_password ? "/cambiar-clave" : safeNext(next), { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setFormError({ tone: "error", text: t.signIn.invalid });
      } else if (err instanceof ApiError && err.status === 423) {
        const minutes = Math.max(1, Math.ceil((err.retryAfter ?? 60) / 60));
        setFormError({ tone: "warning", text: t.signIn.locked(minutes) });
      } else if (err instanceof ApiError && err.code !== "network") {
        setFormError({ tone: "error", text: err.message });
      } else {
        setFormError({ tone: "error", text: t.errors.network });
      }
      setPassword("");
      passwordRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-canvas lg:flex-row-reverse">
      {/* feature 022: device choice before sign-in, US1 AC3 */}
      <div className="absolute right-4 top-4 z-10 text-ink">
        <LanguageSwitcher compact />
      </div>
      <div className="relative overflow-hidden bg-brand-gradient px-6 pb-16 pt-safe text-white lg:flex lg:min-h-screen lg:w-1/2 lg:flex-col lg:justify-center lg:px-16 lg:pb-0">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/15 opacity-50" />
        <div className="relative mx-auto w-full max-w-md pt-10 lg:mx-0 lg:pt-0">
          <div className="flex items-center">
            <Logo inverted className="h-12 w-12 shrink-0" />
            <div className="ml-3 min-w-0">
              <p className="truncate text-2xl font-bold lg:text-3xl">{product_name}</p>
              {organization_name ? <p className="truncate text-on-primary">{organization_name}</p> : null}
            </div>
          </div>
          <p className="mt-6 text-lg font-medium text-brand-50 lg:mt-10 lg:text-3xl lg:leading-tight">{t.signIn.heroTagline}</p>
        </div>
      </div>

      <main className="-mt-8 flex flex-1 justify-center px-4 pb-8 lg:mt-0 lg:items-center lg:py-12">
        <Card tone="accent" className="h-fit w-full max-w-md p-6 shadow-raised sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">{t.signIn.title}</h1>
          <p className="mb-6 mt-1 text-ink-muted">{t.signIn.subtitle}</p>

          {searchParams.get("expirada") === "1" && !formError ? (
            <div className="mb-4">
              <Alert tone="info">{t.signIn.sessionEnded}</Alert>
            </div>
          ) : null}
          {formError ? (
            <div className="mb-4">
              <Alert tone={formError.tone}>{formError.text}</Alert>
            </div>
          ) : null}

          {step === "code" ? (
            <MfaStep
              onDone={(u) => navigate(u.must_change_password ? "/cambiar-clave" : safeNext(next), { replace: true })}
              onBack={() => {
                setStep("password");
                setFormError(null);
              }}
              complete={completeMfa}
            />
          ) : step === "telegram" ? (
            <TelegramSignInPanel
              onSignedIn={(u) => {
                setUser(u);
                navigate(u.must_change_password ? "/cambiar-clave" : safeNext(next), { replace: true });
              }}
              onMfa={(enrollmentRequired) => {
                if (enrollmentRequired) void refresh().then(() => navigate(MFA_SETUP_PATH, { replace: true }));
                else setStep("code");
              }}
              onCancel={() => setStep("password")}
            />
          ) : (
          <>
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <Input
              ref={emailRef}
              label={t.signIn.email}
              type="email"
              autoComplete="username"
              inputMode="email"
              autoCapitalize="none"
              spellCheck={false}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={errors.email}
            />
            <PasswordField
              ref={passwordRef}
              label={t.signIn.password}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={errors.password}
            />
            <Button type="submit" block loading={submitting}>
              {submitting ? t.signIn.submitting : t.signIn.submit}
            </Button>
          </form>
          {telegram_sign_in ? (
            <>
              <div className="my-4 flex items-center" aria-hidden>
                <span className="h-px flex-1 bg-line" />
                <span className="px-3 text-sm text-ink-soft">{t.telegram.or}</span>
                <span className="h-px flex-1 bg-line" />
              </div>
              <Button variant="secondary" block icon={<Send className="h-5 w-5" aria-hidden />}
                onClick={() => { setFormError(null); setStep("telegram"); }}>
                {t.telegram.signIn}
              </Button>
            </>
          ) : null}
          </>
          )}

          <p className="mt-5 text-sm text-ink-soft">{t.signIn.forgot}</p>
        </Card>
      </main>

      <SourceFooter className="pb-safe px-4 py-4 lg:fixed lg:bottom-0 lg:left-0 lg:w-1/2" />
    </div>
  );
}

function MfaStep({
  complete,
  onDone,
  onBack,
}: {
  complete: (input: { code?: string; recovery_code?: string }) => Promise<User>;
  onDone: (u: User) => void;
  onBack: () => void;
}) {
  const t = useT();
  const [recovery, setRecovery] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState<{ tone: "error" | "warning"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), [recovery]);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (busy || !value.trim()) return;
    setBusy(true);
    setError(null);
    try {
      onDone(await complete(recovery ? { recovery_code: value.trim() } : { code: value.replace(/\D/g, "") }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) {
        const minutes = Math.max(1, Math.ceil((err.retryAfter ?? 60) / 60));
        setError({ tone: "warning", text: t.signIn.locked(minutes) });
      } else if (err instanceof ApiError && err.code === "unauthenticated") {
        onBack(); // pending step expired: start again
      } else if (err instanceof ApiError && err.status === 429) {
        setError({ tone: "warning", text: err.message });
      } else {
        setError({ tone: "error", text: t.mfa.invalidCode });
      }
      setValue("");
      ref.current?.focus();
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">{t.mfa.stepTitle}</h2>
        <p className="mt-1 text-sm text-ink-muted">{recovery ? t.mfa.recoveryCode : t.mfa.stepSubtitle}</p>
      </div>
      {error ? <Alert tone={error.tone}>{error.text}</Alert> : null}
      <Input
        ref={ref}
        label={recovery ? t.mfa.recoveryCode : t.mfa.code}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        inputMode={recovery ? "text" : "numeric"}
        autoComplete="one-time-code"
        autoCapitalize={recovery ? "characters" : "none"}
        spellCheck={false}
        maxLength={recovery ? 11 : 6}
        className="font-mono"
      />
      <Button type="submit" block loading={busy}>
        {t.mfa.verify}
      </Button>
      <div className="flex flex-wrap justify-between">
        <button type="button" onClick={() => { setRecovery(!recovery); setValue(""); setError(null); }}
          className="min-h-tap text-sm font-medium text-accent hover:underline">
          {recovery ? t.mfa.useApp : t.mfa.useRecovery}
        </button>
        <button type="button" onClick={onBack} className="min-h-tap text-sm font-medium text-ink-muted hover:underline">
          {t.mfa.backToPassword}
        </button>
      </div>
    </form>
  );
}
