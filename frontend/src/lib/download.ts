/** POST fetch that downloads a blob and triggers a browser download. */
export async function downloadPdf(url: string, filename: string, defaultMessage: string): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-Requested-With": "fetch" },
  });
  if (!res.ok) {
    let message = defaultMessage;
    try {
      message = (await res.json()).error?.message ?? defaultMessage;
    } catch {
      /* not JSON */
    }
    throw new Error(message);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
