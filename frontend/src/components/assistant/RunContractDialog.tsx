import { useEffect, useRef, useState } from "react";
import { api, ApiError, askReauth } from "../../api/client";
import { projectsApi } from "../../api/projects";
import type {
  AssistantSession,
  RunContract,
  RunProfile,
} from "../../api/types";
import { useT } from "../../i18n";
import { Alert } from "../Alert";
import { Button } from "../Button";

type StageChoice = "draft" | "preview" | "apply";

/** 24 px minimum target (WCAG 2.5.8): the project's e2e axe run enforces it. */
const CHOICE = "h-6 w-6 shrink-0 accent-accent";

const STAGES: Record<StageChoice, Array<"draft" | "preview" | "apply">> = {
  draft: ["draft"],
  preview: ["draft", "preview"],
  apply: ["draft", "preview", "apply"],
};

function stageChoice(stages: RunContract["stages"] | undefined): StageChoice {
  if (stages?.includes("apply")) return "apply";
  if (stages?.includes("preview")) return "preview";
  return "draft";
}

/**
 * Feature 028: the run contract (FR-001).
 *
 * One authorisation for a whole run: stages, sources, limits, `modify_existing`, `auto_rollback`,
 * `visible_to`, plus the step-up (password, and the two-step code on the `internet` profile). It is
 * the only modal-like panel of the feature and it is dismissible: cancelling leaves the mode as it
 * was.
 */
