import { Eye, EyeOff, Lock } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { FieldDef } from "../api/types";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Input } from "./Input";
import { useT } from "../i18n";



export const PEM_CLASS =
  "block w-full rounded-xl border border-transparent bg-field px-4 py-3 font-mono text-xs text-ink placeholder-ink-faint transition-colors focus:outline-none focus:ring-2 focus:ring-field-focus";

export const PEM_ERROR_CLASS =
  "block w-full rounded-xl border border-danger-border bg-field px-4 py-3 font-mono text-xs text-ink placeholder-ink-faint transition-colors focus:outline-none focus:ring-2 focus:ring-danger-focus";

export function pemClass(error?: string | null): string {
  return error ? PEM_ERROR_CLASS : PEM_CLASS;
}

export function PemField({
  id,
  label,
  required = false,
  value,
  onChange,
  error = null,
  help = null,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  value: string;
  onChange: (v: string) => void;
  error?: string | null;
  help?: string | null;
  children?: ReactNode;
}) {
  const errorId = error ? `${id}-error` : undefined;
  const hintId = help ? `${id}-hint` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline gap-0.5">
        <label htmlFor={id} className="block text-sm font-semibold text-ink-2">
          {label}
        </label>
        {required ? (
          <span aria-hidden="true" className="text-danger">
            *
          </span>
        ) : null}
      </div>
      <textarea
        id={id}
        rows={6}
        className={pemClass(error)}
        value={value}
        autoComplete="off"
        spellCheck={false}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(e) => onChange(e.target.value)}
      />
      {error ? (
        <p id={errorId} className="mt-1.5 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {help ? (
        <p id={hintId} className="mt-1.5 text-sm text-ink-soft">
          {help}
        </p>
      ) : null}
      {children}
    </div>
  );
}

/** Write-only credential (feature 004, FR-004/FR-005). The stored value never reaches the
 * browser. `value`: undefined = keep stored, string = new value, null = remove on save. */
export function SecretField({
  field,
  configured,
  value,
  onChange,
  error,
}: {
  field: Pick<FieldDef, "name" | "label" | "type" | "required" | "help">;
  configured: boolean;
  value: string | null | undefined;
  onChange: (v: string | null | undefined) => void;
  error?: string | null;
}) {
  const t = useT();
  const [visible, setVisible] = useState(false);
  const label = field.label;
  const mark = field.required ? <span aria-hidden="true" className="text-danger">*</span> : null;
  const id = `secret-${field.name}`;

  if (configured && value === undefined) {
    return (
      <div>
        <p className="mb-1.5 text-sm font-semibold text-ink-2">{label}{mark}</p>
        <div className="flex flex-wrap items-center">
          <Badge tone="green" icon={<Lock className="h-3.5 w-3.5" aria-hidden />}>{t.admin.secretField.configured}</Badge>
          <Button variant="ghost" className="ml-2" onClick={() => onChange("")}>{t.admin.secretField.replace}</Button>
          {!field.required ? <Button variant="ghost" onClick={() => onChange(null)}>{t.admin.secretField.remove}</Button> : null}
        </div>
        {error ? <p className="mt-1.5 text-sm text-danger">{error}</p> : null}
      </div>
    );
  }
  if (value === null) {
    return (
      <div>
        <p className="mb-1.5 text-sm font-semibold text-ink-2">{label}{mark}</p>
        <div className="flex flex-wrap items-center">
          <span className="text-sm text-warning-strong">{t.admin.secretField.willRemove}</span>
          <Button variant="ghost" className="ml-2" onClick={() => onChange(undefined)}>{t.admin.secretField.undo}</Button>
        </div>
      </div>
    );
  }
  const cancel = configured ? (
    <Button variant="ghost" onClick={() => onChange(undefined)}>{t.admin.secretField.cancel}</Button>
  ) : null;
  if (field.type === "pem") {
    return (
      <PemField
        id={id}
        label={label}
        required={field.required}
        value={value ?? ""}
        onChange={onChange}
        error={error}
        help={field.help}
      >
        {cancel}
      </PemField>
    );
  }
  return (
    <div>
      <Input
        id={id}
        label={label}
        required={field.required}
        type={visible ? "text" : "password"}
        autoComplete="new-password"
        autoCapitalize="none"
        spellCheck={false}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        error={error}
        hint={field.help || undefined}
        trailing={
          <button type="button" onClick={() => setVisible((v) => !v)} aria-label={visible ? t.admin.secretField.hide : t.admin.secretField.show}
            aria-pressed={visible}
            className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-lg text-ink-soft hover:text-accent">
            {visible ? <EyeOff className="h-5 w-5" aria-hidden /> : <Eye className="h-5 w-5" aria-hidden />}
          </button>
        }
      />
      {cancel}
    </div>
  );
}
