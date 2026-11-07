import { useEffect, useMemo, useRef, useState } from "react";
import { ClipboardPaste, X } from "lucide-react";
import { api, qs } from "../../api/client";
import type { MailListOption, RecipientOption } from "../../api/types";
import { useT } from "../../i18n";
import {
  domainAllowed,
  errorText,
  parseRecipients,
  recipientTotal,
} from "../../lib/sharing";
import { Button } from "../Button";
import { Input } from "../Input";
import { IconButton } from "../IconButton";

export interface PickedUser {
  id: number;
  name: string;
  email?: string;
}

/** Feature 058: a chosen list, with the number of people it reaches right now. */
export interface PickedList {
  id: number;
  name: string;
  count: number;
}

/** Feature 058: the three kinds a send may mix, plus the addresses that block it. */
export interface PickedRecipients {
  users: PickedUser[];
  lists: PickedList[];
  emails: string[];
  /** Raw text of what could not be used: shown in red and it blocks the send. */
  invalid: string[];
}

export function emptyRecipients(): PickedRecipients {
  return { users: [], lists: [], emails: [], invalid: [] };
}

export function RecipientPicker(props: {
  code: string;
  allowedDomains: string[];
  /** `null` (the contract) means no ceiling at all. */
  max?: number | null;
  /** `EMAIL_FREE_ADDRESSES_ROLE=admin` leaves typing addresses to administrators. */
  freeAddressesAllowed?: boolean;
  lists?: MailListOption[];
  value: PickedRecipients;
  onChange: (v: PickedRecipients) => void;
  error?: string | null;
}) {
  const t = useT();
  const {
    code,
    allowedDomains,
    max = null,
    freeAddressesAllowed = true,
    lists = [],
    value,
    onChange,
    error,
  } = props;
  const [query, setQuery] = useState("");
  const [rawResults, setRawResults] = useState<RecipientOption[]>([]);
  const [searching, setSearching] = useState(true);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [external, setExternal] = useState("");
  const [pasted, setPasted] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const chosenUserIds = useMemo(
    () => new Set(value.users.map((u) => u.id)),
    [value.users],
  );
  const chosenListIds = useMemo(
    () => new Set(value.lists.map((l) => l.id)),
    [value.lists],
  );
  const chosenEmails = useMemo(() => {
    const set = new Set(value.emails.map((e) => e.toLowerCase()));
    for (const u of value.users) {
      if (u.email) set.add(u.email.toLowerCase());
    }
    return set;
  }, [value.users, value.emails]);

  const results = useMemo(
    () => rawResults.filter((item) => !chosenUserIds.has(item.id)),
    [rawResults, chosenUserIds],
  );

  const total = recipientTotal(value);
  const overCeiling = max !== null && total > max;
  const pasteId = `${code}-paste`;

  useEffect(() => {
    let cancelled = false;
    const debounce = setTimeout(() => {
      void (async () => {
        const requestId = ++requestIdRef.current;
        try {
          const data = await api.get<{ items: RecipientOption[] }>(
            `/api/dashboards/${encodeURIComponent(code)}/email/recipients${qs({ q: query || undefined })}`,
          );
          if (cancelled || requestId !== requestIdRef.current) return;
          setRawResults(data.items);
          setSearching(false);
          setSearchError(null);
        } catch (e) {
          if (cancelled || requestId !== requestIdRef.current) return;
          setSearchError(errorText(e));
          setSearching(false);
        }
      })();
    }, query ? 250 : 0);
    return () => {
      cancelled = true;
      clearTimeout(debounce);
    };
  }, [query, code]);

  /** Parses a typed or pasted block: valid addresses join the chips, the rest stay visible in red. */
  const addText = (text: string) => {
    const parsed = parseRecipients(text);
    const accepted: string[] = [];
    const disallowed: string[] = [];
    for (const entry of parsed.valid) {
      if (chosenEmails.has(entry.address) || accepted.includes(entry.address)) continue;
      if (allowedDomains.length > 0 && !domainAllowed(entry.address, allowedDomains)) {
        disallowed.push(entry.address);
        continue;
      }
      accepted.push(entry.address);
    }
    const invalid = [...parsed.invalid, ...disallowed];
    if (accepted.length === 0 && invalid.length === 0) {
      setAddError(t.sharing.email.alreadyAdded);
      return;
    }
    if (max !== null && total + accepted.length > max) {
      setAddError(t.sharing.email.tooMany(max));
      return;
    }
    setAddError(null);
    onChange({
      ...value,
      emails: [...value.emails, ...accepted],
      invalid: [...value.invalid, ...invalid.filter((raw) => !value.invalid.includes(raw))],
    });
  };

  const addExternal = () => {
    const text = external.trim();
    if (!text) return;
    addText(text);
    setExternal("");
  };

  const addPasted = () => {
    const text = pasted.trim();
    if (!text) return;
    addText(text);
    setPasted("");
  };

  const toggleList = (list: MailListOption) => {
    setAddError(null);
    if (chosenListIds.has(list.id)) {
      onChange({ ...value, lists: value.lists.filter((l) => l.id !== list.id) });
      return;
    }
    if (max !== null && total + list.count > max) {
      setAddError(t.sharing.email.tooMany(max));
      return;
    }
    onChange({
      ...value,
      lists: [...value.lists, { id: list.id, name: list.name, count: list.count }],
    });
  };

  const addUser = (item: RecipientOption) => {
    if (max !== null && total + 1 > max) {
      setAddError(t.sharing.email.tooMany(max));
      return;
    }
    setAddError(null);
    onChange({
      ...value,
      users: [
        ...value.users,
        { id: item.id, name: item.name, email: item.email },
      ],
    });
  };

  const removeUser = (userId: number) => {
    onChange({ ...value, users: value.users.filter((u) => u.id !== userId) });
  };

  const removeEmail = (email: string) => {
    onChange({ ...value, emails: value.emails.filter((e) => e !== email) });
  };

  const removeInvalid = (raw: string) => {
    onChange({ ...value, invalid: value.invalid.filter((item) => item !== raw) });
  };

  const chipClass =
    "inline-flex min-h-tap items-center gap-2 rounded-full bg-subtle px-3 py-1.5 text-sm text-ink";

  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 block text-sm font-semibold text-ink-2">
        {t.sharing.email.recipients}
      </legend>
      <p aria-live="polite" className="mb-3 text-sm font-semibold text-ink">
        {t.sharing.email.recipientCount(total)}
        {max !== null && (
          <span className="ml-2 font-normal text-ink-muted">
            {t.sharing.email.tooMany(max)}
          </span>
        )}
      </p>

      {(value.users.length > 0 ||
        value.lists.length > 0 ||
        value.emails.length > 0 ||
        value.invalid.length > 0) && (
        <ul className="mb-4 flex flex-wrap gap-2">
          {value.users.map((u) => (
            <li key={`u-${u.id}`} className={chipClass}>
              <span>
                {u.name}
                {u.email && <span className="ml-2 text-ink-muted">{u.email}</span>}
              </span>
              <IconButton
                icon={<X className="h-4 w-4" aria-hidden />}
                aria-label={t.sharing.email.removeRecipient(u.name)}
                onClick={() => removeUser(u.id)}
              />
            </li>
          ))}
          {value.lists.map((list) => (
            <li
              key={`l-${list.id}`}
              className={`${chipClass} ring-1 ring-inset ring-accent-line`}
            >
              <span>{t.sharing.email.listChip(list.name, list.count)}</span>
              <IconButton
                icon={<X className="h-4 w-4" aria-hidden />}
                aria-label={t.sharing.email.removeList(list.name)}
                onClick={() =>
                  onChange({
                    ...value,
                    lists: value.lists.filter((l) => l.id !== list.id),
                  })
                }
              />
            </li>
          ))}
          {value.emails.map((email) => (
            <li key={`e-${email}`} className={chipClass}>
              <span>{email}</span>
              <IconButton
                icon={<X className="h-4 w-4" aria-hidden />}
                aria-label={t.sharing.email.removeRecipient(email)}
                onClick={() => removeEmail(email)}
              />
            </li>
          ))}
          {/* Colour is never the only signal: the chip also says why it cannot be used. */}
          {value.invalid.map((raw) => (
            <li
              key={`i-${raw}`}
              className="inline-flex min-h-tap items-center gap-2 rounded-full bg-danger-soft px-3 py-1.5 text-sm text-danger ring-1 ring-inset ring-danger-line"
            >
              <span>
                {raw}
                <span className="ml-2 text-xs font-semibold">
                  · {t.sharing.email.invalidAddress}
                </span>
              </span>
              <IconButton
                icon={<X className="h-4 w-4" aria-hidden />}
                aria-label={t.sharing.email.removeRecipient(raw)}
                onClick={() => removeInvalid(raw)}
              />
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-5">
        <div>
          <p className="mb-1.5 text-sm font-semibold text-ink-2">
            {t.sharing.email.lists}
          </p>
          {lists.length === 0 ? (
            <p className="text-sm text-ink-muted">
              {t.sharing.email.noLists} {t.sharing.email.noListsHint}
            </p>
          ) : (
            <>
              <ul className="flex flex-wrap gap-2">
                {lists.map((list) => {
                  const chosen = chosenListIds.has(list.id);
                  return (
                    <li key={list.id}>
                      <button
                        type="button"
                        aria-pressed={chosen}
                        aria-label={
                          chosen
                            ? t.sharing.email.removeList(list.name)
                            : t.sharing.email.addList(list.name)
                        }
                        onClick={() => toggleList(list)}
                        className={`min-h-tap rounded-full px-4 text-sm font-medium transition-colors ${
                          chosen
                            ? "bg-accent-soft text-accent ring-1 ring-inset ring-accent-line"
                            : "bg-field text-ink-2 hover:bg-subtle"
                        }`}
                      >
                        {t.sharing.email.listChip(list.name, list.count)}
                      </button>
                    </li>
                  );
                })}
              </ul>
              <p className="mt-1.5 text-sm text-ink-soft">
                {t.sharing.email.listHint}
              </p>
            </>
          )}
        </div>

        <Input
          label={t.sharing.email.searchUsers}
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSearching(true);
          }}
        />

        {searchError ? (
          <p role="alert" className="text-sm text-danger">
            {searchError}
          </p>
        ) : searching ? (
          <p className="text-sm text-ink-muted">{t.common.loading}</p>
        ) : results.length === 0 ? (
          <p className="text-sm text-ink-muted">{t.sharing.email.noUsers}</p>
        ) : (
          <ul className="space-y-1">
            {results.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => addUser(item)}
                  className="flex min-h-tap w-full min-w-0 items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-ink hover:bg-subtle focus:outline-none focus:ring-2 focus:ring-field-focus"
                >
                  <span className="min-w-0 truncate text-ink">{item.name}</span>
                  {item.email && (
                    <span className="min-w-0 truncate text-sm text-ink-muted">
                      {item.email}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}

        {freeAddressesAllowed ? (
          <>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
              <div className="min-w-0 flex-1">
                <Input
                  label={t.sharing.email.external}
                  hint={t.sharing.email.externalHint(allowedDomains)}
                  type="text"
                  inputMode="email"
                  autoComplete="off"
                  value={external}
                  onChange={(e) => setExternal(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addExternal();
                    }
                  }}
                />
              </div>
              <div className="sm:mt-7">
                <Button onClick={addExternal} className="min-h-tap">
                  {t.sharing.email.add}
                </Button>
              </div>
            </div>

            <div>
              <label
                htmlFor={pasteId}
                className="mb-1.5 block text-sm font-semibold text-ink-2"
              >
                {t.sharing.email.paste}
              </label>
              <textarea
                id={pasteId}
                rows={3}
                value={pasted}
                placeholder={t.sharing.email.pastePlaceholder}
                aria-describedby={`${pasteId}-hint`}
                onChange={(e) => setPasted(e.target.value)}
                className="block w-full rounded-xl border border-transparent bg-field px-4 py-3 text-ink placeholder-ink-faint focus:outline-none focus:ring-2 focus:ring-field-focus"
              />
              <p id={`${pasteId}-hint`} className="mt-1.5 text-sm text-ink-soft">
                {t.sharing.email.pasteHint}
              </p>
              <div className="mt-2">
                <Button
                  variant="secondary"
                  icon={<ClipboardPaste className="h-5 w-5" aria-hidden />}
                  onClick={addPasted}
                  disabled={!pasted.trim()}
                >
                  {t.sharing.email.pasteButton}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <p className="text-sm text-ink-muted">
            {t.sharing.email.freeAddressesAdmin}
          </p>
        )}

        {value.invalid.length > 0 && (
          <p role="alert" className="text-sm text-danger">
            {t.sharing.email.invalidAddresses(value.invalid.length)}
            {allowedDomains.length > 0 &&
              ` ${t.sharing.email.domainNotAllowed(allowedDomains)}`}
          </p>
        )}
        {overCeiling && max !== null && (
          <p role="alert" className="text-sm text-danger">
            {t.sharing.email.tooMany(max)}
          </p>
        )}
        {addError && (
          <p role="alert" className="text-sm text-danger">
            {addError}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </fieldset>
  );
}
