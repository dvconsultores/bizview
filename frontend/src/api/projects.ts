/** Feature 020: BI projects API (folders, editor, history, apply). */
import { api, ApiError, askReauth, qs } from "./client";
import { currentLocale, t } from "../i18n/live";
import type {
  HistoryItem,
  ImportLimits,
  ProjectChanges,
  ProjectCheck,
  ProjectDetail,
  ProjectDiff,
  ProjectFix,
  FixResult,
  ProjectFile,
  ProjectHistory,
  ProjectImportResult,
  ProjectRevision,
  ProjectRevisionList,
  ProjectSummary,
  ProjectTree,
  Revision,
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
  /** Feature 049: the two import allowances in force, so the browser can refuse before uploading. */
  limits: () => api.get<ImportLimits>("/api/projects/limits"),
  saveLimits: (body: Record<string, number | null>) =>
    api.put<ImportLimits>("/api/projects/limits", body),
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
  /** `checkOrigin` runs every query against its source (the «Volver a comprobar» button); the
   * editor's refreshes pass false — a background change is not the moment to hit the source. */
  validate: (slug: string, opts: { checkOrigin?: boolean } = {}) =>
    api.post<ProjectCheck>(
      `${base(slug)}/validate${qs({ check_origin: String(opts.checkOrigin ?? true) })}`),
  /** 035: apply the validator's deterministic corrections (works with the AI off). */
  applyFixes: (slug: string, fixes: (ProjectFix & { problem_id?: string | null
                                                   base_sha256?: string | null })[]) =>
    api.post<FixResult>(`${base(slug)}/fix`, { fixes }),
  apply: (slug: string) =>
    api.post<{ version: WorkspaceVersion; revalidated: boolean; project: ProjectDetail }>(
      `${base(slug)}/apply`),
  remove: (slug: string) => api.del<void>(base(slug)),
  convert: (slug: string) => api.post<ProjectDetail>(`${base(slug)}/convert`),
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
  /** Feature 055: the project's own revisions, newest first. */
  revisions: (slug: string) => api.get<ProjectRevisionList>(`${base(slug)}/revisions`),
  revisionZipUrl: (slug: string, number: number) =>
    `${base(slug)}/revisions/${number}/zip`,
  /** Write an older revision back as a new draft and apply it (step-up). */
  revert: (slug: string, number: number) =>
    api.post<{ revision: ProjectRevision; restored: number; missing: string[] }>(
      `${base(slug)}/revisions/${number}/revert`),
};

/** Raw zip upload (the JSON client only sends JSON); same step-up retry as `api`. */
export interface ImportParams {
  name?: string;
  slug?: string;
  /** Ask for a second project instead of a revision of the one this slug belongs to. */
  copy?: boolean;
  /** Answer the diff and write nothing. */
  dryRun?: boolean;
  /** Accept overwriting the editor changes the draft holds. */
  replaceDraft?: boolean;
}

export async function importProjectZip(
  file: Blob,
  params: ImportParams = {},
): Promise<ProjectImportResult> {
  const query = qs({
    name: params.name, slug: params.slug,
    copy: params.copy ? "true" : undefined,
    dry_run: params.dryRun ? "true" : undefined,
    replace_draft: params.replaceDraft ? "true" : undefined,
  });
  const send = () => fetch(`/api/projects/import${query}`, {
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
