/**
 * Feature 049: what a zip would cost, before it is uploaded.
 *
 * The server owns the answer (`backend/app/projects/budgets.py`). This is the same measurement
 * done early, on the archive's declared sizes, so the import screen can disable a button and name
 * the allowance that is over instead of sending a file that will be refused. The classification
 * (`assets/` is one allowance, everything else the other) mirrors `layout.budget_of`.
 */
import type { ImportBudget, ImportLimits } from "../api/types";

export const ASSET_PREFIX = "assets/";

export type BudgetName = "artifacts" | "assets";

export interface Tally {
  files: number;
  bytes: number;
  over: ("files" | "bytes")[];
}

export interface Preflight {
  artifacts: Tally;
  assets: Tally;
  ignored: string[];
  /** The allowance to blame, when one is over. Artifacts first: that is what a project *is*. */
  over: BudgetName | null;
}

function tallyFor(entries: { name: string; size: number }[], budget: ImportBudget): Tally {
  const files = entries.length;
  const bytes = entries.reduce((total, entry) => total + entry.size, 0);
  const over: ("files" | "bytes")[] = [];
  if (files > budget.max_files) over.push("files");
  if (bytes > budget.max_mb * 1024 * 1024) over.push("bytes");
  return { files, bytes, over };
}

/**
 * Tally a zip's entries against the installation's limits.
 *
 * `top` is the shared top folder the importer strips (`ventas/`), so the classification sees the
 * same paths the server will.
 */
export function tallyIndex(
  entries: { name: string; size: number }[],
  limits: ImportLimits,
): Preflight {
  const stripped = stripTopFolder(entries.map((entry) => entry.name));
  const prefix = stripped.prefix;
  const relative = entries.map((entry) => ({
    name: entry.name.startsWith(prefix) ? entry.name.slice(prefix.length) : entry.name,
    size: entry.size,
  }));
  // Everything the layout does not own ends up as ignored on the server; here it is enough to keep
  // it out of both tallies.
  const artifacts = relative.filter((e) => isArtifact(e.name));
  const assets = relative.filter((e) => e.name.startsWith(ASSET_PREFIX) && isAsset(e.name));
  const ignored = relative
    .filter((e) => !isArtifact(e.name) && !(e.name.startsWith(ASSET_PREFIX) && isAsset(e.name)))
    .map((e) => e.name)
    .sort();
  const result: Preflight = {
    artifacts: tallyFor(artifacts, limits.artifacts),
    assets: tallyFor(assets, limits.assets),
    ignored,
    over: null,
  };
  if (result.artifacts.over.length) result.over = "artifacts";
  else if (result.assets.over.length) result.over = "assets";
  return result;
}

/** The importer's rule: one folder shared by every entry, and not a layout folder itself. */
function stripTopFolder(names: string[]): { prefix: string } {
  const tops = new Set(names.map((name) => name.split("/")[0]));
  const everyEntryIsNested = names.every((name) => name.includes("/"));
  if (tops.size !== 1 || !everyEntryIsNested) return { prefix: "" };
  const top = [...tops][0];
  const layoutTops = new Set(["specs", "integrations", "reports", "distributions", "themes",
                              "assets", ".specify", "project.yaml"]);
  return { prefix: layoutTops.has(top) ? "" : `${top}/` };
}

const ARTIFACT_PATTERNS: RegExp[] = [
  /^project\.yaml$/,
  /^\.specify\/memory\/constitution\.md$/,
  /^specs\/[0-9]{3}-[a-z0-9][a-z0-9-]*\/(spec|plan|tasks|research|data-model|quickstart|run-report)\.md$/,
  /^specs\/[0-9]{3}-[a-z0-9][a-z0-9-]*\/checklists\/[a-z0-9][a-z0-9._-]*\.md$/,
  /^integrations\/[a-z][a-z0-9-]*\/integration\.yaml$/,
  /^integrations\/[a-z][a-z0-9-]*\/queries\/[a-z0-9][a-z0-9._-]*\.sql$/,
  /^integrations\/[a-z][a-z0-9-]*\/requests\/[a-z0-9][a-z0-9._-]*\.yaml$/,
  /^reports\/[a-z][a-z0-9-]*\/report\.yaml$/,
  /^distributions\/[a-z][a-z0-9-]*\.yaml$/,
  /^themes\/[a-z][a-z0-9-]*\.(yaml|yml)$/,
];

const ASSET_PATTERN =
  /^assets\/(?:[a-z0-9][a-z0-9._-]*\/)?[A-Za-z0-9][A-Za-z0-9._-]*\.(png|jpg|jpeg|webp|svg)$/i;

function isArtifact(name: string): boolean {
  return ARTIFACT_PATTERNS.some((pattern) => pattern.test(name));
}

function isAsset(name: string): boolean {
  return ASSET_PATTERN.test(name);
}

/** A one-line, human reading of one tally: "483 archivos, 1,8 MB". */
export function describeTally(tally: Tally, budget: ImportBudget): string {
  return `${tally.files}/${budget.max_files} · ${formatSize(tally.bytes)}/${budget.max_mb} MB`;
}

export function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
