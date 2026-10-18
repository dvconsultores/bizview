import { AlertTriangle, CheckCircle2, Globe, Info, Lock, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { SecurityOverview } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { TelegramAdminCard } from "../../components/TelegramAdminCard";
import { useT } from "../../i18n";

function Mark({ ok }: { ok: boolean | null }) {
  const t = useT();
  if (ok === true) return <CheckCircle2 className="h-5 w-5 text-success-bright" aria-label={t.admin.security.correct} />;
  if (ok === false) return <XCircle className="h-5 w-5 text-danger-bright" aria-label={t.admin.security.needsAttention} />;
  return <Info className="h-5 w-5 text-ink-faint" aria-label={t.admin.security.info} />;
}

/** Security overview for the super user (feature 004, FR-025). The profile is an installation
 * setting (SECURITY_PROFILE in .env), deliberately not editable here. */
export function Security() {
  const t = useT();
  const [data, setData] = useState<SecurityOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .get<SecurityOverview>("/api/security")
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  return (
    <div className="space-y-5">
      <Breadcrumbs back="/admin" items={[{ label: t.nav.admin, to: "/admin" }, { label: t.admin.security.security }]} />
      <PageHeader title={t.admin.security.security} subtitle={t.admin.security.subtitle} />
      {error ? (
        <Alert tone="error" action={<Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>{t.common.retry}</Button>}>{error}</Alert>
      ) : !data ? (
        <div role="status" className="flex justify-center py-12 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      ) : (
        <>
          <Card tone="accent" className="space-y-3 p-5 sm:p-6">
            <div className="flex flex-wrap items-center">
              <span className="mr-3 flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                {data.profile === "internet" ? <Globe className="h-6 w-6" aria-hidden /> : <Lock className="h-6 w-6" aria-hidden />}
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="text-lg font-semibold text-ink">
                  {data.profile === "internet" ? t.admin.security.profileInternet : t.admin.security.profilePrivate}
                </h2>
                <p className="text-sm text-ink-muted">
                  {data.profile === "internet"
                    ? t.admin.security.internetDescription
                    : t.admin.security.privateDescription}
                </p>
              </div>
              <Badge tone={data.profile === "internet" ? "green" : "blue"}>
                {data.profile_source === "auto" ? t.admin.security.automatic : t.admin.security.configured}
              </Badge>
            </div>
            <p className="text-xs text-ink-soft">
              {t.admin.security.envNote}
            </p>
          </Card>
          {data.legacy_origin_variable_present ? (
            <Alert tone="warning">
              {t.admin.security.legacyVariable}
            </Alert>
          ) : null}
          <Card className="overflow-hidden">
            <ul className="divide-y divide-line">
              {data.checks.map((c) => (
                <li key={c.id} className="flex min-h-tap items-start p-4">
                  <span className="mt-0.5 shrink-0"><Mark ok={c.ok} /></span>
                  <div className="ml-3 min-w-0">
                    <p className="font-medium text-ink">{t.admin.security.checks[c.id] ?? c.id}</p>
                    {c.detail ? <p className="break-words text-sm text-ink-muted">{c.detail}</p> : null}
                    {c.ok === false ? (
                      <p className="mt-1 flex items-center text-sm text-danger">
                        <AlertTriangle className="mr-1 h-4 w-4" aria-hidden />{t.admin.security.needsAttention}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="space-y-3 p-5 sm:p-6" aria-labelledby="direct-reads-title">
            <h2 id="direct-reads-title" className="text-lg font-semibold text-ink">
              {t.directReads.title}
            </h2>
            <p className="text-sm text-ink-muted">{t.directReads.subtitle}</p>
            {(data.direct_reads ?? []).length === 0 ? (
              <p className="text-sm text-ink-soft">{t.directReads.empty}</p>
            ) : (
              <ul className="divide-y divide-line">
                {(data.direct_reads ?? []).map((r) => (
                  <li
                    key={r.source}
                    data-testid="direct-read-row"
                    className="flex min-h-tap flex-wrap items-center justify-between gap-2 py-2"
                  >
                    <span className="font-medium break-words text-ink">
                      {r.source === "bi" ? t.directReads.bi : r.source}
                    </span>
                    <span className="text-sm text-ink-muted">
                      {t.directReads.total}: {r.total}
                    </span>
                    {r.failed > 0 ? (
                      <Badge tone="red">
                        {t.directReads.failed}: {r.failed}
                      </Badge>
                    ) : (
                      <span className="text-sm text-ink-muted">
                        {t.directReads.failed}: 0
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card className="space-y-3 p-5 sm:p-6" aria-labelledby="chat-briefs-title">
            <h2 id="chat-briefs-title" className="text-lg font-semibold text-ink">
              {t.chatAttachments.title}
            </h2>
            <p className="text-sm text-ink-muted">{t.chatAttachments.subtitle}</p>
            {(data.attachments?.total ?? 0) === 0 ? (
              <p className="text-sm text-ink-soft">{t.chatAttachments.empty}</p>
            ) : (
              <dl className="grid gap-2 sm:grid-cols-2" data-testid="chat-attachments-summary">
                <div className="flex min-h-tap items-center justify-between gap-2">
                  <dt className="text-sm text-ink-muted">{t.chatAttachments.total}</dt>
                  <dd className="font-medium text-ink">{data.attachments?.total}</dd>
                </div>
                <div className="flex min-h-tap items-center justify-between gap-2">
                  <dt className="text-sm text-ink-muted">{t.chatAttachments.size}</dt>
                  <dd className="font-medium text-ink">
                    {t.chatAttachments.sizeValue.replace(
                      "{value}",
                      ((data.attachments?.bytes ?? 0) / 1_048_576).toFixed(2),
                    )}
                  </dd>
                </div>
                <div className="flex min-h-tap items-center justify-between gap-2">
                  <dt className="text-sm text-ink-muted">{t.chatAttachments.conversations}</dt>
                  <dd className="font-medium text-ink">{data.attachments?.conversations}</dd>
                </div>
                <div className="flex min-h-tap items-center justify-between gap-2">
                  <dt className="text-sm text-ink-muted">{t.chatAttachments.provider}</dt>
                  <dd className="font-medium break-words text-ink">
                    {data.attachments?.provider}
                    {data.attachments?.model ? ` · ${data.attachments.model}` : ""}
                  </dd>
                </div>
              </dl>
            )}
          </Card>
          <TelegramAdminCard />
        </>
      )}
    </div>
  );
}
