import { ChevronDown, ChevronUp, Pencil, Plus, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { googleAdmin, type GoogleRuleInput } from "../api/google";
import { ApiError } from "../api/client";
import type {
  GoogleAccess,
  GoogleAccessMode,
  GoogleAdminState,
  GoogleCondition,
  GoogleRule,
  GoogleSettings,
  Role,
} from "../api/types";
import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";
import { Alert } from "./Alert";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { IconButton } from "./IconButton";
import { Input } from "./Input";
import { RoleTiles } from "./RoleTiles";
import { SegmentedControl } from "./SegmentedControl";
import { Select } from "./Select";
import { Switch } from "./Switch";
import { useToast } from "./Toast";

type SettingsDraft = Omit<GoogleSettings, "domains_from_env" | "updated_at">;

const draftOf = (settings: GoogleSettings): SettingsDraft => ({
  allowed_domains: [...settings.allowed_domains],
  auto_provision: settings.auto_provision,
  default_role: settings.default_role,
  default_access: settings.default_access,
  apply_rules_to_existing: settings.apply_rules_to_existing,
});

/**
 * A rule an earlier *enabled* rule already covers: it can never decide anything, because the first
 * match wins. Shown as a hint rather than refused — two rules may legitimately share a condition
 * while one of them is disabled (spec, Edge Cases).
 */
function shadowedBy(rules: GoogleRule[], index: number): GoogleRule | null {
  const rule = rules[index];
  if (!rule.enabled) return null;
  const values = new Set(rule.value.map((v) => v.trim().toLowerCase()));
  for (const earlier of rules.slice(0, index)) {
    if (!earlier.enabled || earlier.condition !== rule.condition) continue;
    if (earlier.value.some((v) => values.has(v.trim().toLowerCase()))) return earlier;
  }
  return null;
}

const sameAccess = (a: GoogleAccess, b: GoogleAccess) =>
  a.mode === b.mode && (a.mode !== "list" || [...(a.codes ?? [])].sort().join() === [...(b.codes ?? [])].sort().join());

const sameDraft = (a: SettingsDraft, b: SettingsDraft) =>
  a.allowed_domains.join() === b.allowed_domains.join() &&
  a.auto_provision === b.auto_provision &&
  a.default_role === b.default_role &&
  a.apply_rules_to_existing === b.apply_rules_to_existing &&
  sameAccess(a.default_access, b.default_access);

const emptyRule = (): GoogleRuleInput => ({
  condition: "domain",
  value: [],
  role: "user",
  access: { mode: "none" },
  enabled: true,
});

const message = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

/**
 * The dashboard picker shared by the provisioning defaults and every rule: `none` and
 * `all_public` need no list, `list` shows the catalogue with one switch per dashboard.
 */
function AccessPicker({
  value,
  onChange,
  dashboards,
  label,
}: {
  value: GoogleAccess;
  onChange: (access: GoogleAccess) => void;
  dashboards: GoogleAdminState["dashboards"];
  label: string;
}) {
  const t = useT();
  const codes = value.codes ?? [];
  const option = (mode: GoogleAccessMode) => ({
    value: mode,
    label: t.google.admin.accessModes[mode],
  });
  return (
    <div>
      <SegmentedControl
        label={label}
        value={value.mode}
        options={[option("none"), option("all_public"), option("list")]}
        onChange={(mode) => onChange(mode === "list" ? { mode, codes } : { mode })}
      />
      {value.mode === "list" ? (
        <ul className="mt-2 divide-y divide-line-soft rounded-xl border border-line">
          {dashboards.map((dashboard) => {
            const on = codes.indexOf(dashboard.code) !== -1;
            return (
              <li key={dashboard.code}
                className="flex min-h-[56px] items-center justify-between gap-3 px-3 py-1">
                <span className="min-w-0 truncate font-medium text-ink">{dashboard.name}</span>
                <Switch
                  checked={on}
                  label={dashboard.name}
                  onChange={(next) =>
                    onChange({
                      mode: "list",
                      codes: next
                        ? [...codes, dashboard.code]
                        : codes.filter((code) => code !== dashboard.code),
                    })
                  }
                />
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function DomainsField({
  domains,
  fromEnv,
  rejected,
  onChange,
}: {
  domains: string[];
  fromEnv: boolean;
  /** `GOOGLE_ALLOWED_DOMAINS` entries that are not domains: shown, never silently obeyed. */
  rejected: string[];
  onChange: (domains: string[]) => void;
}) {
  const t = useT();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const add = () => {
    const value = text.trim().toLowerCase().replace(/^@/, "");
    if (!value) return;
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(value)) {
      setError(t.google.admin.domains.invalid);
      return;
    }
    if (domains.indexOf(value) !== -1) {
      setError(t.google.admin.domains.duplicate);
      return;
    }
    onChange([...domains, value]);
    setText("");
    setError(null);
  };

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <Input
          label={t.google.admin.domains.label}
          hint={fromEnv ? t.google.admin.domains.fromEnv : t.google.admin.domains.help}
          error={error}
          value={text}
          placeholder={t.google.admin.domains.placeholder}
          className="min-w-[12rem] flex-1"
          onChange={(e) => {
            setText(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button variant="secondary" onClick={add} icon={<Plus className="h-4 w-4" aria-hidden />}
          className="mt-6 self-start">
          {t.google.admin.domains.add}
        </Button>
      </div>
      {rejected.length ? (
        <div className="mt-3">
          <Alert tone="warning">{t.google.admin.domains.rejected(rejected.join(", "))}</Alert>
        </div>
      ) : null}
      {domains.length ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {domains.map((domain) => (
            <li key={domain}
              className="inline-flex items-center gap-1 rounded-full bg-field py-1 pl-3 pr-1 text-sm text-ink">
              {domain}
              <button
                type="button"
                aria-label={t.google.admin.domains.remove(domain)}
                onClick={() => onChange(domains.filter((d) => d !== domain))}
                className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-full text-ink-3 hover:text-danger"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-ink-muted">{t.google.admin.domains.empty}</p>
      )}
    </div>
  );
}

function ShadowHint({ rules, index }: { rules: GoogleRule[]; index: number }) {
  const t = useT();
  const earlier = shadowedBy(rules, index);
  if (!earlier) return null;
  const position = rules.indexOf(earlier) + 1;
  return (
    <span className="inline-flex">
      <Badge tone="amber">{t.google.admin.rules.shadowed(position)}</Badge>
    </span>
  );
}

function RuleEditor({
  initial,
  dashboards,
  busy,
  onSave,
  onCancel,
}: {
  initial: GoogleRuleInput;
  dashboards: GoogleAdminState["dashboards"];
  busy: boolean;
  onSave: (rule: GoogleRuleInput) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const [rule, setRule] = useState<GoogleRuleInput>(initial);
  const [valueText, setValueText] = useState(initial.value.join("\n"));
  const [error, setError] = useState<string | null>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const values = valueText
      .split(/[\n,]/)
      .map((v) => v.trim().toLowerCase().replace(/^@/, ""))
      .filter(Boolean);
    if (!values.length) {
      setError(t.google.admin.rules.valueRequired);
      return;
    }
    onSave({ ...rule, value: values });
  };

  return (
    <form onSubmit={submit} className="space-y-3 rounded-xl border border-line p-3">
      {error ? <Alert tone="error">{error}</Alert> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <Select
          label={t.google.admin.rules.condition}
          value={rule.condition}
          onChange={(e) => {
            const condition = e.target.value as GoogleCondition;
            setRule({ ...rule, condition });
            setValueText("");
            setError(null);
          }}
        >
          <option value="domain">{t.google.admin.rules.conditions.domain}</option>
          <option value="email">{t.google.admin.rules.conditions.email}</option>
          <option value="group" disabled>{t.google.admin.rules.conditions.group}</option>
        </Select>
        <Select
          label={t.google.admin.rules.role}
          value={rule.role}
          onChange={(e) => setRule({ ...rule, role: e.target.value as Role })}
        >
          <option value="user">{t.roles.user}</option>
          <option value="admin">{t.roles.admin}</option>
        </Select>
      </div>
      <label className="block">
        <span className="mb-1.5 block text-sm font-semibold text-ink-2">
          {rule.condition === "email" ? t.google.admin.rules.emails : t.google.admin.rules.domain}
        </span>
        <textarea
          value={valueText}
          rows={rule.condition === "email" ? 3 : 1}
          placeholder={
            rule.condition === "email"
              ? t.google.admin.rules.emailsPlaceholder
              : t.google.admin.domains.placeholder
          }
          onChange={(e) => {
            setValueText(e.target.value);
            setError(null);
          }}
          className="block min-h-[3.25rem] w-full rounded-xl border border-transparent bg-field px-4 py-3 text-base text-ink transition-colors focus:outline-none focus:ring-2 focus:ring-field-focus"
        />
      </label>
      <AccessPicker
        label={t.google.admin.rules.access}
        value={rule.access}
        dashboards={dashboards}
        onChange={(access) => setRule({ ...rule, access })}
      />
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-sm font-medium text-ink-2">
          <Switch
            checked={rule.enabled}
            label={t.google.admin.rules.enabled}
            onChange={(enabled) => setRule({ ...rule, enabled })}
          />
          {t.google.admin.rules.enabled}
        </span>
        <span className="flex gap-2">
          <Button variant="ghost" onClick={onCancel}>{t.common.cancel}</Button>
          <Button type="submit" loading={busy}>{t.common.save}</Button>
        </span>
      </div>
    </form>
  );
}

/**
 * Administración → Seguridad → Ingreso con Google (feature 054).
 *
 * The installation's Google policy: which domains may sign in, whether an unknown account is
 * created on first sign-in, and the ordered rules that decide role and dashboard access. Every
 * write is audited server-side; the card only shows what the callback will obey.
 */
export function GoogleAdminCard() {
  const t = useT();
  const toast = useToast();
  const { google_auth } = useBranding();
  const [state, setState] = useState<GoogleAdminState | null>(null);
  const [draft, setDraft] = useState<SettingsDraft | null>(null);
  const [rules, setRules] = useState<GoogleRule[]>([]);
  const [editing, setEditing] = useState<{ id: number | null; initial: GoogleRuleInput } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const apply = useCallback((next: GoogleAdminState) => {
    setState(next);
    setDraft(draftOf(next.settings));
  }, []);

  const load = useCallback(async () => {
    try {
      const [next, list] = await Promise.all([
        googleAdmin.state(),
        googleAdmin.rules(),
      ]);
      apply(next);
      setRules(list);
    } catch (e) {
      setError(message(e, t.common.unexpected));
    }
  }, [apply, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const dirty = useMemo(
    () => Boolean(state && draft && !sameDraft(draft, draftOf(state.settings))),
    [state, draft],
  );

  if (!state || !draft) return null;
  const set = (patch: Partial<SettingsDraft>) => setDraft({ ...draft, ...patch });

  const saveSettings = async () => {
    setBusy("settings");
    setError(null);
    try {
      apply(await googleAdmin.saveSettings(draft));
      toast(t.google.admin.saved);
    } catch (e) {
      setError(message(e, t.common.unexpected));
    } finally {
      setBusy(null);
    }
  };

  const saveRule = async (input: GoogleRuleInput) => {
    setBusy("rule");
    setError(null);
    try {
      const id = editing?.id ?? null;
      const saved = id === null
        ? await googleAdmin.createRule(input)
        : await googleAdmin.updateRule(id, input);
      setRules((list) => (id === null
        ? [saved, ...list.map((r) => ({ ...r, position: r.position + 1 }))]
        : list.map((r) => (r.id === id ? saved : r))));
      setEditing(null);
      toast(id === null ? t.google.admin.rules.created : t.google.admin.rules.updated);
    } catch (e) {
      setError(message(e, t.common.unexpected));
    } finally {
      setBusy(null);
    }
  };

  const move = async (index: number, delta: number) => {
    const next = [...rules];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setRules(next);
    setBusy("reorder");
    setError(null);
    try {
      setRules(await googleAdmin.reorder(next.map((r) => r.id)));
    } catch (e) {
      setRules(rules);
      setError(message(e, t.common.unexpected));
    } finally {
      setBusy(null);
    }
  };

  const toggleRule = async (rule: GoogleRule, enabled: boolean) => {
    setBusy(`rule-${rule.id}`);
    setError(null);
    try {
      const saved = await googleAdmin.updateRule(rule.id, {
        condition: rule.condition,
        value: rule.value,
        role: rule.role,
        access: rule.access,
        enabled,
      });
      setRules((list) => list.map((r) => (r.id === rule.id ? saved : r)));
    } catch (e) {
      setError(message(e, t.common.unexpected));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (rule: GoogleRule) => {
    setBusy(`rule-${rule.id}`);
    setError(null);
    try {
      await googleAdmin.deleteRule(rule.id);
      setRules(await googleAdmin.rules());
      toast(t.google.admin.rules.deleted);
    } catch (e) {
      setError(message(e, t.common.unexpected));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="p-4 sm:p-6" role="region" aria-labelledby="google-card-title"
      data-testid="google-admin-card">
      <h2 id="google-card-title" className="text-lg font-semibold text-ink">
        {t.google.admin.title}
      </h2>
      <p className="mb-4 mt-1 text-sm text-ink-muted">{t.google.admin.description}</p>
      <div className="space-y-6">
        {error ? <Alert tone="error">{error}</Alert> : null}
        {/* The provider itself is an installation setting (GOOGLE_CLIENT_ID): without it the policy
            below is stored but nothing can use it, which is worth saying before it is edited. */}
        {google_auth ? null : <Alert tone="warning">{t.google.admin.providerOff}</Alert>}

        <DomainsField
          domains={draft.allowed_domains}
          fromEnv={state.settings.domains_from_env}
          rejected={state.settings.domains_rejected ?? []}
          onChange={(allowed_domains) => set({ allowed_domains })}
        />

        <div>
          <div className="flex items-center justify-between gap-3">
            <span className="min-w-0">
              <span className="block font-medium text-ink">{t.google.admin.provisioning.title}</span>
              <span className="mt-0.5 block text-sm text-ink-muted">
                {t.google.admin.provisioning.help}
              </span>
            </span>
            <Switch
              checked={draft.auto_provision}
              label={t.google.admin.provisioning.title}
              onChange={(auto_provision) => set({ auto_provision })}
            />
          </div>
          {draft.auto_provision ? (
            <div className="mt-3 space-y-3">
              <RoleTiles
                value={draft.default_role}
                onChange={(default_role) => set({ default_role })}
              />
              <AccessPicker
                label={t.google.admin.provisioning.access}
                value={draft.default_access}
                dashboards={state.dashboards}
                onChange={(default_access) => set({ default_access })}
              />
              <p className="text-sm text-ink-muted">{t.google.admin.provisioning.accessForUsers}</p>
            </div>
          ) : null}
        </div>

        <div>
          <div className="flex items-center justify-between gap-3">
            <span className="min-w-0">
              <span className="block font-medium text-ink">{t.google.admin.existing.title}</span>
              <span className="mt-0.5 block text-sm text-ink-muted">
                {t.google.admin.existing.help}
              </span>
            </span>
            <Switch
              checked={draft.apply_rules_to_existing}
              label={t.google.admin.existing.apply}
              onChange={(apply_rules_to_existing) => set({ apply_rules_to_existing })}
            />
          </div>
          {draft.apply_rules_to_existing ? (
            <p className="mt-2 text-sm text-ink-muted">{t.google.admin.existing.warning}</p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={saveSettings} loading={busy === "settings"} disabled={!dirty}>
            {t.common.save}
          </Button>
          {dirty ? (
            <Button variant="ghost" onClick={() => setDraft(draftOf(state.settings))}>
              {t.common.cancel}
            </Button>
          ) : null}
        </div>

        <div className="border-t border-line-soft pt-4">
          <h3 className="font-semibold text-ink">{t.google.admin.rules.title}</h3>
          <p className="mb-3 mt-1 text-sm text-ink-muted">{t.google.admin.rules.help}</p>
          {rules.length ? (
            <ol className="space-y-2">
              {rules.map((rule, index) => (
                <li key={rule.id} className="rounded-xl border border-line p-3">
                  {editing?.id === rule.id ? (
                    <RuleEditor
                      initial={editing.initial}
                      dashboards={state.dashboards}
                      busy={busy === "rule"}
                      onSave={saveRule}
                      onCancel={() => setEditing(null)}
                    />
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="flex flex-wrap items-center gap-2 font-medium text-ink">
                          <Badge tone="neutral">{index + 1}</Badge>
                          {t.google.admin.rules.conditions[rule.condition]}
                          <span className="font-normal text-ink-2">{rule.value.join(", ")}</span>
                          {rule.enabled ? null : (
                            <Badge tone="amber">{t.google.admin.rules.disabled}</Badge>
                          )}
                          <ShadowHint rules={rules} index={index} />
                        </p>
                        <p className="mt-1 text-sm text-ink-muted">
                          {t.roles[rule.role]} · {t.google.admin.accessModes[rule.access.mode]}
                          {rule.access.mode === "list" && rule.access.codes?.length
                            ? ` (${rule.access.codes.length})`
                            : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <Switch
                          checked={rule.enabled}
                          label={`${t.google.admin.rules.enabled}: ${rule.value.join(", ")}`}
                          onChange={(enabled) => toggleRule(rule, enabled)}
                        />
                        <IconButton aria-label={t.google.admin.rules.moveUp} disabled={index === 0}
                          onClick={() => move(index, -1)} icon={<ChevronUp className="h-4 w-4" aria-hidden />} />
                        <IconButton aria-label={t.google.admin.rules.moveDown}
                          disabled={index === rules.length - 1}
                          onClick={() => move(index, 1)} icon={<ChevronDown className="h-4 w-4" aria-hidden />} />
                        <IconButton aria-label={t.google.admin.rules.edit}
                          onClick={() => setEditing({
                            id: rule.id,
                            initial: {
                              condition: rule.condition,
                              value: rule.value,
                              role: rule.role,
                              access: rule.access,
                              enabled: rule.enabled,
                            },
                          })}
                          icon={<Pencil className="h-4 w-4" aria-hidden />} />
                        <IconButton aria-label={t.google.admin.rules.delete} tone="danger"
                          disabled={busy === `rule-${rule.id}`}
                          onClick={() => remove(rule)}
                          icon={<Trash2 className="h-4 w-4" aria-hidden />} />
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-ink-muted">{t.google.admin.rules.empty}</p>
          )}
          {editing?.id === null ? (
            <div className="mt-3">
              <RuleEditor
                initial={editing.initial}
                dashboards={state.dashboards}
                busy={busy === "rule"}
                onSave={saveRule}
                onCancel={() => setEditing(null)}
              />
            </div>
          ) : (
            <Button variant="secondary" className="mt-3"
              icon={<Plus className="h-4 w-4" aria-hidden />}
              onClick={() => setEditing({ id: null, initial: emptyRule() })}>
              {t.google.admin.rules.add}
            </Button>
          )}
          <p className="mt-3 text-sm text-ink-muted">{t.google.admin.rules.superuserNote}</p>
        </div>
      </div>
    </Card>
  );
}
