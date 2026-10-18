import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError, setReauthHandler } from "../api/client";
import { useT } from "../i18n";
import { Alert } from "./Alert";
import { Button } from "./Button";
import { PasswordField } from "./PasswordField";
import { View } from "./View";

/** Step-up confirmation (feature 004): the API client calls this when a request answers
 * `reauth_required`; the request is retried once after the password is confirmed. */
export function ReauthProvider({ children }: { children: ReactNode }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pendingRef = useRef<{ promise: Promise<boolean>; resolve: (ok: boolean) => void } | null>(null);

  const ask = useCallback((): Promise<boolean> => {
    if (pendingRef.current) return pendingRef.current.promise;
    let resolve!: (ok: boolean) => void;
    const promise = new Promise<boolean>((r) => { resolve = r; });
    pendingRef.current = { promise, resolve };
    setPassword("");
    setError(null);
    setOpen(true);
    return promise;
  }, []);

  useEffect(() => {
    setReauthHandler(ask);
    return () => setReauthHandler(null);
  }, [ask]);

  const finish = (ok: boolean) => {
    setOpen(false);
    setPassword("");
    pendingRef.current?.resolve(ok);
    pendingRef.current = null;
  };

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!password || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/reauth", { password });
      finish(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
      setPassword("");
      if (err instanceof ApiError && (err.status === 423 || err.status === 429)) finish(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {children}
      <View open={open} title={t.reauth.title} autoFocus onClose={() => finish(false)}>
        <form onSubmit={submit} noValidate className="space-y-4">
          <p className="text-sm text-ink-muted">{t.reauth.text}</p>
          {error ? <Alert tone="error">{error}</Alert> : null}
          <PasswordField label={t.signIn.password} autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={() => finish(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" loading={busy} disabled={!password}>
              {t.reauth.confirm}
            </Button>
          </div>
        </form>
      </View>
    </>
  );
}
