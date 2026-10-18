import { CheckCircle2, ChevronRight, ShieldCheck, ShieldOff } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import { MFA_SETUP_PATH, useAuth } from "../auth/AuthContext";
import { useT } from "../i18n";
import { Alert } from "./Alert";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { CopyButton } from "./CopyButton";
import { Input } from "./Input";
import { useToast } from "./Toast";
import { View } from "./View";

/** Own two-step sign-in in the profile (feature 004, FR-018). */
export function TwoFactorCard() {
  const t = useT();
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [codes, setCodes] = useState<string[] | null>(null);
  const [disableOpen, setDisableOpen] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  const regenerate = async () => {
    setBusy(true);
    try {
      const res = await api.post<{ recovery_codes: string[] }>("/api/me/mfa/recovery-codes");
      setCodes(res.recovery_codes);
      await refresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setBusy(false);
    }
  };

  const closeDisable = () => {
    setDisableOpen(false);
    setCode("");
    setError(null);
  };

  const disable = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/me/mfa/disable", { code: code.replace(/\D/g, "") });
      closeDisable();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError && err.code === "invalid_code" ? t.mfa.invalidCode : err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4 sm:p-6">
      <div className="mb-3 flex flex-wrap items-center justify-between">
        <h2 className="mr-2 text-lg font-semibold">{t.mfa.profileTitle}</h2>
        {user.mfa_enabled ? (
          <Badge tone="green" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>{t.mfa.enabled}</Badge>
        ) : (
          <Badge tone="gray" icon={<ShieldOff className="h-3.5 w-3.5" aria-hidden />}>{t.mfa.disabled}</Badge>
        )}
      </div>
      {user.mfa_required ? <p className="mb-3 text-sm text-ink-muted">{t.mfa.requiredByProfile}</p> : null}
      {!user.mfa_enabled ? (
        <Link to={MFA_SETUP_PATH} className="-mx-2 flex min-h-tap items-center rounded-xl px-2 py-2 hover:bg-subtle">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </span>
          <span className="ml-3 flex-1 font-medium text-ink">{t.mfa.enable}</span>
          <ChevronRight className="h-5 w-5 text-ink-faint" aria-hidden />
        </Link>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-ink-muted">{t.mfa.codesLeft(user.recovery_codes_left ?? 0)}</p>
          <div className="flex flex-col sm:flex-row">
            <Button variant="secondary" loading={busy} onClick={regenerate} className="sm:mr-2">{t.mfa.regenerate}</Button>
            {!user.mfa_required ? (
              <Button variant="ghost" className="mt-2 text-danger hover:bg-danger-soft sm:mt-0" onClick={() => setDisableOpen(true)}>
                {t.mfa.disable}
              </Button>
            ) : null}
          </div>
        </div>
      )}

      <View open={codes !== null} title={t.mfa.codesTitle} onClose={() => setCodes(null)}
        footer={<Button onClick={() => setCodes(null)}>{t.mfa.saved}</Button>}>
        <p className="mb-3 text-sm">{t.mfa.codesText}</p>
        <ul className="grid grid-cols-2 gap-2 font-mono sm:grid-cols-3">
          {(codes ?? []).map((c) => <li key={c} className="rounded-lg bg-subtle px-2 py-1.5 text-center ring-1 ring-line">{c}</li>)}
        </ul>
        <div className="mt-3"><CopyButton text={(codes ?? []).join("\n")} /></div>
      </View>

      <View open={disableOpen} title={t.mfa.disableTitle} autoFocus onClose={closeDisable}>
        <form onSubmit={disable} noValidate className="space-y-3">
          {error ? <Alert tone="error">{error}</Alert> : null}
          <Input label={t.mfa.code} value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric"
            autoComplete="one-time-code" maxLength={6} className="font-mono" />
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={closeDisable}>{t.common.cancel}</Button>
            <Button type="submit" variant="danger" loading={busy} disabled={code.replace(/\D/g, "").length !== 6}>{t.mfa.disable}</Button>
          </div>
        </form>
      </View>
    </Card>
  );
}
