/** Mailing lists (feature 058): `/api/mail/lists`. Every call is authenticated. */
import { api, qs } from "./client";
import type {
  MailImportResult,
  MailList,
  MailListInput,
  MailListPatch,
  MailListsPage,
  MailMemberInput,
} from "./types";

const BASE = "/api/mail/lists";

export type MailListScope = "mine" | "shared" | "all";

export const mail = {
  /** `mine` is only yours, `shared` only the shared ones, `all` what you may use. */
  listLists: (scope: MailListScope = "all", q?: string) =>
    api.get<MailListsPage>(`${BASE}${qs({ scope, q })}`),

  getList: (id: number) => api.get<MailList>(`${BASE}/${id}`),

  createList: (body: MailListInput) => api.post<MailList>(BASE, { ...body }),

  updateList: (id: number, body: MailListPatch) =>
    api.patch<MailList>(`${BASE}/${id}`, { ...body }),

  deleteList: (id: number) => api.del<void>(`${BASE}/${id}`),

  /** The whole member list at once: the rows the editor keeps plus the text it pasted. */
  putMembers: (id: number, body: { members?: MailMemberInput[]; text?: string | null }) =>
    api.put<MailList>(`${BASE}/${id}/members`, { ...body }),

  importCsv: (id: number, text: string) =>
    api.post<MailImportResult>(`${BASE}/${id}/members/import`, { text }),

  /** The CSV is an attachment, so the browser downloads it with a plain link. */
  exportCsvUrl: (id: number) => `${BASE}/${id}/export`,

  pauseMember: (id: number, memberId: number, paused: boolean) =>
    api.post<MailList>(`${BASE}/${id}/members/${memberId}/pause`, { paused }),
};
