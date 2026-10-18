import { Maximize, X } from "lucide-react";
import { useId, type ReactNode } from "react";
import { useT } from "../../i18n";
import { Button } from "../Button";

export interface TvLayoutProps {
  title: string;
  periodText: string;
  rangeText: string | null;
  updatedText: string;
  status: ReactNode;
  fullscreenAvailable: boolean;
  fullscreen: boolean;
  onFullscreen: () => void;
  onExit: () => void;
  children: ReactNode;
}

export function TvLayout(props: TvLayoutProps) {
  const t = useT();
  const titleId = useId();

  return (
    <section aria-labelledby={titleId} data-testid="tv-layout" className="min-h-[calc(100vh-2rem)]">
      <header className="flex flex-col gap-4 border-b border-line pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1
            id={titleId}
            className="text-2xl font-bold tracking-tight text-ink [overflow-wrap:anywhere] sm:text-3xl xl:text-5xl"
          >
            {props.title}
          </h1>

          <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2 text-base sm:text-lg xl:text-2xl">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-soft sm:text-sm xl:text-base">
                {t.reportParams.contextPeriod}
              </dt>
              <dd className="font-semibold text-ink">
                <span>{props.periodText}</span>
                {props.rangeText ? <span className="font-normal text-ink-2">{" · "}{props.rangeText}</span> : null}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-soft sm:text-sm xl:text-base">
                {t.reportParams.contextUpdated}
              </dt>
              <dd className="font-semibold text-ink tabular-nums">{props.updatedText}</dd>
            </div>
          </dl>

          <div className="mt-2">{props.status}</div>
        </div>

        <div className="flex flex-wrap gap-2">
          {props.fullscreenAvailable && !props.fullscreen ? (
            <Button variant="secondary" icon={<Maximize className="h-5 w-5" aria-hidden />} onClick={props.onFullscreen}>
              {t.tvMode.fullscreen}
            </Button>
          ) : null}
          <Button variant="primary" icon={<X className="h-5 w-5" aria-hidden />} onClick={props.onExit}>
            {t.tvMode.exit}
          </Button>
        </div>
      </header>

      <div className="mt-6 space-y-6 xl:text-lg">{props.children}</div>
    </section>
  );
}
