import { BackLink } from "../components/BackLink";
import { Download, KeyRound, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { MfaSetup } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { CopyButton, SecretBox } from "../components/CopyButton";
import { Input } from "../components/Input";
import { PageHeader } from "../components/PageHeader";
import { Spinner } from "../components/Spinner";
import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";

/** Enrollment in two-step sign-in (feature 004, FR-018). Forced for administrators under the
 * internet profile (RequireAuth redirects here). */
export function TwoFactorSetup() {
  const t = useT();
  const { user, refresh } = useAuth();
  const { product_name } = useBranding();
  const navigate = useNavigate();
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user?.mfa_enabled || setup) return;
    let cancelled = false;
    api
      .post<MfaSetup>("/api/me/mfa/setup")
      .then((s) => !cancelled && setSetup(s))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
  }, [user?.mfa_enabled, setup]);

  const activate = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const digits = code.replace(/\D/g, "");
    if (digits.length !== 6 || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ recovery_codes: string[] }>("/api/me/mfa/enable", { code: digits });
      setCodes(res.recovery_codes);
    } catch (err) {
      setError(err instanceof ApiError && err.code === "invalid_code" ? t.mfa.invalidCode : err instanceof ApiError ? err.message : t.common.unexpected);
      setCode("");
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    const text = `${product_name} — ${user?.email}\n${t.mfa.codesTitle}\n\n${(codes ?? []).join("\n")}\n`;
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "codigos-recuperacion.txt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const done = async () => {
    await refresh();
    navigate("/perfil", { replace: true });
  };

  if (codes) {
    return (
      <div className="space-y-5">
        <BackLink to="/perfil" />
        <PageHeader title={t.mfa.codesTitle} subtitle={t.mfa.codesText} />
        <div className="max-w-lg space-y-5">
          <Card tone="accent" className="space-y-4 p-5 sm:p-6">
            <ul className="grid grid-cols-2 gap-2" aria-label={t.mfa.codesTitle}>
              {codes.map((c) => (
                <li key={c} className="rounded-lg border border-line bg-subtle px-3 py-2 text-center font-mono text-sm font-semibold text-ink-2">{c}</li>
              ))}
            </ul>
            <div className="flex flex-wrap">
              <div className="mb-2 mr-2"><CopyButton text={codes.join("\n")} /></div>
              <Button variant="secondary" className="mb-2" icon={<Download className="h-4 w-4" aria-hidden />} onClick={download}>
                {t.mfa.download}
              </Button>
            </div>
          </Card>
          <Button block icon={<ShieldCheck className="h-5 w-5" aria-hidden />} onClick={() => void done()}>
            {t.mfa.saved}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <BackLink to="/perfil" />
      <PageHeader title={t.mfa.setupTitle} subtitle={t.mfa.setupIntro} />
      {user?.mfa_required ? <Alert tone="warning">{t.mfa.setupRequired}</Alert> : null}
      {error ? <Alert tone="error">{error}</Alert> : null}
      {!setup ? (
        error ? null : (
          <div role="status" className="flex justify-center py-12 text-accent">
            <Spinner className="h-8 w-8" />
            <span className="sr-only">{t.common.loading}</span>
          </div>
        )
      ) : (
        <Card tone="accent" className="max-w-lg space-y-5 p-5 sm:p-6">
          <div>
            <h2 className="font-semibold text-ink">{t.mfa.step1}</h2>
            <img src={setup.qr_svg} alt={t.mfa.step1} className="mx-auto mt-3 h-52 w-52 rounded-xl bg-subtle p-2 ring-1 ring-line" />
            <p className="mt-3 flex items-center text-sm text-ink-muted">
              <KeyRound className="mr-1.5 h-4 w-4 shrink-0" aria-hidden />
              {t.mfa.manualKey}
            </p>
            <div className="mt-2"><SecretBox value={setup.secret.replace(/(.{4})/g, "$1 ").trim()} /></div>
            <div className="mt-2"><CopyButton text={setup.secret} /></div>
          </div>
          <form onSubmit={activate} noValidate className="space-y-3">
            <h2 className="font-semibold text-ink">{t.mfa.step2}</h2>
            <Input label={t.mfa.code} value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric"
              autoComplete="one-time-code" maxLength={6} className="font-mono" />
            <Button type="submit" block loading={busy} disabled={code.replace(/\D/g, "").length !== 6}>
              {t.mfa.activate}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
