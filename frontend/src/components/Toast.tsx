import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

type Tone = "success" | "warning";
const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const [tone, setTone] = useState<Tone>("success");
  const timer = useRef<number | undefined>(undefined);
  const show = useCallback((m: string, t: Tone = "success") => {
    setMessage(m);
    setTone(t);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setMessage(null), 3500);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-24 z-50 flex justify-center px-4 lg:bottom-6">
        {message ? (
          <div className="pointer-events-auto flex items-center rounded-xl bg-toast px-4 py-3 text-sm font-medium text-white shadow-raised">
            {/* The toast is dark in both themes, so its icons use fixed light tints. */}
            {tone === "warning"
              ? <AlertTriangle className="mr-2 h-5 w-5 shrink-0 text-amber-300" aria-hidden />
              : <CheckCircle2 className="mr-2 h-5 w-5 shrink-0 text-emerald-400" aria-hidden />}
            {message}
          </div>
        ) : null}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
