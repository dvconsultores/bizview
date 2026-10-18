import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";

/** Version, license, and the source-code link every user must be offered (AGPL-3.0 §13). */
export function SourceFooter({ className = "" }: { className?: string }) {
  const t = useT();
  const { product_name, version, source_url, license, footer_credit } = useBranding();
  const licenseName = license.replace(/-or-later$/, "");
  return (
    <footer className={`text-center text-xs text-ink-soft ${className}`}>
      <span>
        © {new Date().getFullYear()} {product_name}
      </span>
      {version ? <span> · {t.footer.version(version)}</span> : null}
      <span> · </span>
      {source_url ? (
        <a href={source_url} target="_blank" rel="noopener noreferrer" className="underline decoration-line-strong underline-offset-2 hover:text-accent">
          {t.footer.source} · {licenseName}
        </a>
      ) : (
        <span>{licenseName}</span>
      )}
      {footer_credit ? <span> - {footer_credit}</span> : null}
    </footer>
  );
}
