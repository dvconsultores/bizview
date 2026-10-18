import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { api, qs } from "../../api/client";
import type { RecipientOption } from "../../api/types";
import { useT } from "../../i18n";
import {
  domainAllowed,
  errorText,
  isValidEmail,
} from "../../lib/sharing";
import { Button } from "../Button";
import { Input } from "../Input";
import { IconButton } from "../IconButton";

export interface PickedUser {
  id: number;
  name: string;
  email?: string;
}

export interface PickedRecipients {
  users: PickedUser[];
  emails: string[];
}

export function RecipientPicker(props: {
  code: string;
  allowedDomains: string[];
  max: number;
  value: PickedRecipients;
  onChange: (v: PickedRecipients) => void;
  error?: string | null;
}) {
  const t = useT();
  const { code, allowedDomains, max, value, onChange, error } = props;
  const [query, setQuery] = useState("");
  const [rawResults, setRawResults] = useState<RecipientOption[]>([]);
  const [searching, setSearching] = useState(true);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [external, setExternal] = useState("");
  const [externalError, setExternalError] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const chosenUserIds = useMemo(
    () => new Set(value.users.map((u) => u.id)),
    [value.users],
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

  const addUser = (item: RecipientOption) => {
    if (value.users.length + value.emails.length >= max) {
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
    onChange({
      ...value,
      users: value.users.filter((u) => u.id !== userId),
    });
  };

  const removeEmail = (email: string) => {
    onChange({
      ...value,
      emails: value.emails.filter((e) => e !== email),
    });
  };

  const addExternal = () => {
    const email = external.trim().toLowerCase();
    if (!isValidEmail(email)) {
      setExternalError(t.sharing.email.invalidEmail);
      return;
    }
    if (!domainAllowed(email, allowedDomains)) {
      setExternalError(t.sharing.email.domainNotAllowed(allowedDomains));
      return;
    }
    if (chosenEmails.has(email)) {
      setExternalError(t.sharing.email.alreadyAdded);
      return;
    }
    if (value.users.length + value.emails.length >= max) {
      setExternalError(t.sharing.email.tooMany(max));
      return;
    }
    setExternalError(null);
    setExternal("");
    setAddError(null);
    onChange({ ...value, emails: [...value.emails, email] });
  };

  const total = value.users.length + value.emails.length;

  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 block text-sm font-semibold text-ink-2">
        {t.sharing.email.recipients}{" "}
        <span className="font-normal text-ink-muted">
          {total}/{max}
        </span>
      </legend>

      {(value.users.length > 0 || value.emails.length > 0) && (
        <div className="mb-4 flex flex-wrap gap-2">
          {value.users.map((u) => (
            <span
              key={u.id}
              className="inline-flex min-h-tap items-center gap-2 rounded-full bg-subtle px-3 py-1.5 text-sm text-ink"
            >
              <span>
                {u.name}
                {u.email && (
                  <span className="ml-2 text-ink-muted">{u.email}</span>
                )}
              </span>
              <IconButton
                icon={<X className="h-4 w-4" aria-hidden />}
                aria-label={t.sharing.email.removeRecipient(u.name)}
                onClick={() => removeUser(u.id)}
              />
            </span>
          ))}
          {value.emails.map((email) => (
            <span
              key={email}
              className="inline-flex min-h-tap items-center gap-2 rounded-full bg-subtle px-3 py-1.5 text-sm text-ink"
            >
              <span>{email}</span>
              <IconButton
                icon={<X className="h-4 w-4" aria-hidden />}
                aria-label={t.sharing.email.removeRecipient(email)}
                onClick={() => removeEmail(email)}
              />
            </span>
          ))}
        </div>
      )}

      <div className="space-y-5">
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
          <p className="text-sm text-ink-muted">
            {t.sharing.email.noUsers}
          </p>
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

        {allowedDomains.length > 0 ? (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
            <div className="flex-1">
              <Input
                label={t.sharing.email.external}
                hint={t.sharing.email.externalHint(allowedDomains)}
                type="email"
                inputMode="email"
                autoComplete="off"
                value={external}
                onChange={(e) => setExternal(e.target.value)}
                error={externalError}
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
        ) : (
          <p className="text-sm text-ink-muted">
            {t.sharing.email.externalHint([])}
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
