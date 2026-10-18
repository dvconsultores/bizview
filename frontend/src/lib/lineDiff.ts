import type { DiffHunk, DiffLine } from "../api/types";

const MAX_CELLS = 4_000_000;   // a×b LCS table cap; beyond it every line counts as changed

/** Line diff of two texts as hunks with `context` lines around changes (same shape as the
 * server's `history.diff`), used for unsaved buffers that are not a revision yet. */
export function lineDiff(a: string, b: string, context = 3): DiffHunk[] {
  const x = a.split("\n");
  const y = b.split("\n");
  if (x[x.length - 1] === "") x.pop();
  if (y[y.length - 1] === "") y.pop();
  const ops: { t: DiffLine["t"]; text: string; ai: number; bi: number }[] = [];
  if (x.length * y.length <= MAX_CELLS) {
    const lcs: Uint32Array[] = Array.from({ length: x.length + 1 }, () => new Uint32Array(y.length + 1));
    for (let i = x.length - 1; i >= 0; i--) {
      for (let j = y.length - 1; j >= 0; j--) {
        lcs[i][j] = x[i] === y[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
      }
    }
    let i = 0;
    let j = 0;
    while (i < x.length || j < y.length) {
      if (i < x.length && j < y.length && x[i] === y[j]) ops.push({ t: " ", text: x[i++], ai: i, bi: ++j });
      else if (j < y.length && (i === x.length || lcs[i][j + 1] > lcs[i + 1][j])) ops.push({ t: "+", text: y[j++], ai: i + 1, bi: j });
      else ops.push({ t: "-", text: x[i++], ai: i, bi: j + 1 });
    }
  } else {
    x.forEach((text, i) => ops.push({ t: "-", text, ai: i + 1, bi: 1 }));
    y.forEach((text, j) => ops.push({ t: "+", text, ai: x.length + 1, bi: j + 1 }));
  }
  const hunks: DiffHunk[] = [];
  let current: DiffHunk | null = null;
  let lastChange = -Infinity;
  ops.forEach((op, k) => {
    if (op.t !== " ") {
      if (!current || k - lastChange > 2 * context) {
        const start = Math.max(0, k - context);
        const first = ops[start];
        current = { a_start: first.ai, b_start: first.bi, lines: [] };
        hunks.push(current);
        for (let c = start; c < k; c++) current.lines.push({ t: " ", text: ops[c].text });
      } else {
        for (let c = lastChange + 1; c < k; c++) current.lines.push({ t: ops[c].t, text: ops[c].text });
      }
      current.lines.push({ t: op.t, text: op.text });
      lastChange = k;
    }
  });
  if (current) {
    for (let c = lastChange + 1; c < Math.min(ops.length, lastChange + 1 + context); c++) {
      (current as DiffHunk).lines.push({ t: " ", text: ops[c].text });
    }
  }
  return hunks;
}
