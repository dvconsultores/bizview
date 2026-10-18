import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ReactNode } from "react";

type Tone = "info" | "success" | "warning" | "error";

const STYLES: Record<Tone, { box: string; Icon: typeof Info }> = {
  info: { box: "bg-accent-soft text-accent-deep ring-accent-line", Icon: Info },
  success: { box: "bg-success-soft text-success-deep ring-success-line", Icon: CheckCircle2 },
  warning: { box: "bg-warning-soft text-warning-deep ring-warning-line", Icon: AlertTriangle },
  error: { box: "bg-danger-soft text-danger-deep ring-danger-line", Icon: XCircle },
};

/** Errors are announced immediately (role=alert); others politely (role=status). */
export function Alert({ tone = "info", children, action }: { tone?: Tone; children: ReactNode; action?: ReactNode }) {
  const { box, Icon } = STYLES[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`flex flex-wrap items-start rounded-xl p-3.5 text-sm ring-1 ring-inset ${box}`}>
      <Icon className="mr-2.5 mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
      {action ? <div className="basis-full sm:basis-auto sm:ml-3 sm:shrink-0 ml-[1.875rem] mt-1.5 sm:mt-0">{action}</div> : null}
    </div>
  );
}
