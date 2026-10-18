import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { useT } from "../i18n";
import { Button } from "./Button";

/** Clipboard API with an execCommand fallback (older iOS/Android, non-secure origins). */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through */
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  area.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  document.body.removeChild(area);
  return ok;
}

export function CopyButton({ text }: { text: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(id);
  }, [copied]);
  return (
    <Button
      variant="secondary"
      icon={copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
      onClick={async () => setCopied(await copyText(text))}
    >
      <span aria-live="polite">{copied ? t.common.copied : t.common.copy}</span>
    </Button>
  );
}

export function SecretBox({ value }: { value: string }) {
  return (
    <div className="select-all break-all rounded-xl bg-subtle p-3 font-mono text-lg text-ink ring-1 ring-inset ring-line">
      {value}
    </div>
  );
}
