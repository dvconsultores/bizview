import { useId, type ReactNode } from "react";
import { useT } from "../i18n";
import { dateTimeFormat } from "../lib/intl";

export interface WelcomeBannerProps {
  name: string;
  chip?: ReactNode;
  subtitle?: ReactNode;
  date?: Date;
  className?: string;
}

function isoDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** The home page greeting on the brand gradient (feature 010, Customer A look). */
export function WelcomeBanner({ name, chip, subtitle, date = new Date(), className = "" }: WelcomeBannerProps) {
  const t = useT();
  const titleId = useId();
  const title = name.trim() ? `${t.design.welcomeBack}, ${name}` : t.design.welcomeBack;
  const formatted = dateTimeFormat({
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  }).format(date);
  const formattedDateCapitalized = formatted.charAt(0).toUpperCase() + formatted.slice(1);

  return (
    <section
      aria-labelledby={titleId}
      className={`relative overflow-hidden rounded-3xl bg-brand-gradient p-6 text-on-primary sm:p-8 lg:p-10 ${className}`}
    >
      <span aria-hidden className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-white/15 opacity-60" />
      <div className="relative">
        {chip ? (
          <span className="inline-flex rounded-full px-3 py-1 text-xs font-semibold tracking-wide ring-1 ring-inset ring-white/30">{chip}</span>
        ) : null}
        <h1 id={titleId} className="mt-3 text-2xl font-bold tracking-tight break-words lg:text-3xl">
          {title}
        </h1>
        {subtitle ? <p className="mt-1 max-w-2xl text-sm text-on-primary">{subtitle}</p> : null}
        <p className="mt-3 text-xs font-medium text-on-primary sm:text-sm">
          <time dateTime={isoDate(date)}>{formattedDateCapitalized}</time>
        </p>
      </div>
    </section>
  );
}
