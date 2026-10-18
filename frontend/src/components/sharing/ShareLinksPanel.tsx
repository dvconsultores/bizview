import { useCallback, useEffect, useRef, useState } from "react";
import { type FormEvent } from "react";
import { Ban, Link as LinkIcon, RefreshCw } from "lucide-react";
import { api, ApiError } from "../../api/client";
import type {
  CreatedShareLink,
  ShareLink,
  ShareLinksState,
} from "../../api/types";
import { t, useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import {
  LINK_DAY_CHIPS,
  errorText,
} from "../../lib/sharing";
import { Alert } from "../Alert";
import { Badge } from "../Badge";
import { Button } from "../Button";
import { Card } from "../Card";
import { CopyButton } from "../CopyButton";
import { EmptyState } from "../EmptyState";
import { Input } from "../Input";
import { Spinner } from "../Spinner";
import { useToast } from "../Toast";

function linkStatusBadge(link: ShareLink) {
  if (link.revoked_at) {
    return <Badge tone="gray">{t.sharing.statusRevoked}</Badge>;
  }
  if (!link.active) {
    return <Badge tone="amber">{t.sharing.statusExpired}</Badge>;
  }
  return <Badge tone="green">{t.sharing.statusActive}</Badge>;
}

export function ShareLinksPanel({ code }: { code: string }) {
  const t = useT();
  const [state, setState] = useState<ShareLinksState | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  const [note, setNote] = useState("");
  const [fieldErrors, setFieldErrors] = useState<
    Record<string, string>
  >({});
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedShareLink | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [revoking, setRevoking] = useState(false);
  const toast = useToast();
  const initialized = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.get<ShareLinksState>(
        `/api/dashboards/${encodeURIComponent(code)}/links`,
      );
      setState(data);
      if (!initialized.current) {
        initialized.current = true;
        setDays(data.days.default);
      }
    } catch (e) {
      setLoadError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeCount =
    state?.active_count ??
    state?.items.filter((link) => link.active && link.counted !== false).length ??
    0;

  const atMax = state ? activeCount >= state.max_active : false;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setPostError(null);
    setFieldErrors({});
    if (!state) return;
    if (
      !Number.isInteger(days) ||
      days < state.days.min ||
      days > state.days.max
    ) {
      setFieldErrors({ days: t.sharing.daysHint });
      return;
    }
    setPosting(true);
    try {
      const createdLink = await api.post<CreatedShareLink>(
        `/api/dashboards/${encodeURIComponent(code)}/links`,
        { days, note: note.trim() || null },
      );
      setCreated(createdLink);
      setNote("");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        const firstField = ["days", "note"].find(
          (field) => e.fields[field] !== undefined,
        );
        if (firstField) {
          setFieldErrors({ [firstField]: e.message });
        } else {
          setPostError(e.message);
        }
      } else {
        setPostError(errorText(e));
      }
    } finally {
      setPosting(false);
    }
  };

  const revoke = async (id: number) => {
    setRevoking(true);
    setPostError(null);
    try {
      await api.del(`/api/dashboards/${encodeURIComponent(code)}/links/${id}`);
      toast(t.sharing.revokedToast);
      setConfirming(null);
      await load();
    } catch (e) {
      setPostError(errorText(e));
    } finally {
      setRevoking(false);
    }
  };

  if (loading && !state) {
    return (
      <div role="status" className="flex justify-center py-8 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  if (loadError || !state) {
    return (
      <Alert tone="error" action={
        <Button
          variant="secondary"
          icon={<RefreshCw className="h-5 w-5" aria-hidden />}
          onClick={() => void load()}
        >
          {t.common.retry}
        </Button>
      }>
        {loadError ?? t.common.unexpected}
      </Alert>
    );
  }

  return (
    <div className="space-y-8">
      <p className="text-sm text-ink-2">{t.sharing.shareIntro}</p>

      {created && (
        <Alert tone="success">
          <div className="space-y-2">
            <p className="text-sm">{t.sharing.createdOnce}</p>
            <code className="block break-all rounded-lg bg-subtle px-3 py-2 text-xs text-ink">
              {created.url}
            </code>
            <CopyButton text={created.url} />
          </div>
        </Alert>
      )}

      {state.sharing_enabled ? (
        <Card tone="accent" className="p-5">
          <form onSubmit={(e) => void submit(e)} className="space-y-5">
            <div role="group" aria-label={t.sharing.daysLabel}>
              <div className="flex flex-wrap gap-2">
                {LINK_DAY_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    aria-pressed={days === chip}
                    onClick={() => setDays(chip)}
                    className={`min-h-tap rounded-full px-4 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-field-focus ${
                      days === chip
                        ? "bg-primary text-on-primary"
                        : "border border-line bg-surface text-ink-2 hover:bg-subtle"
                    }`}
                  >
                    {t.sharing.dayChip(chip)}
                  </button>
                ))}
              </div>
              <div className="mt-3 max-w-xs">
                <Input
                  label={t.sharing.daysLabel}
                  type="number"
                  value={days}
                  onChange={(e) =>
                    setDays(
                      e.target.value === "" ? 0 : Number(e.target.value),
                    )
                  }
                  hint={t.sharing.daysHint}
                  error={fieldErrors.days}
                  min={state.days.min}
                  max={state.days.max}
                />
              </div>
            </div>

            <Input
              label={t.sharing.noteLabel}
              hint={t.sharing.noteHint}
              maxLength={200}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              error={fieldErrors.note}
            />

            {atMax && (
              <Alert tone="warning">
                {t.sharing.maxActive(state.max_active)}
              </Alert>
            )}

            {postError && <Alert tone="error">{postError}</Alert>}

            <Button
              type="submit"
              variant="primary"
              icon={<LinkIcon className="h-5 w-5" aria-hidden />}
              loading={posting}
              disabled={atMax}
            >
              {t.sharing.create}
            </Button>
          </form>
        </Card>
      ) : (
        <Alert tone="info">{t.sharing.sharingDisabled}</Alert>
      )}

      <section>
        <h2 className="mb-3 text-base font-semibold text-ink">
          {t.sharing.activeLinks}
        </h2>
        {state.items.length === 0 ? (
          <EmptyState title={t.sharing.noLinks} />
        ) : (
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {state.items.map((link) => (
                <li key={link.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-ink">
                        {link.note ?? "—"}
                      </p>
                      {(link.origin === "email" || link.origin === "subscription") && (
                        <p className="mt-1 text-xs text-ink-muted">
                          {t.sharing.origin[link.origin]}
                          {link.origin === "subscription" ? ` · ${t.sharing.notCounted}` : ""}
                        </p>
                      )}
                      <p className="mt-1 text-sm text-ink-muted">
                        {t.sharing.linkMeta(
                          link.created_by.name ?? "—",
                          formatDateTime(link.created_at),
                          formatDateTime(link.expires_at),
                          link.visits,
                          formatDateTime(link.last_visit_at),
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {linkStatusBadge(link)}
                      {link.active && (
                        confirming === link.id ? (
                          <div className="flex items-center gap-2">
                            <Button
                              variant="danger"
                              onClick={() => void revoke(link.id)}
                              loading={revoking}
                            >
                              {t.sharing.confirmRevoke}
                            </Button>
                            <Button
                              variant="secondary"
                              onClick={() => setConfirming(null)}
                            >
                              {t.common.cancel}
                            </Button>
                          </div>
                        ) : (
                          <Button
                            variant="secondary"
                            icon={<Ban className="h-5 w-5" aria-hidden />}
                            onClick={() => setConfirming(link.id)}
                          >
                            {t.sharing.revoke}
                          </Button>
                        )
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}
