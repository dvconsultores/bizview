import { Shield, User as UserIcon } from "lucide-react";
import type { Role } from "../api/types";
import { useT } from "../i18n";

/** Two large radio tiles for the role; `adminDisabled` greys out only the admin option. */
export function RoleTiles({
  value,
  onChange,
  disabled = false,
  adminDisabled = false,
  hint,
}: {
  value: Role;
  onChange: (r: Role) => void;
  disabled?: boolean;
  adminDisabled?: boolean;
  hint?: string;
}) {
  const t = useT();
  const options: { role: Role; label: string; Icon: typeof Shield; off: boolean }[] = [
    { role: "user", label: t.roles.user, Icon: UserIcon, off: disabled },
    { role: "admin", label: t.roles.admin, Icon: Shield, off: disabled || adminDisabled },
  ];
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-ink-3">{t.admin.role}</legend>
      <div className="grid grid-cols-1 gap-3 min-[400px]:grid-cols-2">
        {options.map(({ role, label, Icon, off }) => {
          const selected = value === role;
          return (
            <label
              key={role}
              className={`relative flex min-h-[64px] items-center rounded-xl border p-3 transition-colors focus-within:ring-2 focus-within:ring-accent-line-strong ${
                selected ? "border-primary bg-accent-soft ring-1 ring-primary" : "border-line-strong bg-surface"
              } ${off ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:border-accent-line-strong"}`}
            >
              <input
                type="radio"
                name="role"
                value={role}
                checked={selected}
                disabled={off}
                onChange={() => onChange(role)}
                className="sr-only"
              />
              <Icon className={`mr-2 h-5 w-5 shrink-0 ${selected ? "text-accent" : "text-ink-soft"}`} aria-hidden />
              <span className="min-w-0 break-words font-medium text-ink">{label}</span>
            </label>
          );
        })}
      </div>
      {hint ? <p className="mt-1.5 text-sm text-ink-soft">{hint}</p> : null}
    </fieldset>
  );
}
