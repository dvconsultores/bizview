import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router";
import { useOptionalUser } from "../../auth/AuthContext";
import { resolveAppLink, splitAppLinks } from "../../lib/appLinks";
import { useAssistantPanelOptional } from "./AssistantPanelContext";

/** An assistant answer: text as written, with in-app links the viewer can open (feature 023).
 * Disallowed or unknown links show their label only; other schemes stay literal. */
export function ChatText({ text }: { text: string }) {
  const user = useOptionalUser();
  const panel = useAssistantPanelOptional();
  const onNavigate = () => {
    // Phones and tablets: the docked panel covers the page, so it collapses after navigating.
    if (typeof window !== "undefined" && window.matchMedia?.("(max-width: 1023px)").matches) {
      panel?.close();
    }
  };
  return (
    <p className="min-w-0 whitespace-pre-wrap text-base leading-relaxed text-ink">
      {splitAppLinks(text).map((part, i) => {
        const to = part.to ? resolveAppLink(part.to, user) : null;
        if (!to) return <span key={i}>{part.text}</span>;
        return (
          <Link
            key={i}
            to={to}
            onClick={onNavigate}
            className="inline-flex items-center gap-0.5 py-1 text-accent underline underline-offset-2 hover:text-accent-strong"
          >
            {part.text}
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        );
      })}
    </p>
  );
}
