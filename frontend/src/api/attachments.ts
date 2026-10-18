/** Feature 024: image briefs of the chat. The bytes travel as the raw request body (the
 *  server decides the type from the magic bytes), so this needs its own fetch, like the zip
 *  import of feature 020. */
import { ApiError, api, askReauth, qs } from "./client";
import type { Attachment } from "./types";
import { currentLocale, t } from "../i18n/live";

export async function uploadAttachment(sessionId: number, file: File): Promise<Attachment> {
  const send = () =>
    fetch(`/api/assistant/sessions/${sessionId}/attachments${qs({ name: file.name })}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-Requested-With": "fetch",
        Accept: "application/json",
        "Accept-Language": currentLocale(),
      },
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
  return data as Attachment;
}

export function deleteAttachment(id: number): Promise<void> {
  return api.del<void>(`/api/assistant/attachments/${id}`);
}

/** The first image send needs the "images go to the provider" notice accepted (FR-006). */
export function acceptAttachmentsNotice(): Promise<void> {
  return api.post<void>("/api/me/attachments-notice");
}
