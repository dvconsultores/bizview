import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router";
import { api } from "../../api/client";
import type { AssistantSession } from "../../api/types";
import { Spinner } from "../../components/Spinner";
import { useT } from "../../i18n";

/** Old conversation links (`/admin/asistente/:id`) open the conversation inside its project. */
export function RedirectToProject() {
  const t = useT();
  const { id } = useParams<{ id: string }>();
  const [target, setTarget] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.get<AssistantSession>(`/api/assistant/sessions/${id}`)
      .then((s) => !cancelled && setTarget(s.project ? `/proyectos/${s.project.slug}?chat=${s.id}` : "/proyectos"))
      .catch(() => !cancelled && setTarget("/proyectos"));
    return () => { cancelled = true; };
  }, [id]);
  if (target) return <Navigate to={target} replace />;
  return (
    <div role="status" className="flex justify-center py-12 text-accent">
      <Spinner className="h-8 w-8" /><span className="sr-only">{t.common.loading}</span>
    </div>
  );
}
