/**
 * Feature 049: reading a zip's table of contents in the browser.
 *
 * The reader is what makes the pre-flight possible: it lists names and declared sizes from the
 * central directory, without decompressing anything and without a library.
 */
import { describe, expect, it } from "vitest";
import { readZipIndex } from "../../src/lib/zipIndex";

/** Build a real (stored) zip in memory: local headers, central directory, EOCD. */
function buildZip(files: { name: string; content?: Uint8Array }[], comment = ""): Blob {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;

  const u16 = (n: number) => [n & 0xff, (n >> 8) & 0xff];
  const u32 = (n: number) => [n & 0xff, (n >> 8) & 0xff, (n >> 16) & 0xff, (n >> 24) & 0xff];

  for (const file of files) {
    const name = encoder.encode(file.name);
    const data = file.content ?? new Uint8Array([1, 2, 3, 4]);
    const crc = 0;                                   // the reader never looks at it
    const local = new Uint8Array([
      0x50, 0x4b, 0x03, 0x04, ...u16(20), ...u16(0), ...u16(0), ...u16(0), ...u16(0),
      ...u32(crc), ...u32(data.length), ...u32(data.length), ...u16(name.length), ...u16(0),
      ...name, ...data,
    ]);
    chunks.push(local);
    central.push(new Uint8Array([
      0x50, 0x4b, 0x01, 0x02, ...u16(20), ...u16(20), ...u16(0), ...u16(0), ...u16(0),
      ...u16(0), ...u32(crc), ...u32(data.length), ...u32(data.length),
      ...u16(name.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0),
      ...u32(offset), ...name,
    ]));
    offset += local.length;
  }

  const directory = new Uint8Array(central.reduce((n, c) => n + c.length, 0));
  let at = 0;
  for (const entry of central) { directory.set(entry, at); at += entry.length; }

  const tail = encoder.encode(comment);
  const eocd = new Uint8Array([
    0x50, 0x4b, 0x05, 0x06, ...u16(0), ...u16(0), ...u16(files.length), ...u16(files.length),
    ...u32(directory.length), ...u32(offset), ...u16(tail.length), ...tail,
  ]);
  return new Blob([...chunks, directory, eocd]);
}

describe("readZipIndex", () => {
  it("lists names and declared sizes, and drops directories", async () => {
    const zip = buildZip([
      { name: "ventas/", content: new Uint8Array() },
      { name: "ventas/project.yaml", content: new Uint8Array(120) },
      { name: "ventas/assets/coins/BTC.png", content: new Uint8Array(3800) },
    ]);
    const entries = await readZipIndex(zip);
    expect(entries).toEqual([
      { name: "ventas/project.yaml", size: 120 },
      { name: "ventas/assets/coins/BTC.png", size: 3800 },
    ]);
  });

  it("reads a zip whose end record is followed by a comment", async () => {
    const zip = buildZip([{ name: "project.yaml", content: new Uint8Array(50) }],
                         "x".repeat(1000));
    expect(await readZipIndex(zip)).toEqual([{ name: "project.yaml", size: 50 }]);
  });

  it("handles the 483-image archive from the report", async () => {
    const files = Array.from({ length: 483 }, (_, i) => ({
      name: `ventas/assets/coins/C${i}.png`, content: new Uint8Array(3800),
    }));
    const entries = await readZipIndex(buildZip(files));
    expect(entries).toHaveLength(483);
    expect(entries![0].size).toBe(3800);
  });

  it("returns an empty list for a zip with no files", async () => {
    expect(await readZipIndex(buildZip([]))).toEqual([]);
  });

  it("returns null for something that is not a zip, so the upload is not blocked", async () => {
    expect(await readZipIndex(new Blob(["not a zip at all"]))).toBeNull();
    expect(await readZipIndex(new Blob([]))).toBeNull();
  });

  it("returns null for a truncated archive", async () => {
    const zip = buildZip([{ name: "project.yaml", content: new Uint8Array(50) }]);
    const bytes = new Uint8Array(await zip.arrayBuffer()).slice(0, 40);
    expect(await readZipIndex(new Blob([bytes]))).toBeNull();
  });
});
