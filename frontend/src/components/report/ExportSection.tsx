import { useId, useState } from "react";
import { FileDown } from "lucide-react";
import { useT } from "../../i18n";
import { Button } from "../Button";

interface ExportSectionProps {
  pdfAvailable: boolean;
  csvAvailable: boolean;
  ready: boolean;
  pdfBusy: boolean;
  onPdf: () => void;
  onCsv: () => void;
}

// Selected state comes from React state, not CSS :has() (Safari 14 has no :has()).
const optionClass = (selected: boolean) =>
  `flex min-h-tap flex-1 cursor-pointer items-center gap-2 rounded-xl border px-3 text-sm font-semibold focus-within:ring-2 focus-within:ring-field-focus ${
    selected ? "border-accent bg-accent-soft text-accent" : "border-line bg-field text-ink-2"
  }`;

export function ExportSection({
  pdfAvailable,
  csvAvailable,
  ready,
  pdfBusy,
  onPdf,
  onCsv,
}: ExportSectionProps) {
  const t = useT();
  const headingId = useId();
  const radioName = useId();
  const [format, setFormat] = useState<"pdf" | "csv">(pdfAvailable ? "pdf" : "csv");

  if (!pdfAvailable && !csvAvailable) return null;

  return (
    <section aria-labelledby={headingId} className="mt-5 space-y-4 border-t border-line pt-5">
      <h3 id={headingId} className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
        {t.reportParams.exportSection}
      </h3>

      <fieldset>
        <legend className="text-sm font-semibold text-ink-2">{t.reportParams.exportFormat}</legend>
        <div className="mt-2 flex gap-2">
          {pdfAvailable ? (
            <label className={optionClass(format === "pdf")}>
              <input
                type="radio"
                name={radioName}
                value="pdf"
                checked={format === "pdf"}
                onChange={() => setFormat("pdf")}
                className="h-4 w-4 accent-primary"
              />
              {t.reportParams.formatPdf}
            </label>
          ) : null}
          {csvAvailable ? (
            <label className={optionClass(format === "csv")}>
              <input
                type="radio"
                name={radioName}
                value="csv"
                checked={format === "csv"}
                onChange={() => setFormat("csv")}
                className="h-4 w-4 accent-primary"
              />
              {t.reportParams.formatCsv}
            </label>
          ) : null}
        </div>
      </fieldset>

      <p className="text-xs text-ink-muted">
        {ready ? t.reportParams.exportApplied : t.reportParams.exportNotReady}
      </p>

      <Button
        type="button"
        variant="secondary"
        block
        icon={<FileDown className="h-5 w-5" aria-hidden />}
        loading={format === "pdf" && pdfBusy}
        disabled={!ready}
        onClick={format === "pdf" ? onPdf : onCsv}
      >
        {t.reportParams.generate}
      </Button>
    </section>
  );
}
