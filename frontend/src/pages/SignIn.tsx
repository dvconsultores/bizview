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
import { useT, type Catalogue } from "../i18n";
import { SourceFooter } from "../components/SourceFooter";
import { TelegramSignInPanel } from "../components/TelegramSignInPanel";
import { GoogleSignInButton } from "../components/GoogleSignInButton";

type FieldErrors = { email?: string; password?: string };

/** Feature 027/054: one sentence for every refusal — an unknown identity, a domain, an inactive
 * account and a provider failure all read the same — and the reason lives only in the audit log. A
 * cancelled consent is the one exception: the person did it, and saying so is not a leak. */
function googleErrorMessage(code: string, t: Catalogue): string {
  return code === "denied" ? t.google.errors.cancelled : t.google.errors.failed;
}

export function SignIn() {
  const t = useT();
  const { user, loading, login, completeMfa, refresh, setUser } = useAuth();
  const { product_name, organization_name, telegram_sign_in, google_auth } = useBranding();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");
  const googleErrorCode = searchParams.get("google_error");
  const googleError = googleErrorCode ? googleErrorMessage(googleErrorCode, t) : null;
  const navigate = useNavigate();
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<{ tone: "error" | "warning"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // The Google callback that still owes the second factor comes back with ?mfa=1 and a pending
  // session: the existing code prompt takes over, exactly as after a password sign-in returning "mfa".
  const [step, setStep] = useState<"password" | "code" | "telegram">(
    searchParams.get("mfa") === "1" ? "code" : "password",
  );

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
    <div className="relative flex min-h-dvh scroll-pb-32 flex-col bg-canvas lg:min-h-screen lg:flex-row-reverse">
      {/* Feature 059: the hero is the page's own header on a phone (compact, no overlap with the
          card) and the half-screen banner it always was from 1024 px up. The language switch sits
          under the header on the right, never over the product name. */}
      <header className="relative overflow-hidden bg-chrome-gradient px-4 pb-6 pt-safe text-on-chrome sm:px-6 lg:flex lg:min-h-screen lg:w-1/2 lg:flex-col lg:justify-center lg:px-16 lg:pb-0">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/15 opacity-50" />
        <div className="relative mx-auto w-full max-w-md lg:mx-0">
          <div className="flex items-center gap-3 pt-3 lg:pt-0">
            <Logo inverted className="h-10 w-10 shrink-0 lg:h-12 lg:w-12" />
            <div className="min-w-0">
              <p className="truncate text-lg font-bold leading-tight lg:text-3xl">{product_name}</p>
              {organization_name ? (
                <p className="truncate text-xs text-on-primary lg:text-base">{organization_name}</p>
              ) : null}
            </div>
          </div>
          <p className="mt-2 hidden text-sm font-medium text-on-chrome [@media(min-height:600px)]:block lg:mt-10 lg:text-3xl lg:leading-tight">
            {t.signIn.heroTagline}
          </p>
        </div>
        {/* feature 022: device choice before sign-in, US1 AC3 */}
        <div className="relative mt-3 flex justify-end text-ink lg:hidden">
          <LanguageSwitcher compact />
        </div>
      </header>

      <main className="flex flex-1 justify-center px-4 pb-8 pt-4 sm:px-4 lg:items-center lg:py-12">
        <Card tone="accent" className="h-fit w-full max-w-md rounded-2xl p-4 shadow-raised sm:p-6 lg:p-8">
          <h1 className="text-xl font-bold leading-tight tracking-tight text-ink sm:text-3xl">{t.signIn.title}</h1>
          <p className="mb-4 mt-1 text-sm text-ink-muted sm:mb-6 sm:text-base">{t.signIn.subtitle}</p>

          {searchParams.get("expirada") === "1" && !formError ? (
            <div className="mb-4">
              <Alert tone="info">{t.signIn.sessionEnded}</Alert>
            </div>
          ) : null}
          {googleError && !formError ? (
            <div className="mb-4">
              <Alert tone="error">{googleError}</Alert>
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
              autoComplete="email"
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
            <Button type="submit" block className="max-sm:min-h-[48px]" loading={submitting}>
              {submitting ? t.signIn.submitting : t.signIn.submit}
            </Button>
          </form>
          {telegram_sign_in || google_auth ? (
            <>
              <div className="my-4 flex items-center" aria-hidden>
                <span className="h-px flex-1 bg-line" />
                <span className="px-3 text-sm text-ink-soft">{t.signIn.or}</span>
                <span className="h-px flex-1 bg-line" />
              </div>
              {/* Feature 059: two providers share one row on a phone (icon + short label); from
                  640 px up each takes its own row, so "Continuar con Google" stays on one line.
                  A single enabled provider takes the whole width. */}
              <div
                className={
                  google_auth && telegram_sign_in
                    ? "grid grid-cols-2 gap-2 sm:grid-cols-1 sm:gap-3"
                    : "space-y-3"
                }
              >
                {google_auth ? (
                  <GoogleSignInButton
                    compact={google_auth && telegram_sign_in}
                    label={google_auth && telegram_sign_in ? t.google.signInShort : undefined}
                    onClick={() => {
                      setFormError(null);
                      // A normal navigation: the endpoint sets the state cookie and 302s to Google.
                      window.location.assign("/api/auth/google/start");
                    }}
                  />
                ) : null}
                {telegram_sign_in ? (
                  <Button variant="secondary" block
                    className={google_auth ? "gap-2 px-2 text-sm sm:gap-3 sm:px-4 sm:text-base" : "gap-3 px-4"}
                    icon={<Send className="h-5 w-5 shrink-0" aria-hidden />}
                    aria-label={t.telegram.signIn}
                    onClick={() => { setFormError(null); setStep("telegram"); }}>
                    {google_auth ? (
                      <>
                        <span className="max-sm:hidden">{t.telegram.signIn}</span>
                        <span className="sm:hidden">{t.telegram.signInShort}</span>
                      </>
                    ) : (
                      t.telegram.signIn
                    )}
                  </Button>
                ) : null}
              </div>
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
