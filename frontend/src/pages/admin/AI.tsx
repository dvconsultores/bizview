import { AlertTriangle, CheckCircle2, Cpu, Info, KeyRound, Power, Server, ShieldCheck, Sparkles, Timer, Zap } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../../api/client";
import type { AIStatus, AITestResult } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { CodeChip } from "../../components/CodeChip";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useT } from "../../i18n";

function Item({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center text-sm text-ink-muted">
        <span className="mr-1.5 inline-flex">{icon}</span>
        {label}
      </dt>
      <dd className="mt-1 break-all font-medium text-ink">{children}</dd>
    </div>
  );
}

function StatusBadge({ status }: { status: AIStatus }) {
  const t = useT();
  if (status.enabled) return <Badge tone="green" icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}>{t.ai.enabled}</Badge>;
  if (status.provider === "none") return <Badge tone="gray" icon={<Power className="h-4 w-4" aria-hidden />}>{t.ai.disabled}</Badge>;
  return <Badge tone="amber" icon={<AlertTriangle className="h-4 w-4" aria-hidden />}>{t.ai.incomplete}</Badge>;
}

function HowTo({ enabled }: { enabled: boolean }) {
  const t = useT();
  return (
    <Card className="space-y-4 p-5 sm:p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
          <Info className="h-5 w-5" aria-hidden />
        </span>
        <h2 className="text-lg font-semibold text-ink">{enabled ? t.ai.howTitleChange : t.ai.howTitle}</h2>
      </div>
      <p className="text-sm text-ink-muted">{t.ai.howText}</p>
      <ul className="list-disc space-y-2 pl-5 text-sm text-ink-3">
        <li className="break-words">{t.ai.howAnthropic}</li>
        <li className="break-words">{t.ai.howLocal}</li>
      </ul>
      <p className="flex items-start text-sm text-ink-muted">
        <ShieldCheck className="mr-2 h-5 w-5 shrink-0 text-success-bright" aria-hidden />
        <span>{t.ai.privacy}</span>
      </p>
    </Card>
  );
}

function TestResult({ result }: { result: AITestResult }) {
  const t = useT();
  if (result.ok) {
    return (
      <Alert tone="success">
        <p className="font-semibold">{t.ai.testOk}</p>
        {result.latency_ms !== null ? <p className="mt-1">{t.ai.latency(result.latency_ms)}</p> : null}
        {result.model ? <p className="mt-1 break-all">{t.ai.model}: {result.model}</p> : null}
        {result.reply ? (
          <div className="mt-2">
            <p className="font-medium">{t.ai.reply}</p>
            <p className="mt-1 break-words rounded-lg bg-subtle p-2 font-mono text-xs text-ink-2">{result.reply}</p>
          </div>
        ) : null}
        {result.tool_call ? (
          <p className="mt-2 text-sm">
            <span className="font-medium">{t.ai.toolCall}: </span>
            {result.tool_call.ok
              ? t.ai.toolCallOk
              : (result.tool_call.error?.message ?? t.ai.toolCallFail)}
          </p>
        ) : null}
        <Models result={result} />
      </Alert>
    );
  }
  const code = result.error?.code ?? "provider_error";
  return (
    <Alert tone="error">
      <p className="font-semibold">{t.ai.testFail}</p>
      <p className="mt-1 flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs">{code}</span>
        <span>{t.ai.errorCodes[code] ?? result.error?.message}</span>
      </p>
      {result.error?.action === "admin_ai" ? (
        <p className="mt-1 text-xs text-ink-muted">{t.ai.action.admin_ai}</p>
      ) : null}
      {/* The provider's own words: «devolvió un error» cannot be acted on. */}
      {result.error?.detail ? (
        <div className="mt-2">
          <p className="font-medium">{t.ai.detail}</p>
          <p className="mt-1 max-h-40 overflow-auto break-words rounded-lg bg-subtle p-2 font-mono text-xs text-ink-2">
            {result.error.detail}
          </p>
        </div>
      ) : null}
      <details className="mt-2 text-xs text-ink-muted">
        <summary className="cursor-pointer font-medium">{t.ai.details.title}</summary>
        <p className="mt-1">{t.ai.details.at}: {new Date().toLocaleString()}</p>
        <p className="mt-1">{t.ai.details.log}</p>
        <p className="mt-1 overflow-x-auto rounded bg-subtle p-2 font-mono text-[11px]">
          {t.ai.details.cmd}
        </p>
      </details>
      {result.latency_ms !== null ? <p className="mt-1">{t.ai.latency(result.latency_ms)}</p> : null}
      <Models result={result} />
    </Alert>
  );
}

