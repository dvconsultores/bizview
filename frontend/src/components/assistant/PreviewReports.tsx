import { useState } from "react";
import { Eye, FileDown } from "lucide-react";
import { api, ApiError } from "../../api/client";
import type { ReportData, ReportDefinition } from "../../api/types";
import { useT } from "../../i18n";
import { downloadPdf } from "../../lib/download";
import { Alert } from "../Alert";
import { Button } from "../Button";
import { Spinner } from "../Spinner";
import { ReportViews } from "../report/ReportViews";

/** Reports of a succeeded preview rendered with the real report views (014), for a project's
 * preview (`/api/projects/<slug>/preview/report/<id>`), each with its preview PDF. */
export function PreviewReports(props: { base: string; reportIds: string[] }) {
  const t = useT();
  const [open, setOpen] = useState<string | null>(null);
  const [state, setState] = useState<{ def: ReportDefinition; data: ReportData } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfBusy, setPdfBusy] = useState<string | null>(null);

  const show = async (rid: string) => {
    setOpen(rid);
    setState(null);
    setError(null);
    setLoading(true);
    try {
      const url = `${props.base}/preview/report/${encodeURIComponent(rid)}`;
      const def = await api.get<ReportDefinition>(url);
      const data = await api.get<ReportData>(`${url}/data`);
      setState({ def, data });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    } finally {
      setLoading(false);
    }
  };

  const pdf = async (rid: string) => {
    if (pdfBusy) return;
    setPdfBusy(rid);
    setError(null);
    try {
      await downloadPdf(`${props.base}/preview/report/${encodeURIComponent(rid)}/pdf`,
                        `${rid}-vista-previa.pdf`, t.assistant.previewPdfError);
    } catch (e) {
      setError(e instanceof Error ? e.message : t.assistant.previewPdfError);
    } finally {
      setPdfBusy(null);
    }
  };

  if (props.reportIds.length === 0) return null;
  return (
    <section className="space-y-3" aria-label={t.projects.preview}>
      <div className="flex flex-wrap gap-2">
        {props.reportIds.map((rid) => (
          <div key={rid} className="flex flex-wrap gap-2">
            <Button variant={open === rid ? "primary" : "secondary"}
                    icon={<Eye className="h-4 w-4" aria-hidden />} onClick={() => void show(rid)}>
              {rid}
            </Button>
            <Button variant="ghost" icon={<FileDown className="h-4 w-4" aria-hidden />}
                    loading={pdfBusy === rid} onClick={() => void pdf(rid)}>
              {t.assistant.previewPdf}: {rid}
            </Button>
          </div>
        ))}
      </div>
      {loading && <div role="status" className="flex justify-center py-6 text-accent"><Spinner className="h-6 w-6" /><span className="sr-only">{t.common.loading}</span></div>}
      {error && <Alert tone="error">{error}</Alert>}
      {state && <div className="space-y-4"><ReportViews def={state.def} data={state.data} /></div>}
    </section>
  );
}
