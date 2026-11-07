import { useEffect, useId, useMemo, useState } from "react";
import { Download, Save, Trash2, Upload, X } from "lucide-react";
import { mail } from "../../api/mail";
import { ApiError } from "../../api/client";
import type {
  MailImportResult,
  MailList,
  MailListMember,
  MailListKind,
  MailListVisibility,
} from "../../api/types";
import { useT } from "../../i18n";
import { errorText } from "../../lib/sharing";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button, buttonClass } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { IconButton } from "../../components/IconButton";
import { Input } from "../../components/Input";
import { Select } from "../../components/Select";
import { Spinner } from "../../components/Spinner";
import { Switch } from "../../components/Switch";
import { useToast } from "../../components/Toast";

/**
 * Feature 058: one list, created or edited in place — never in a modal. A list somebody else
 * shared opens read-only here: its members are shown, its pause switches are not.
 */
export function ListEditor(props: {
  list: MailList | null;
  maxMembers: number;
  canShare: boolean;
  onSaved: (list: MailList) => void;
  onDeleted: (id: number) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const { list, maxMembers, canShare, onSaved, onDeleted, onCancel } = props;
  const editing = list !== null;
  const readOnly = list !== null && !list.editable;
  const [name, setName] = useState(list?.name ?? "");
  const [description, setDescription] = useState(list?.description ?? "");
  const [visibility, setVisibility] = useState<MailListVisibility>(
    list?.visibility ?? "personal",
  );
  const [kind, setKind] = useState<MailListKind>(list?.kind ?? "members");
  const [role, setRole] = useState<"user" | "admin">(
    (list?.role as "user" | "admin" | null) ?? "user",
  );
  const [members, setMembers] = useState<MailListMember[]>(list?.members ?? []);
  const [membersText, setMembersText] = useState("");
  const [loadingMembers, setLoadingMembers] = useState(editing);
  const [saving, setSaving] = useState(false);
  const [busyMember, setBusyMember] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<MailImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const toast = useToast();
  const importId = useId();
  const membersId = `${importId}-members`;

  const loadMembers = async (id: number) => {
    try {
      const full = await mail.getList(id);
      setMembers(full.members ?? []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoadingMembers(false);
    }
  };

  useEffect(() => {
    if (!list) return;
    setLoadingMembers(true);
    void loadMembers(list.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list?.id]);

  const active = useMemo(() => members.filter((m) => !m.paused).length, [members]);
  const paused = members.length - active;

  const save = async () => {
    setError(null);
    if (!name.trim()) {
      setError(t.common.required);
      return;
    }
    setSaving(true);
    try {
      let saved: MailList;
      if (!editing) {
        saved = await mail.createList({
          name: name.trim(),
          description: description.trim() || null,
          visibility,
          kind,
          role: kind === "role" ? role : null,
        });
        if (kind === "members" && membersText.trim()) {
          saved = await mail.putMembers(saved.id, { text: membersText.trim() });
        }
      } else {
        saved = await mail.updateList(list.id, {
          name: name.trim(),
          description: description.trim() || null,
          visibility,
        });
        if (list.kind === "members") {
          saved = await mail.putMembers(list.id, {
            members: members.map((m) => ({
              address: m.address,
              name: m.name,
              paused: m.paused,
            })),
            text: membersText.trim() || null,
          });
        }
      }
      toast(t.mailLists.savedToast);
      onSaved(saved);
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const togglePause = async (member: MailListMember) => {
    if (!list) return;
    setBusyMember(member.id);
    setError(null);
    try {
      const updated = await mail.pauseMember(list.id, member.id, !member.paused);
      setMembers(updated.members ?? []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyMember(null);
    }
  };

  const removeMember = (id: number) => {
    setMembers(members.filter((m) => m.id !== id));
  };

  const importCsv = async (file: File) => {
    if (!list) return;
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const text = await file.text();
      const result = await mail.importCsv(list.id, text);
      setImportResult(result);
      await loadMembers(list.id);
    } catch (e) {
      setImportError(errorText(e));
    } finally {
      setImporting(false);
    }
  };

  const remove = async () => {
    if (!list) return;
    setDeleting(true);
    setError(null);
    try {
      await mail.deleteList(list.id);
      toast(t.mailLists.deletedToast);
      onDeleted(list.id);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setDeleting(false);
    }
  };

  const isRole = list ? list.kind === "role" : kind === "role";

  return (
    <Card tone="accent" className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ink">
          {editing ? t.mailLists.editTitle : t.mailLists.createTitle}
        </h2>
        {readOnly && <Badge tone="gray">{t.mailLists.readOnly}</Badge>}
      </div>

      {readOnly && <Alert tone="info">{t.mailLists.sharedReadOnly}</Alert>}

      <div className="mt-4 space-y-5">
        <Input
          label={t.mailLists.name}
          hint={t.mailLists.nameHint}
          value={name}
          maxLength={120}
          readOnly={readOnly}
          onChange={(e) => setName(e.target.value)}
        />

        <Input
          label={t.mailLists.description}
          value={description}
          maxLength={300}
          readOnly={readOnly}
          onChange={(e) => setDescription(e.target.value)}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label={t.mailLists.visibility}
            value={visibility}
            disabled={readOnly || !canShare}
            onChange={(e) => setVisibility(e.target.value as MailListVisibility)}
          >
            <option value="personal">{t.mailLists.visibilityPersonal}</option>
            {canShare && (
              <option value="compartida">{t.mailLists.visibilityShared}</option>
            )}
          </Select>

          {editing ? (
            <div className="min-w-0">
              <p className="mb-1.5 text-sm font-semibold text-ink-2">
                {t.mailLists.kind}
              </p>
              <p className="text-sm text-ink">
                {list.kind === "role"
                  ? t.mailLists.roleKind(t.roles[list.role ?? "user"] ?? list.role ?? "")
                  : t.mailLists.membersKind}
              </p>
            </div>
          ) : (
            <Select
              label={t.mailLists.kind}
              value={kind}
              onChange={(e) => setKind(e.target.value as MailListKind)}
            >
              <option value="members">{t.mailLists.kindMembers}</option>
              <option value="role">{t.mailLists.kindRole}</option>
            </Select>
          )}
        </div>

        {!editing && kind === "role" && (
          <Select
            label={t.mailLists.role}
            value={role}
            onChange={(e) => setRole(e.target.value as "user" | "admin")}
          >
            <option value="user">{t.roles.user}</option>
            <option value="admin">{t.roles.admin}</option>
          </Select>
        )}

        {isRole ? (
          <p className="text-sm text-ink-muted">
            {editing && list ? t.mailLists.roleHint(list.count) : null}{" "}
            {t.mailLists.readOnlyRole}
          </p>
        ) : (
          <div className="space-y-4">
            <div>
              <label
                htmlFor={membersId}
                className="mb-1.5 block text-sm font-semibold text-ink-2"
              >
                {t.mailLists.members}
              </label>
              <textarea
                id={membersId}
                rows={4}
                value={membersText}
                readOnly={readOnly}
                placeholder={t.mailLists.membersPlaceholder}
                aria-describedby={`${membersId}-hint`}
                onChange={(e) => setMembersText(e.target.value)}
                className="block w-full rounded-xl border border-transparent bg-field px-4 py-3 text-ink placeholder-ink-faint focus:outline-none focus:ring-2 focus:ring-field-focus"
              />
              <p id={`${membersId}-hint`} className="mt-1.5 text-sm text-ink-soft">
                {t.mailLists.membersHint} {t.mailLists.membersNote}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={members.length > maxMembers ? "red" : "gray"}>
                {t.mailLists.count(members.length, maxMembers)}
              </Badge>
              {paused > 0 && (
                <Badge tone="amber">{t.mailLists.pausedCount(paused)}</Badge>
              )}
              <span className="text-sm text-ink-muted">{t.mailLists.cap(maxMembers)}</span>
            </div>

            {editing && !readOnly && (
              <>
                <div className="flex flex-wrap gap-2">
                  <label className={`${buttonClass("secondary")} cursor-pointer`} htmlFor={importId}>
                    <Upload className="mr-2 inline-flex h-5 w-5" aria-hidden />
                    {t.mailLists.importCsv}
                  </label>
                  <input
                    id={importId}
                    type="file"
                    accept=".csv,text/csv"
                    className="sr-only"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) void importCsv(file);
                      e.target.value = "";
                    }}
                  />
                  {list && (
                    <a
                      className={buttonClass("secondary")}
                      href={mail.exportCsvUrl(list.id)}
                      download
                    >
                      <Download className="mr-2 inline-flex h-5 w-5" aria-hidden />
                      {t.mailLists.exportCsv}
                    </a>
                  )}
                </div>
                <p className="text-sm text-ink-muted">
                  {t.mailLists.importHint} {t.mailLists.exportHint}
                </p>
              </>
            )}
            {importing && (
              <p role="status" className="text-sm text-ink-muted">
                {t.common.loading}
              </p>
            )}
            {importError && <Alert tone="error">{importError}</Alert>}
            {importResult && (
              <Alert tone={importResult.errors.length > 0 ? "warning" : "success"}>
                <p>
                  {importResult.added === 0 &&
                  importResult.updated === 0 &&
                  importResult.skipped === 0
                    ? t.mailLists.importEmpty
                    : t.mailLists.importResult(
                        importResult.added,
                        importResult.updated,
                        importResult.skipped,
                      )}
                </p>
                {importResult.errors.length > 0 && (
                  <>
                    <p className="mt-1 font-semibold">
                      {t.mailLists.importErrors(importResult.errors.length)}
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {importResult.errors.map((entry) => (
                        <li key={`${entry.line}-${entry.value}`}>
                          {t.mailLists.importLine(entry.line, entry.value, entry.code)}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </Alert>
            )}

            {loadingMembers ? (
              <div role="status" className="flex justify-center py-4 text-accent">
                <Spinner className="h-6 w-6" />
                <span className="sr-only">{t.common.loading}</span>
              </div>
            ) : members.length === 0 ? (
              <EmptyState title={t.mailLists.noMembers} />
            ) : (
              <ul className="divide-y divide-line rounded-xl border border-line">
                {members.map((member) => (
                  <li
                    key={member.id}
                    className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="break-all text-sm font-medium text-ink">
                        {member.address}
                      </p>
                      {member.name && (
                        <p className="truncate text-sm text-ink-muted">{member.name}</p>
                      )}
                    </div>
                    <Badge tone={member.paused ? "amber" : "green"}>
                      {member.paused
                        ? t.mailLists.memberPaused
                        : t.mailLists.memberActive}
                    </Badge>
                    {!readOnly && (
                      <>
                        <Switch
                          checked={!member.paused}
                          disabled={busyMember === member.id}
                          label={
                            member.paused
                              ? t.mailLists.resumeMember(member.address)
                              : t.mailLists.pauseMember(member.address)
                          }
                          onChange={() => void togglePause(member)}
                        />
                        <IconButton
                          icon={<X className="h-4 w-4" aria-hidden />}
                          aria-label={t.mailLists.removeMember(member.address)}
                          onClick={() => removeMember(member.id)}
                        />
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {error && <Alert tone="error">{error}</Alert>}

        {!readOnly ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              loading={saving}
              icon={<Save className="h-5 w-5" aria-hidden />}
              onClick={() => void save()}
            >
              {editing ? t.mailLists.saveMembers : t.mailLists.save}
            </Button>
            <Button variant="secondary" onClick={onCancel}>
              {t.common.cancel}
            </Button>
            {editing &&
              (confirming ? (
                <>
                  <Button variant="danger" loading={deleting} onClick={() => void remove()}>
                    {t.mailLists.confirmDelete}
                  </Button>
                  <Button variant="secondary" onClick={() => setConfirming(false)}>
                    {t.common.cancel}
                  </Button>
                </>
              ) : (
                <Button
                  variant="danger-soft"
                  icon={<Trash2 className="h-5 w-5" aria-hidden />}
                  onClick={() => setConfirming(true)}
                >
                  {t.mailLists.delete}
                </Button>
              ))}
          </div>
        ) : (
          <Button variant="secondary" onClick={onCancel}>
            {t.common.close}
          </Button>
        )}
        {!readOnly && editing && (
          <p className="text-sm text-ink-muted">{t.mailLists.deleteWarning}</p>
        )}
      </div>
    </Card>
  );
}
