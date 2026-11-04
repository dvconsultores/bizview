/** Feature 052: the structure of a source, its sample requests and the generated pack. */
import { api, ApiError, askReauth, qs } from "./client";
import { currentLocale, t } from "../i18n/live";
import type {
  GenerateResult,
  SampleRequest,
  SampleRun,
  SourceKind,
  StructureState,
} from "./types";

const base = (name: string) => `/api/sources/${encodeURIComponent(name)}`;

export const sourcesApi = {
  /** The tab's read: the generated pack, the previous one and the live scan. */
  structureState: (name: string) => api.get<StructureState>(`${base(name)}/structure/pack`),
  /** The download the browser saves; the API answers an attachment (the generated pack if any). */
  downloadUrl: (name: string, format: "md" | "json", mode: "pack" | "scan" = "pack") =>
    `${base(name)}/structure${qs({ format, mode })}`,
  saveNotes: (name: string, notes: string) =>
    api.put<{ notes: string }>(`${base(name)}/structure/notes`, { notes }),
  setPersonal: (
    name: string,
    body: { schema_name: string; table: string; column: string; personal: boolean },
  ) => api.put<{ personal: boolean }>(`${base(name)}/structure/columns`, body),
  samples: (name: string) =>
    api.get<{ items: SampleRequest[] }>(`${base(name)}/samples`).then((r) => r.items),
  createSample: (
    name: string,
    body: { name: string; path: string; params: Record<string, string>; notes?: string },
  ) => api.post<SampleRequest>(`${base(name)}/samples`, body),
  deleteSample: (name: string, id: number) => api.del(`${base(name)}/samples/${id}`),
  runSample: (name: string, id: number) => api.post<SampleRun>(`${base(name)}/samples/${id}/run`),
  /** The generator: one POST, cancellable. The client's JSON helper has no signal, so this is raw. */
  generate: (name: string, signal?: AbortSignal) =>
    generate(`${base(name)}/structure/generate`, signal),
};

/** POST that may take minutes: step-up, redacted errors and an abort that stops waiting. */
async function generate(path: string, signal?: AbortSignal, retried = false): Promise<GenerateResult> {
  const res = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Accept": "application/json", "Accept-Language": currentLocale(),
               "X-Requested-With": "fetch" },
    signal,
  });
  if (res.status === 204) return undefined as unknown as GenerateResult;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const e = data?.error ?? {};
    const err = new ApiError(res.status, e.code ?? "error", e.message ?? t.common.unexpected,
                            e.fields ?? {}, e.retry_after_seconds, e);
    if (res.status === 403 && err.code === "reauth_required" && !retried && !signal?.aborted) {
      if (await askReauth()) return generate(path, signal, true);
    }
    throw err;
  }
  return data as GenerateResult;
}

export type { SourceKind };
