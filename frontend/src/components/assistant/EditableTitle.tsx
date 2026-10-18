import { Pencil } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ApiError, api } from "../../api/client";
import type { AssistantSession } from "../../api/types";
import { useT } from "../../i18n";
import { iconButtonClass } from "../IconButton";

interface EditableTitleProps {
  sessionId: number;
  title: string;
  onRenamed: (session: AssistantSession) => void;
  children: ReactNode;
  as?: "div" | "span";
  className?: string;
  inputClassName?: string;
  buttonLabel?: string;
}

export function EditableTitle({
  sessionId,
  title,
  onRenamed,
  children,
  as: Wrapper = "div",
  className = "",
  inputClassName = "",
  buttonLabel,
}: EditableTitleProps) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const cancelledRef = useRef(false);
  const mountedRef = useRef(true);
  const leftEditingRef = useRef(false);
  const pencilRef = useRef<HTMLButtonElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const inputId = useId();
  const errorId = useId();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!editing && leftEditingRef.current) {
      leftEditingRef.current = false;
      pencilRef.current?.focus();
    }
  }, [editing]);

  const leaveEdit = () => {
    leftEditingRef.current = true;
    setEditing(false);
  };

  const cancel = () => {
    cancelledRef.current = true;
    setDraft(title);
    setError(null);
    leaveEdit();
  };

  const save = async () => {
    if (savingRef.current || cancelledRef.current) return;
    const value = draft.trim();
    if (value === title) {
      cancelledRef.current = true;
      leaveEdit();
      return;
    }
    if (value.length < 1 || value.length > 120) {
      setError(t.assistant.renameInvalid);
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const result = await api.patch<AssistantSession>(
        `/api/assistant/sessions/${sessionId}`,
        { title: value },
      );
      if (!mountedRef.current || cancelledRef.current) return;
      onRenamed(result);
      cancelledRef.current = true;
      leaveEdit();
    } catch (err) {
      if (!mountedRef.current || cancelledRef.current) return;
      setError(
        err instanceof ApiError ? err.message : t.assistant.failedToRename,
      );
    } finally {
      savingRef.current = false;
      if (mountedRef.current) setSaving(false);
    }
  };

  const handleBlur = () => {
    void save();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void save();
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      cancel();
    }
  };

  if (!editing) {
    return (
      <Wrapper
        className={`flex min-w-0 items-center gap-1 ${className}`}
        data-editable-title-root=""
      >
        {children}
        <button
          ref={pencilRef}
          type="button"
          className={iconButtonClass()}
          aria-label={buttonLabel ?? t.assistant.rename}
          title={t.assistant.rename}
          data-rename-trigger=""
          onClick={() => {
            cancelledRef.current = false;
            setDraft(title);
            setError(null);
            setEditing(true);
          }}
        >
          <Pencil className="h-4 w-4" aria-hidden />
        </button>
      </Wrapper>
    );
  }

  return (
    <Wrapper
      className={`flex min-w-0 flex-wrap items-center gap-1 ${className}`}
      data-editable-title-root=""
    >
      <label className="sr-only" htmlFor={inputId}>
        {t.assistant.renameLabel}
      </label>
      <input
        ref={inputRef}
        id={inputId}
        type="text"
        autoFocus
        maxLength={120}
        value={draft}
        readOnly={saving}
        aria-busy={saving}
        aria-invalid={error !== null}
        aria-describedby={error ? errorId : undefined}
        className={`min-w-0 flex-1 rounded-xl border-0 bg-field px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-field-focus ${inputClassName}`}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
      />
      {error && (
        <span
          id={errorId}
          role="alert"
          className="block w-full text-xs text-danger"
        >
          {error}
        </span>
      )}
    </Wrapper>
  );
}
