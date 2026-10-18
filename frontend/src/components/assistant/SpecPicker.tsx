import { useId } from "react";
import type { SpecChoice } from "../../api/types";
import { useT } from "../../i18n";

/** Inline choice of the conversation's current spec when a command needs one (409 needs_spec). */
export function SpecPicker(props: {
  command: string;
  specs: SpecChoice[];
  onPick: (folder: string) => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const t = useT();
  const titleId = useId();
  const { command, specs, onPick, onCancel, busy } = props;
  return (
    <section data-spec-picker="" className="rounded-xl border border-line bg-surface p-3 text-sm">
      <p id={titleId} className="font-medium text-ink">
        {t.assistant.commands.specPickerTitle.replace("{command}", command)}
      </p>
      {specs.length === 0 ? (
        <p className="mt-2 text-ink-muted">{t.assistant.commands.specPickerEmpty}</p>
      ) : (
        <ul aria-labelledby={titleId} className="mt-2 flex flex-col gap-2">
          {specs.map((spec) => {
            const meta = [spec.title, spec.kind, spec.stage].filter(Boolean).join(" · ");
            return (
              <li key={spec.folder}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onPick(spec.folder)}
                  className="flex min-h-tap w-full flex-wrap items-center gap-x-2 rounded-lg border border-line px-3 py-2 text-left hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
                >
                  <span className="font-mono text-ink">{spec.folder}</span>
                  {meta ? <span className="text-ink-muted">{meta}</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <button
        type="button"
        onClick={onCancel}
        disabled={busy}
        className="mt-3 inline-flex min-h-tap items-center rounded-lg border border-line px-3 text-sm text-ink hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
      >
        {t.assistant.commands.cancel}
      </button>
    </section>
  );
}
