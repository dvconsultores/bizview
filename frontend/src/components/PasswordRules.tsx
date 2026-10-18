import { Check, X } from "lucide-react";
import { useT } from "../i18n";
import { passwordChecklist } from "../lib/password";

/** Live rule checklist: icon + text, never colour alone (FR-028). */
export function PasswordRules({ password, email, current }: { password: string; email: string; current?: string }) {
  const t = useT();
  const checks = passwordChecklist(password, email, current);
  return (
    <ul className="space-y-1" aria-label={t.password.rulesLabel}>
      {checks.map((c) => (
        <li key={c.id} className={`flex items-center text-sm ${c.ok ? "text-success" : "text-ink-soft"}`}>
          {c.ok ? <Check className="mr-1.5 h-4 w-4 shrink-0" aria-hidden /> : <X className="mr-1.5 h-4 w-4 shrink-0" aria-hidden />}
          <span>
            {t.password.rules[c.id as keyof typeof t.password.rules]}
            <span className="sr-only">{c.ok ? ": cumplido" : ": pendiente"}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
