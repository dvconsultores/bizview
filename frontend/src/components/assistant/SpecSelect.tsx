import { useId } from "react";
import type { SpecChoice } from "../../api/types";
import { useT } from "../../i18n";
import { Badge } from "../Badge";

/** "Spec actual" selector of a conversation header: every project spec with its stage badge. */
export function SpecSelect(props: {
  current: string | null;
  specs: SpecChoice[];
  onChange: (folder: string) => void;
  label?: string;
}) {
  const t = useT();
  const selectId = useId();
  const { current, specs, onChange, label } = props;
  const active = specs.find((spec) => spec.folder === current);
  if (specs.length === 0) return null;
  const stage = active?.stage ?? null;
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      <label className="sr-only" htmlFor={selectId}>
        {label ?? t.projects.currentSpec}
      </label>
      <select
        id={selectId}
        data-current-spec=""
        value={current ?? ""}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-tap min-w-0 max-w-[13rem] rounded-card border border-line bg-surface px-2 text-sm text-ink"
      >
        <option value="">{t.projects.noCurrentSpec}</option>
        {specs.map((spec) => (
          <option key={spec.folder} value={spec.folder}>
            {spec.stage
              ? `${spec.folder} · ${t.projects.stage[spec.stage]}`
              : spec.folder}
          </option>
        ))}
      </select>
      {stage ? <Badge tone="gray">{t.projects.stage[stage]}</Badge> : null}
    </span>
  );
}
