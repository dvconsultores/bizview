import { RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { useT } from "../i18n";
import { reloadApp, useNewVersion } from "../lib/appVersion";
import { Button } from "./Button";

/**
 * "A new version is available" (feature 025): a self-hosted installation is updated in place, so a
 * tab left open keeps running the bundle it loaded. Shown only when the deployed entry document
 * points at another build than the one this page is running — never a modal, never in the way.
 */
export function UpdateBanner() {
  const t = useT();
  const stale = useNewVersion();
  const [dismissed, setDismissed] = useState(false);

  if (!stale || dismissed) return null;

  return (
    <div
      role="status"
      className="mx-4 mt-4 flex flex-wrap items-center gap-2 rounded-xl bg-accent-soft p-3 text-sm text-accent-deep ring-1 ring-inset ring-accent-line sm:mx-6 lg:mx-8"
    >
      <RefreshCw className="h-5 w-5 shrink-0" aria-hidden />
      <p className="min-w-0 flex-1">{t.update.available}</p>
      <Button size="sm" onClick={reloadApp}>{t.update.reload}</Button>
      <Button size="sm" variant="ghost" onClick={() => setDismissed(true)}>{t.update.later}</Button>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label={t.update.dismiss}
        title={t.update.dismiss}
        className="control-compact inline-flex min-w-tap items-center justify-center rounded-lg text-accent-deep hover:bg-accent-soft-2"
      >
        <X className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