/** 035: what the last real call did, recorded by the installation (not by this page). */
function RecordedOutcome({ status }: { status: AIStatus }) {
  const t = useT();
  if (!status.last_error_code && !status.last_ok_at) return null;
  return (
    <dl className="grid gap-1 text-xs text-ink-muted sm:grid-cols-2">
      {status.last_ok_at ? (
        <div className="flex flex-wrap gap-1">
          <dt className="font-semibold">{t.ai.lastOk}:</dt>
          <dd>{new Date(status.last_ok_at).toLocaleString()}</dd>
        </div>
      ) : null}
      {status.last_error_code ? (
        <div className="flex flex-wrap gap-1">
          <dt className="font-semibold">{t.ai.lastError}:</dt>
          <dd className="font-mono">{status.last_error_code}</dd>
          {status.last_error_at ? <dd>({new Date(status.last_error_at).toLocaleString()})</dd> : null}
        </div>
      ) : null}
      {status.last_error_detail ? (
        <div className="sm:col-span-2">
          <dd className="max-h-24 overflow-auto break-words rounded bg-subtle p-2 font-mono">
            {status.last_error_detail}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

/** 035: the model ids the endpoint reports, so a wrong AI_MODEL is visible at a glance. */
function Models({ result }: { result: AITestResult }) {
  const t = useT();
  if (result.models === undefined || result.models === null) {
    return <p className="mt-2 text-xs text-ink-muted">{t.ai.modelsUnavailable}</p>;
  }
  return (
    <div className="mt-2 text-xs">
      <p className="font-medium">{t.ai.models}</p>
      <ul className="mt-1 flex flex-wrap gap-1">
        {result.models.map((id) => (
          <li key={id} className="rounded bg-subtle px-1.5 py-0.5 font-mono text-ink-2">{id}</li>
        ))}
      </ul>
      {result.model && !result.models.includes(result.model) ? (
        <p className="mt-1 text-danger-deep">{t.ai.modelsMissing}</p>
      ) : null}
    </div>
  );
}

/** Super user: AI provider status and connection test (feature 003, US3). */
export function AI() {
  const t = useT();
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<AITestResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .get<AIStatus>("/api/admin/ai")
      .then((s) => !cancelled && setStatus(s))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const runTest = async () => {
    setTesting(true);
    setResult(null);
    setTestError(null);
    try {
      setResult(await api.post<AITestResult>("/api/admin/ai/test", {}));
    } catch (err) {
      setTestError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setTesting(false);
    }
  };

  let body: ReactNode;
  if (error) {
    body = (
      <Alert tone="error" action={<Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>{t.common.retry}</Button>}>
        {error}
      </Alert>
    );
  } else if (!status) {
    body = (
      <div role="status" className="flex justify-center py-12 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  } else {
    const off = status.provider === "none";
    const testCard = off ? null : (
      <Card className="space-y-4 p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <Zap className="h-5 w-5" aria-hidden />
          </span>
          <h2 className="text-lg font-semibold text-ink">{t.ai.test}</h2>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button icon={<Zap className="h-5 w-5" aria-hidden />} loading={testing} disabled={!status.enabled} onClick={runTest}>
            {testing ? t.ai.testing : t.ai.test}
          </Button>
        </div>
        <RecordedOutcome status={status} />
        <div aria-live="polite" className="empty:hidden">
          {result ? <TestResult result={result} /> : null}
          {testError ? <Alert tone="error">{testError}</Alert> : null}
        </div>
      </Card>
    );
    body = (
      <>
        <Card tone="accent" className="space-y-5 p-5 sm:p-6">
          <div className="flex items-center">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
              <Sparkles className="h-6 w-6" aria-hidden />
            </span>
            <div className="ml-4 flex min-w-0 flex-1 flex-wrap items-center justify-between">
              <h2 className="mr-3 text-lg font-semibold text-ink">{t.ai.status}</h2>
              <StatusBadge status={status} />
            </div>
          </div>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
            <Item icon={<Sparkles className="h-4 w-4" aria-hidden />} label={t.ai.provider}>
              {t.ai.providers[status.provider] ?? status.provider}
            </Item>
            <Item icon={<Cpu className="h-4 w-4" aria-hidden />} label={t.ai.model}>
              {status.model ?? "—"}
            </Item>
            {status.base_url ? (
              <Item icon={<Server className="h-4 w-4" aria-hidden />} label={t.ai.endpoint}>
                {status.base_url}
              </Item>
            ) : null}
            <Item icon={<KeyRound className="h-4 w-4" aria-hidden />} label={t.ai.key}>
              {status.key_configured ? (
                <Badge tone="green" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>{t.ai.keySet}</Badge>
              ) : (
                <Badge tone="gray" icon={<Power className="h-3.5 w-3.5" aria-hidden />}>{t.ai.keyNotSet}</Badge>
              )}
            </Item>
            <Item icon={<Timer className="h-4 w-4" aria-hidden />} label={t.ai.timeout}>
              {t.ai.seconds(status.timeout_seconds)}
            </Item>
          </dl>
          {status.missing.length ? (
            <Alert tone="warning">
              <span>{t.ai.missing}</span>{" "}
              {status.missing.map((name) => (
                <CodeChip key={name} className="mr-1.5">{name}</CodeChip>
              ))}
            </Alert>
          ) : null}
        </Card>
        {off ? <HowTo enabled={false} /> : testCard}
        {off ? null : <HowTo enabled={status.enabled} />}
      </>
    );
  }

  return (
    <div className="space-y-5">
      <Breadcrumbs back="/admin" items={[{ label: t.nav.admin, to: "/admin" }, { label: t.ai.title }]} />
      <PageHeader
        title={t.ai.title}
        subtitle={t.ai.subtitle}
      />
      {body}
    </div>
  );
}
