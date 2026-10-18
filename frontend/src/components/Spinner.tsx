import { useT } from "../i18n";

export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export function FullPageSpinner() {
  const t = useT();
  return (
    <div className="flex min-h-screen items-center justify-center text-accent" role="status">
      <Spinner className="h-8 w-8" />
      <span className="sr-only">{t.common.loading}</span>
    </div>
  );
}
