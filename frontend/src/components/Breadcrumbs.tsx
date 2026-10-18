import { ChevronRight } from "lucide-react";
import { Link } from "react-router";
import { useT } from "../i18n";
import { BackLink } from "./BackLink";

export interface Crumb {
  label: string;
  to?: string;
}

export interface BreadcrumbsProps {
  back?: string;
  items: Crumb[];
  className?: string;
}

export function Breadcrumbs({ back, items, className = "" }: BreadcrumbsProps) {
  const t = useT();
  return (
    <div className={`mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 ${className}`}>
      {back ? <BackLink to={back} className="" /> : null}
      {items.length > 0 ? (
        <nav aria-label={t.design.breadcrumbs} className="min-w-0">
          <ol className="flex flex-wrap items-center gap-1.5 text-sm text-ink-muted">
            {items.map((item, index) => {
              const isLast = index === items.length - 1;
              return (
                <li key={`${item.label}-${index}`} className="inline-flex min-w-0 items-center gap-1.5">
                  {index > 0 ? <ChevronRight className="h-3.5 w-3.5 shrink-0 text-ink-faint" aria-hidden /> : null}
                  {isLast ? (
                    <span aria-current="page" className="truncate font-medium text-accent">
                      {item.label}
                    </span>
                  ) : item.to ? (
                    <Link to={item.to} className="inline-flex min-h-tap items-center rounded-md hover:text-accent hover:underline">
                      {item.label}
                    </Link>
                  ) : (
                    <span>{item.label}</span>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      ) : null}
    </div>
  );
}
