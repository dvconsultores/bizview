import { Sparkles } from "lucide-react";
import { useNavigate } from "react-router";
import { useAuth } from "../../auth/AuthContext";
import { useBranding } from "../../config/BrandingContext";
import { useT } from "../../i18n";
import { useAssistantPanel } from "./AssistantPanelContext";

/** Top-bar button that opens/closes the docked assistant (super user, AI configured). */
export function AssistantToggle() {
  const t = useT();
  const { user } = useAuth();
  const { ai_enabled } = useBranding();
  const { mode, toggle } = useAssistantPanel();
  const navigate = useNavigate();
  if (!user?.is_superuser || !ai_enabled) return null;
  const isOpen = mode !== "closed";
  // The docked panel needs room: below 1024 px the full Asistente page (a view) is used.
  const onClick = () => {
    const narrow = typeof window.matchMedia === "function" && !window.matchMedia("(min-width: 1024px)").matches;
    if (narrow) navigate("/admin/asistente");   // the page shows the remembered conversation
    else toggle();
  };
  return (
    <button
      id="assistant-toggle"
      type="button"
      aria-label={isOpen ? t.assistant.closePanel : t.assistant.openPanel}
      title={isOpen ? t.assistant.closePanel : t.assistant.openPanel}
      aria-expanded={isOpen}
      aria-controls="assistant-panel"
      onClick={onClick}
      className={`inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl ${
        isOpen
          ? "text-on-primary hover:bg-white/10 lg:bg-primary lg:hover:bg-primary-hover"
          : "text-on-primary hover:bg-white/10 lg:text-ink-muted lg:hover:bg-subtle lg:hover:text-ink"
      }`}
    >
      <Sparkles className="h-5 w-5" aria-hidden />
    </button>
  );
}
