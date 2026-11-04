/** Feature 052: the structure of a source, its sample requests and the structure chat. */
import { api, qs } from "./client";
import type {
  ChatAnswer,
  ChatHistory,
  SampleRequest,
  SampleRun,
  SourceKind,
  StructurePack,
} from "./types";

const base = (name: string) => `/api/sources/${encodeURIComponent(name)}`;

export const sourcesApi = {
  structure: (name: string, path?: string | null) =>
    api.get<StructurePack>(`${base(name)}/structure${qs({ path })}`),
  /** The download the browser saves; the API answers an attachment. */
  downloadUrl: (name: string, format: "md" | "json") =>
    `${base(name)}/structure${qs({ format })}`,
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
  runSample: (name: string, id: number) =>
    api.post<SampleRun>(`${base(name)}/samples/${id}/run`),
  chat: (name: string) => api.get<ChatHistory>(`${base(name)}/chat`),
  ask: (name: string, question: string) =>
    api.post<ChatAnswer>(`${base(name)}/chat`, { question }),
  clearChat: (name: string) => api.del(`${base(name)}/chat`),
};

export type { SourceKind };