export function RunContractDialog({
  session,
  goal,
  onClose,
  onConfirmed,
}: {
  session: AssistantSession;
  goal: string;
  onClose: () => void;
  onConfirmed: (session: AssistantSession) => void;
}) {
  const t = useT();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [stage, setStage] = useState<StageChoice>("apply");
  const [sources, setSources] = useState<string>("");
  const [tokens, setTokens] = useState("400000");
  const [previews, setPreviews] = useState("5");
  const [applies, setApplies] = useState("1");
  const [minutes, setMinutes] = useState("30");
  const [modifyExisting, setModifyExisting] = useState(false);
  const [autoRollback, setAutoRollback] = useState(true);
  const [visibleToUsers, setVisibleToUsers] = useState(false);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [profiles, setProfiles] = useState<RunProfile[]>([]);
  const [profileId, setProfileId] = useState<number | null>(null);
  const [profileName, setProfileName] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    panelRef.current?.focus();
    void projectsApi
      .runProfiles()
      .then(setProfiles)
      .catch(() => setProfiles([]));
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    panelRef.current?.addEventListener("keydown", onKey);
    return () => panelRef.current?.removeEventListener("keydown", onKey);
  }, [onClose]);

  const applyProfile = (id: number | null) => {
    setProfileId(id);
    const profile = profiles.find((item) => item.id === id);
    if (!profile) return;
    const contract = profile.contract;
    setStage(stageChoice(contract.stages));
    setSources((contract.sources ?? []).map((item) => item.name).join(", "));
    if (contract.limits) {
      setTokens(String(contract.limits.tokens));
      setPreviews(String(contract.limits.previews));
      setApplies(String(contract.limits.applies));
      setMinutes(String(Math.round(contract.limits.wall_clock_seconds / 60)));
    }
    setModifyExisting(!!contract.modify_existing);
    setAutoRollback(contract.auto_rollback ?? true);
    setVisibleToUsers((contract.visible_to ?? []).includes("user"));
  };

  const buildContract = (): RunContract => ({
    goal: goal.trim() || t.assistant.contract.goal,
    stages: STAGES[stage],
    sources: sources
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean)
      .map((name) => ({ name })),
    limits: {
      tokens: Number(tokens) || 400000,
      previews: Number(previews) || 0,
      applies: Number(applies) || 0,
      wall_clock_seconds: Math.max(60, (Number(minutes) || 30) * 60),
    },
    modify_existing: modifyExisting,
    auto_rollback: autoRollback,
    visible_to: visibleToUsers ? ["user"] : [],
    profile_id: profileId,
  });

  const authorize = async () => {
    setSaving(true);
    setError(null);
    setFields({});
    try {
      const result = await projectsApi.confirmContract(session.id, {
        contract: buildContract(),
        password,
        code: code.trim() || null,
        profile_id: profileId,
      });
      onConfirmed(result.session);
    } catch (err) {
      if (err instanceof ApiError && err.code === "reauth_required") {
        // A stale session gets the usual step-up prompt, then the same request.
        if (await askReauth()) return void (await authorize());
      }
      if (err instanceof ApiError) {
        setError(err.message);
        setFields(err.fields ?? {});
      } else {
        setError(t.common.unexpected);
      }
    } finally {
      setSaving(false);
    }
  };

  const saveProfile = async () => {
    setSaving(true);
    setError(null);
    try {
      const { goal: _goal, ...contract } = buildContract();
      const row = await projectsApi.saveRunProfile({
        name: profileName.trim(),
        contract,
      });
      setProfiles((items) => [...items, row]);
      setProfileId(row.id);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setSaving(false);
    }
  };

  const cancel = async () => {
    await api
      .post(`/api/assistant/sessions/${session.id}/contract/cancel`, {})
      .catch(() => undefined);
    onClose();
  };

  const field = (name: string) =>
    fields[name] ? <span className="text-xs text-danger">{fields[name]}</span> : null;

  // Feature-010 look: an inline panel above the composer, never a modal overlay.
  return (
    <section
      ref={panelRef}
      tabIndex={-1}
      aria-labelledby="contract-title"
      data-run-contract=""
      className="mb-2 max-h-[60vh] overflow-y-auto rounded-2xl border border-line bg-surface p-4 shadow-sm focus:outline-none sm:p-5"
    >
      <div>
        <h2 id="contract-title" className="text-lg font-semibold text-ink">
          {t.assistant.contract.title}
        </h2>
        <p className="mt-1 text-sm text-ink-muted">{t.assistant.contract.intro}</p>

        <div className="mt-4 flex flex-col gap-4 text-sm">
          <div>
            <span className="font-medium text-ink">{t.assistant.contract.goal}</span>
            <p className="mt-1 whitespace-pre-wrap break-words text-ink-2">
              {goal.trim() || "—"}
            </p>
          </div>

          <fieldset>
            <legend className="font-medium text-ink">{t.assistant.contract.stages}</legend>
            <div className="mt-1 flex flex-col gap-1">
              {(["draft", "preview", "apply"] as StageChoice[]).map((item) => (
                <label key={item} className="inline-flex min-h-tap items-center gap-2">
                  <input
                    type="radio"
                    name="stage"
                    value={item}
                    className={CHOICE}
                    checked={stage === item}
                    onChange={() => setStage(item)}
                  />
                  {item === "draft"
                    ? t.assistant.contract.stageDraft
                    : item === "preview"
                      ? t.assistant.contract.stagePreview
                      : t.assistant.contract.stageApply}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="flex flex-col gap-1">
            <span className="font-medium text-ink">{t.assistant.contract.sources}</span>
            <input
              type="text"
              value={sources}
              onChange={(event) => setSources(event.target.value)}
              placeholder={t.assistant.contract.sourcesHint}
              className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
            />
            {field("sources")}
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-1">
              <span className="text-ink-2">{t.assistant.contract.tokens}</span>
              <input
                type="number"
                inputMode="numeric"
                min={10000}
                value={tokens}
                onChange={(event) => setTokens(event.target.value)}
                className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-ink-2">{t.assistant.contract.previews}</span>
              <input
                type="number"
                inputMode="numeric"
                min={0}
                value={previews}
                onChange={(event) => setPreviews(event.target.value)}
                className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-ink-2">{t.assistant.contract.applies}</span>
              <input
                type="number"
                inputMode="numeric"
                min={0}
                value={applies}
                onChange={(event) => setApplies(event.target.value)}
                className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-ink-2">{t.assistant.contract.minutes}</span>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
                className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
              />
            </label>
          </div>

          <label className="inline-flex min-h-tap items-center gap-2">
            <input
              type="checkbox"
              className={CHOICE}
              checked={modifyExisting}
              onChange={(event) => setModifyExisting(event.target.checked)}
            />
            <span className="text-ink-2">{t.assistant.contract.modifyExisting}</span>
          </label>
          <label className="inline-flex min-h-tap items-center gap-2">
            <input
              type="checkbox"
              className={CHOICE}
              checked={autoRollback}
              onChange={(event) => setAutoRollback(event.target.checked)}
            />
            <span className="text-ink-2">{t.assistant.contract.autoRollback}</span>
          </label>

          <fieldset>
            <legend className="font-medium text-ink">{t.assistant.contract.visibleTo}</legend>
            <label className="mt-1 inline-flex min-h-tap items-center gap-2">
              <input
                type="checkbox"
                className={CHOICE}
                checked={visibleToUsers}
                onChange={(event) => setVisibleToUsers(event.target.checked)}
              />
              {visibleToUsers
                ? t.assistant.contract.visibleToUser
                : t.assistant.contract.visibleToNone}
            </label>
          </fieldset>

          <label className="flex flex-col gap-1">
            <span className="font-medium text-ink">{t.assistant.contract.profile}</span>
            <select
              value={profileId ?? ""}
              onChange={(event) =>
                applyProfile(event.target.value ? Number(event.target.value) : null)
              }
              className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
            >
              <option value="">{t.assistant.contract.profileNone}</option>
              {profiles.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-wrap items-end gap-2">
            <label className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="text-ink-2">{t.assistant.contract.profileName}</span>
              <input
                type="text"
                maxLength={60}
                value={profileName}
                onChange={(event) => setProfileName(event.target.value)}
                className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
              />
            </label>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void saveProfile()}
              disabled={!profileName.trim() || saving}
            >
              {t.assistant.contract.saveProfile}
            </Button>
          </div>
          {saved ? <p className="text-xs text-success">{t.assistant.contract.saved}</p> : null}

          <label className="flex flex-col gap-1">
            <span className="font-medium text-ink">{t.assistant.contract.password}</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
            />
            {field("password")}
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-ink-2">{t.assistant.contract.code}</span>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={8}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              className="min-h-tap rounded-lg border border-line bg-surface px-3 text-ink"
            />
            {field("code")}
          </label>

          {error ? <Alert tone="error">{error}</Alert> : null}
        </div>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => void cancel()}>
            {t.assistant.contract.cancel}
          </Button>
          <Button
            type="button"
            onClick={() => void authorize()}
            disabled={saving || !password}
            data-contract-confirm=""
          >
            {saving ? t.assistant.contract.confirming : t.assistant.contract.confirm}
          </Button>
        </div>
      </div>
    </section>
  );
}
