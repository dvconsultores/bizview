import { useEffect } from "react";
import { useNavigate } from "react-router";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { AssistantView } from "../../components/assistant/AssistantPanel";
import { useAssistantPanel } from "../../components/assistant/AssistantPanelContext";
import { useT } from "../../i18n";

const wide = () => typeof window.matchMedia === "function" && window.matchMedia("(min-width: 1024px)").matches;

/** The assistant chat as a page on phones and tablets, where the docked panel has no room.
 * On wide screens there is only the panel: this address opens it and goes to the home page. */
export function AssistantPage() {
  const t = useT();
  const { open } = useAssistantPanel();
  const navigate = useNavigate();
  const desktop = wide();
  useEffect(() => {
    if (!desktop) return;
    open();
    navigate("/", { replace: true });
  }, [desktop, open, navigate]);
  if (desktop) return null;
  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs back="/" items={[{ label: t.nav.admin, to: "/admin" }, { label: t.assistant.panelTitle }]} />
      <AssistantView placement="page" />
    </div>
  );
}
