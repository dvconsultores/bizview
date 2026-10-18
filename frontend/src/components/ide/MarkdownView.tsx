import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router";
import remarkGfm from "remark-gfm";
import { Code2 } from "lucide-react";
import { Button } from "../Button";
import { useT } from "../../i18n";

/** Spec documents rendered (tables, task lists read-only, no raw HTML) with a "Ver código"
 * switch back to the editor. With `resolveLink` (Ayuda, feature 023) only `app:` links the
 * viewer may open become router links; every other link is plain text. */
export function MarkdownView(props: {
  text: string;
  header?: ReactNode;
  onShowCode?: () => void;
  resolveLink?: (href: string) => string | null;
}) {
  const t = useT();
  const { resolveLink } = props;
  return (
    <div className="flex h-full min-h-0 flex-col">
      {(props.header || props.onShowCode) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-subtle px-3 py-2">
          <div className="min-w-0 flex-1">{props.header}</div>
          {props.onShowCode && (
            <Button variant="secondary" icon={<Code2 className="h-4 w-4" aria-hidden />}
                    onClick={props.onShowCode}>
              {t.projects.viewCode}
            </Button>
          )}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-auto">
        <article className="space-y-3 break-words p-4 text-sm leading-relaxed text-ink [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:mt-4 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:font-semibold [&_li]:ml-5 [&_ol]:list-decimal [&_ul]:list-disc">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            urlTransform={resolveLink ? (url) => url : undefined}
            components={{
              a: ({ href, children }) => {
                if (resolveLink) {
                  const to = href?.startsWith("app:") ? resolveLink(href.slice(4)) : null;
                  return to ? (
                    <Link to={to} className="text-accent underline underline-offset-2 hover:text-accent-strong">
                      {children}
                    </Link>
                  ) : (
                    <span>{children}</span>
                  );
                }
                const web = !!href && /^https?:\/\//.test(href);
                return (
                  <a href={href} target={web ? "_blank" : undefined}
                     rel={web ? "noopener noreferrer" : undefined}
                     className="text-accent underline underline-offset-2 hover:text-accent-strong">
                    {children}
                  </a>
                );
              },
              table: ({ children }) => (
                <div className="overflow-x-auto rounded-card border border-line">
                  <table className="w-full border-collapse text-sm [&_td]:border-t [&_td]:border-line [&_td]:px-2 [&_td]:py-1 [&_th]:bg-subtle [&_th]:px-2 [&_th]:py-1 [&_th]:text-left">
                    {children}
                  </table>
                </div>
              ),
              pre: ({ children }) => (
                <pre className="overflow-x-auto rounded-card bg-surface-2 p-3 text-xs">{children}</pre>
              ),
              code: ({ className, children }) => (
                <code className={`rounded bg-surface-2 px-1 font-mono text-xs ${className ?? ""}`}>
                  {children}
                </code>
              ),
              input: ({ type, checked }) =>
                type === "checkbox" ? (
                  <input type="checkbox" checked={!!checked} readOnly disabled className="mr-1 align-middle" />
                ) : null,
            }}
          >
            {props.text}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
