import { Lock, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { TelegramAdminState, TelegramCheck } from "../api/types";
import { t, useT } from "../i18n";
import { Alert } from "./Alert";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { Input } from "./Input";
import { Switch } from "./Switch";
import { useToast } from "./Toast";

const reasonText = (reason?: string) =>
  (reason && t.telegram.checkReasons[reason]) || t.telegram.checkReasons.telegram_error;

/** Super user: the installation's bot (feature 007, US1). The credential is write-only. */
export function TelegramAdminCard() {
  const t = useT();
  const toast = useToast();
  const [state, setState] = useState<TelegramAdminState | null>(null);
  const [botUsername, setBotUsername] = useState("");
  const [token, setToken] = useState("");
  const [replacing, setReplacing] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ bot_username?: string; token?: string }>({});
  const [check, setCheck] = useState<TelegramCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "check" | "toggle" | null>(null);

  const apply = (s: TelegramAdminState) => {
    setState(s);
    setBotUsername(s.bot_username ?? "");
  };

  const load = useCallback(async () => {
    try {
      apply(await api.get<TelegramAdminState>("/api/admin/telegram"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setBusy("save");
    setFieldErrors({});
    setError(null);
    setCheck(null);
    try {
      const body: { bot_username: string; token?: string } = { bot_username: botUsername.trim() };
      if (!state?.token_configured || replacing) body.token = token.trim();
      apply(await api.put<TelegramAdminState>("/api/admin/telegram", body));
      setToken("");
      setReplacing(false);
      toast(t.telegram.saved);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setFieldErrors({
          bot_username: e.fields.bot_username ? t.telegram.botUsernameInvalid : undefined,
          token: e.fields.token ? t.telegram.botCredentialInvalid : undefined,
        });
      } else {
        setError(e instanceof ApiError ? e.message : t.common.unexpected);
      }
    } finally {
      setBusy(null);
    }
  };

  const runCheck = async () => {
    setBusy("check");
    setError(null);
    try {
      setCheck(await api.post<TelegramCheck>("/api/admin/telegram/check"));
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    } finally {
      setBusy(null);
    }
  };

  const toggle = async (enabled: boolean) => {
    setBusy("toggle");
    setError(null);
    try {
      apply(await api.post<TelegramAdminState>("/api/admin/telegram/enabled", { enabled }));
      toast(enabled ? t.telegram.enabled : t.telegram.disabled);
    } catch (e) {
      setError(e instanceof ApiError && e.code === "telegram_check_required"
        ? t.telegram.enableHint
        : e instanceof ApiError ? e.message : t.common.unexpected);
    } finally {
      setBusy(null);
    }
  };

  if (!state) return null;
  const showTokenInput = !state.token_configured || replacing;

  return (
    <Card className="p-4 sm:p-6">
      <h2 className="text-lg font-semibold text-ink">{t.telegram.adminTitle}</h2>
      <p className="mb-4 mt-1 text-sm text-ink-muted">{t.telegram.adminDescription}</p>
      <div className="space-y-4">
        {error ? <Alert tone="error">{error}</Alert> : null}
        {check ? (
          <Alert tone={check.ok ? "success" : "error"}>
            {check.ok ? t.telegram.checkOk(check.bot_name ?? "") : reasonText(check.reason)}
          </Alert>
        ) : null}
        <Input
          label={t.telegram.botUsername}
          hint={t.telegram.botUsernameHelp}
          value={botUsername}
          onChange={(e) => setBotUsername(e.target.value)}
          error={fieldErrors.bot_username}
          autoCapitalize="none"
          autoComplete="off"
          spellCheck={false}
        />
        {showTokenInput ? (
          <Input
            label={t.telegram.botCredential}
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            error={fieldErrors.token}
          />
        ) : (
          <div>
            <p className="mb-1.5 text-sm font-medium text-ink-3">{t.telegram.botCredential}</p>
            <div className="flex flex-wrap items-center">
              <Badge tone="green" icon={<Lock className="h-3.5 w-3.5" aria-hidden />}>{t.telegram.configured}</Badge>
              <Button variant="ghost" className="ml-2" onClick={() => setReplacing(true)}>{t.telegram.replace}</Button>
            </div>
          </div>
        )}
        <div className="space-y-3 sm:flex sm:space-x-3 sm:space-y-0">
          <Button className="w-full sm:w-auto" onClick={save} loading={busy === "save"}>{t.telegram.save}</Button>
          <Button variant="secondary" className="w-full sm:w-auto" icon={<RefreshCw className="h-5 w-5" aria-hidden />}
            onClick={runCheck} loading={busy === "check"} disabled={!state.token_configured || !state.bot_username}>
            {t.telegram.test}
          </Button>
        </div>
        <div className="flex items-center justify-between border-t border-line-soft pt-4">
          <div className="min-w-0 pr-3">
            <p className="font-medium text-ink">{t.telegram.enable}</p>
            <p className="text-sm text-ink-muted">
              {state.last_check_ok === true
                ? t.telegram.checkOk(state.last_check?.bot_name ?? "")
                : state.last_check_ok === false
                  ? reasonText(state.last_check?.reason)
                  : t.telegram.enableHint}
            </p>
          </div>
          <Switch checked={state.enabled} onChange={(v) => void toggle(v)} label={t.telegram.enable}
            disabled={state.last_check_ok !== true || busy === "toggle"} />
        </div>
      </div>
    </Card>
  );
}
