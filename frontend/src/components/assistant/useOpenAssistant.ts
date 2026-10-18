import { useNavigate } from "react-router";
import { useAssistantPanel } from "./AssistantPanelContext";

/** Opens the assistant (optionally on a conversation): the docked panel from 1024 px, the
 * Asistente page on smaller screens. */
export function useOpenAssistant(): (sessionId?: number) => void {
  const { setSessionId, open } = useAssistantPanel();
  const navigate = useNavigate();
  return (sessionId?: number) => {
    if (sessionId !== undefined) setSessionId(sessionId);
    const narrow = typeof window.matchMedia === "function" && !window.matchMedia("(min-width: 1024px)").matches;
    if (narrow) navigate("/admin/asistente");
    else open();
  };
}
