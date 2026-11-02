/**
 * Feature 049: read a zip's table of contents in the browser, before uploading anything.
 *
 * A zip stores the name and the uncompressed size of every entry in its **central directory** — a
 * table at the end of the file. Reading that table costs one read of the last ~64 KB plus the
 * directory itself: no decompression, no library, no upload. That is what lets the import screen
 * tell an author "2 150 images, over the 2 000 limit" instead of sending 26 MB to be told so.
 *
 * The declared size is what we report. The server re-measures the real bytes, so a lying index buys
 * an author nothing — the pre-flight advises, the server decides.
 */

/** Where the End Of Central Directory record lives, and how far back it can be: 22 bytes of
 *  record plus a comment of at most 65 535. */
const EOCD_SIGNATURE = 0x06054b50;
const EOCD_MIN_BYTES = 22;
const MAX_COMMENT = 0xffff;

const CENTRAL_SIGNATURE = 0x02014b50;
const CENTRAL_MIN_BYTES = 46;

export interface ZipEntry {
  name: string;
  size: number;
}

async function readAt(file: Blob, start: number, length: number): Promise<DataView> {
  const end = Math.min(file.size, start + length);
  const buffer = await file.slice(Math.max(0, start), end).arrayBuffer();
  return new DataView(buffer);
}

/** The offset of the central directory, or null when this is not a zip we can read. */
async function centralDirectory(file: Blob): Promise<{ offset: number; count: number } | null> {
  const tailLength = Math.min(file.size, EOCD_MIN_BYTES + MAX_COMMENT);
  const tail = await readAt(file, file.size - tailLength, tailLength);
  // Scan backwards: the record may be followed by a comment of any length.
  for (let i = tail.byteLength - EOCD_MIN_BYTES; i >= 0; i -= 1) {
    if (tail.getUint32(i, true) !== EOCD_SIGNATURE) continue;
    const count = tail.getUint16(i + 10, true);
    const offset = tail.getUint32(i + 16, true);
    // 0xFFFFFFFF means Zip64: the real values live in another record we deliberately do not read,
    // and an archive that large is refused by the server anyway.
    if (count === 0xffff || offset === 0xffffffff) return null;
    return { offset, count };
  }
  return null;
}

/**
 * The entries of a zip: name and declared size, directories excluded.
 *
 * Returns `null` when the file cannot be read as a zip (Zip64, truncated, not a zip at all) — the
 * caller then skips the pre-flight and lets the server answer, rather than blocking a good upload.
 */
export async function readZipIndex(file: Blob): Promise<ZipEntry[] | null> {
  if (file.size < EOCD_MIN_BYTES) return null;
  let directory: { offset: number; count: number } | null;
  try {
    directory = await centralDirectory(file);
  } catch {
    return null;
  }
  if (!directory) return null;
  if (directory.count === 0) return [];        // an empty archive has no directory to walk
  if (directory.offset + CENTRAL_MIN_BYTES > file.size) return null;

  const view = await readAt(file, directory.offset, file.size - directory.offset);
  const decoder = new TextDecoder("utf-8");
  const entries: ZipEntry[] = [];
  let cursor = 0;
  for (let n = 0; n < directory.count; n += 1) {
    if (cursor + CENTRAL_MIN_BYTES > view.byteLength) return null;
    if (view.getUint32(cursor, true) !== CENTRAL_SIGNATURE) return null;
    const nameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const size = view.getUint32(cursor + 24, true);
    const nameStart = cursor + CENTRAL_MIN_BYTES;
    const nameEnd = nameStart + nameLength;
    if (nameEnd > view.byteLength) return null;
    const name = decoder.decode(new Uint8Array(view.buffer, view.byteOffset + nameStart, nameLength));
    cursor = nameEnd + extraLength + commentLength;
    if (name.endsWith("/")) continue;          // a directory is not a file
    entries.push({ name, size });
  }
  return entries;
}
