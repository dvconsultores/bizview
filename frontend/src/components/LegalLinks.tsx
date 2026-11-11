import { useT } from "../i18n";

/**
 * The installation operator's public legal pages (feature 054b follow-up). Both are optional: a
 * self-hosted installation without its own privacy policy shows nothing rather than a dead link.
 */
export function LegalLinks({
  privacyUrl,
  termsUrl,
  className = "",
}: {
  privacyUrl?: string | null;
  termsUrl?: string | null;
  className?: string;
}) {
  const t = useT();
  if (!privacyUrl && !termsUrl) return null;
  const link =
    "underline decoration-line-strong underline-offset-2 hover:text-accent";
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-3 gap-y-1 ${className}`}>
      {privacyUrl ? (
        <a href={privacyUrl} target="_blank" rel="noopener noreferrer" className={link}>
          {t.footer.privacy}
        </a>
      ) : null}
      {termsUrl ? (
        <a href={termsUrl} target="_blank" rel="noopener noreferrer" className={link}>
          {t.footer.terms}
        </a>
      ) : null}
    </span>
  );
}
