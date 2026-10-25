/** Feature 020: BI projects API (folders, editor, history, apply). */
import { api, ApiError, askReauth, qs } from "./client";
import { currentLocale, t } from "../i18n/live";
import type {
  AssistantMode,
  AssistantSession,
  HistoryItem,
  ProjectChanges,
  ProjectCheck,
  ProjectDetail,
  ProjectDiff,
  ProjectFile,
  ProjectHistory,
  ProjectImportResult,
  ProjectSummary,
  ProjectTree,
  Revision,
  RunContract,
  RunProfile,
  RevisionGroup,
  SaveResult,
  SpecTimeline,
  WorkspaceVersion,
} from "./types";

const base = (slug: string) => `/api/projects/${encodeURIComponent(slug)}`;

export const projectsApi = {
  list: () => api.get<{ projects: ProjectSummary[] }>("/api/projects").then((r) => r.projects),
  /** The list plus whether PROJECTS_DIR can be written (020 T090). */
  listing: () => api.get<{ projects: ProjectSummary[]; folder_writable: boolean }>("/api/projects"),
  suggestSlug: (name: string) =>
    api.get<{ slug: string }>(`/api/projects/slug${qs({ name })}`).then((r) => r.slug),
  create: (body: { name: string; slug?: string; description?: string }) =>
    api.post<ProjectSummary>("/api/projects", body),
  get: (slug: string) => api.get<ProjectDetail>(base(slug)),
  update: (slug: string, body: { name?: string; description?: string; slug?: string }) =>
    api.patch<ProjectDetail>(base(slug), body),
  tree: (slug: string) => api.get<ProjectTree>(`${base(slug)}/tree`),
  file: (slug: string, path: string) => api.get<ProjectFile>(`${base(slug)}/file${qs({ path })}`),
  save: (slug: string, body: { path: string; content: string; base_sha256: string | null;
                                force?: boolean }) =>
    api.put<SaveResult>(`${base(slug)}/file`, body),
  ops: (slug: string, ops: Record<string, unknown>[]) =>
    api.post<ProjectCheck & { results: unknown[] }>(`${base(slug)}/ops`, { ops }),
  changes: (slug: string, after: number) =>
    api.get<ProjectChanges>(`${base(slug)}/changes${qs({ after })}`),
  validate: (slug: string) => api.post<ProjectCheck>(`${base(slug)}/validate`),
  apply: (slug: string) =>
    api.post<{ version: WorkspaceVersion; revalidated: boolean; project: ProjectDetail }>(
      `${base(slug)}/apply`),
  remove: (slug: string) => api.del<void>(base(slug)),
  convert: (slug: string) => api.post<ProjectDetail>(`${base(slug)}/convert`),
  requestPreview: (slug: string) => api.post<{ preview: unknown }>(`${base(slug)}/preview`),
  history: (slug: string, params: { path?: string; spec?: string; before?: number } = {}) =>
    api.get<ProjectHistory>(`${base(slug)}/history${qs(params)}`),
  revision: (slug: string, id: number) =>
    api.get<Revision & { content: string | null }>(`${base(slug)}/history/${id}`),
  diff: (slug: string, from: number, to?: number) =>
    api.get<ProjectDiff>(`${base(slug)}/diff${qs({ from, to })}`),
  restore: (slug: string, id: number, base_sha256: string | null) =>
    api.post<ProjectCheck>(`${base(slug)}/history/${id}/restore`, { base_sha256 }),
  timeline: (slug: string, folder: string) =>
    api.get<SpecTimeline>(`${base(slug)}/specs/${encodeURIComponent(folder)}/timeline`),
  exportUrl: (slug: string) => `${base(slug)}/export.zip`,
  sessions: (slug: string) =>
    api.get<{ sessions: AssistantSession[] }>(`/api/assistant/sessions${qs({ project: slug })}`)
      .then((r) => r.sessions),
  createSession: (project: string, title?: string) =>
    api.post<AssistantSession>("/api/assistant/sessions", { project, ...(title ? { title } : {}) }),
  setCurrentSpec: (sessionId: number, spec: string) =>
    api.post<AssistantSession>(`/api/assistant/sessions/${sessionId}/spec`, { spec }),
  proposal: (text: string) =>
    api.post<{ name: string; slug: string }>("/api/assistant/project-proposal", { text }),
  /** Feature 028: the composer selector (ask | edit | auto). */
  setMode: (sessionId: number, mode: AssistantMode) =>
    api.post<AssistantSession>(`/api/assistant/sessions/${sessionId}/mode`, { mode }),
  /** Feature 028: confirm the run contract with its single step-up. */
  confirmContract: (sessionId: number,
                    body: { contract: RunContract; password?: string; code?: string | null;
                            profile_id?: number | null }) =>
    api.post<{ run: AssistantSession["contract"]; session: AssistantSession }>(
      `/api/assistant/sessions/${sessionId}/contract`, body),
  cancelContract: (sessionId: number) =>
    api.post<void>(`/api/assistant/sessions/${sessionId}/contract/cancel`, {}),
  runProfiles: () =>
    api.get<{ items: RunProfile[] }>("/api/assistant/run-profiles").then((r) => r.items),
  saveRunProfile: (body: { name: string; contract: Partial<RunContract> }) =>
    api.post<RunProfile>("/api/assistant/run-profiles", body),
  updateRunProfile: (id: number, body: { name: string; contract: Partial<RunContract> }) =>
    api.patch<RunProfile>(`/api/assistant/run-profiles/${id}`, body),
  removeRunProfile: (id: number) => api.del<void>(`/api/assistant/run-profiles/${id}`),
};

/** Raw zip upload (the JSON client only sends JSON); same step-up retry as `api`. */
export async function importProjectZip(
  file: Blob,
  params: { name?: string; slug?: string } = {},
): Promise<ProjectImportResult> {
  const send = () => fetch(`/api/projects/import${qs(params)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/zip", "X-Requested-With": "fetch",
               Accept: "application/json", "Accept-Language": currentLocale() },
    body: file,
  });
  let res: Response;
  try {
    res = await send();
    if (res.status === 403) {
      const code = (await res.clone().json().catch(() => null))?.error?.code;
      if (code === "reauth_required" && (await askReauth())) res = await send();
    }
  } catch {
    throw new ApiError(0, "network", t.errors.network);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error ?? {};
    throw new ApiError(res.status, e.code ?? "error", e.message ?? t.common.unexpected);
  }
  return data as ProjectImportResult;
}

/** Is this item of the history a revision group (vs an apply event)? */
export function isRevisionGroup(item: HistoryItem): item is RevisionGroup {
  return "files" in item && Array.isArray(item.files);
}
