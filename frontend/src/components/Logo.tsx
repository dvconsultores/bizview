import { useBranding } from "../config/BrandingContext";
import { initials } from "../lib/format";

/** Configured logo, or a text mark from the product name's first word, e.g. "Bizview AI Powered"
 * → "BI" (no customer hard-coded). */
export function Logo({ className = "h-9 w-9", inverted = false }: { className?: string; inverted?: boolean }) {
  const { logo_url, product_name } = useBranding();
  if (logo_url && inverted) {
    return (
      <span className={`${className} inline-flex items-center justify-center rounded-lg bg-white p-1 ring-1 ring-white/30`}>
        <img src={logo_url} alt="" className="h-full w-full object-contain" />
      </span>
    );
  }
  if (logo_url) return <img src={logo_url} alt="" className={`${className} rounded-lg object-contain`} />;
  return (
    <span
      aria-hidden
      className={`${className} inline-flex items-center justify-center rounded-lg text-sm font-bold ${
        inverted ? "bg-white/15 text-white ring-1 ring-white/30" : "bg-primary text-white"
      }`}
    >
      {initials(product_name.trim().split(/\s+/)[0] ?? product_name)}
    </span>
  );
}
