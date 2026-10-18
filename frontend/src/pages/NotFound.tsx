import { Ban, Home } from "lucide-react";
import type { ReactNode } from "react";
import { ButtonLink } from "../components/Button";
import { Card } from "../components/Card";
import { useT } from "../i18n";

export function MessagePage({ mark, title, text }: { mark: ReactNode; title: string; text: string }) {
  const t = useT();
  return (
    <div className="py-8 sm:py-12">
      <Card tone="accent" className="p-6 text-center sm:p-8">
        {mark}
        <h1 className="mt-4 text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h1>
        <p className="mt-2 text-ink-muted">{text}</p>
        <div className="mt-6 flex justify-center">
          <ButtonLink to="/" variant="primary" icon={<Home className="h-5 w-5" aria-hidden />}>
            {t.notFound.home}
          </ButtonLink>
        </div>
      </Card>
    </div>
  );
}

export function NotFound() {
  const t = useT();
  return (
    <MessagePage
      mark={<p className="text-7xl font-extrabold text-accent" aria-hidden>404</p>}
      title={t.notFound.title}
      text={t.notFound.text}
    />
  );
}

export function ForbiddenMark() {
  return (
    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-danger-soft text-danger">
      <Ban className="h-8 w-8" aria-hidden />
    </div>
  );
}
