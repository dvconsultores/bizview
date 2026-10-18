import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Braces, Database, File, FileCode2, FilePlus, FileText, Folder, FolderOpen, FolderPlus,
         Pencil, Trash2 } from "lucide-react";
import type { ProjectTree } from "../../api/types";
import { useT } from "../../i18n";
import { Badge } from "../Badge";
import { Button } from "../Button";

interface Node { path: string; name: string; folder: boolean; children: Node[] }

const SPEC_FOLDER = /^specs\/\d{3}-[^/]+$/;

function build(tree: ProjectTree): Node[] {
  const roots: Node[] = [];
  const folders = new Map<string, Node>();
  const parentOf = (path: string): Node[] => {
    const cut = path.lastIndexOf("/");
    return cut < 0 ? roots : folder(path.slice(0, cut)).children;
  };
  const folder = (path: string): Node => {
    let node = folders.get(path);
    if (!node) {
      node = { path, name: path.slice(path.lastIndexOf("/") + 1), folder: true, children: [] };
      folders.set(path, node);
      parentOf(path).push(node);
    }
    return node;
  };
  tree.folders.forEach(folder);
  for (const f of tree.files) {
    parentOf(f.path).push({ path: f.path, name: f.path.slice(f.path.lastIndexOf("/") + 1),
                            folder: false, children: [] });
  }
  const sort = (nodes: Node[]) => {
    nodes.sort((a, b) => (a.folder === b.folder ? a.name.localeCompare(b.name) : a.folder ? -1 : 1));
    nodes.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

function icon(node: Node, open: boolean) {
  if (node.folder) return open ? FolderOpen : Folder;
  if (node.name.endsWith(".md")) return FileText;
  if (/\.ya?ml$/.test(node.name)) return FileCode2;
  if (node.name.endsWith(".sql")) return Database;
  if (node.name.endsWith(".json")) return Braces;
  return File;
}

function ancestors(path: string | null): string[] {
  if (!path) return [];
  const parts = path.split("/");
  return parts.slice(0, -1).map((_, i) => parts.slice(0, i + 1).join("/"));
}

const parentFolder = (path: string) => (path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");

type Edit = { mode: "file" | "folder" | "rename"; from?: string; folder?: boolean; value: string };

/** Project files as a WAI-ARIA tree; inline rows for new / rename / delete (no dialogs). */
export function Explorer(props: {
  tree: ProjectTree;
  activePath: string | null;
  readOnly: boolean;
  onOpen: (path: string) => void;
  onCreate: (path: string, folder: boolean) => Promise<string | null>;
  onRename: (from: string, to: string) => Promise<string | null>;
  onDelete: (path: string, folder: boolean) => Promise<string | null>;
}) {
  const t = useT();
  const roots = useMemo(() => build(props.tree), [props.tree]);
  const [open, setOpen] = useState<Set<string>>(() => new Set(["specs", ...ancestors(props.activePath)]));
  const [focused, setFocused] = useState<string | null>(props.activePath);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [deleting, setDeleting] = useState<{ path: string; folder: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const refs = useRef(new Map<string, HTMLButtonElement>());

  const visible = useMemo(() => {
    const out: { node: Node; depth: number }[] = [];
    const walk = (nodes: Node[], depth: number) => nodes.forEach((node) => {
      out.push({ node, depth });
      if (node.folder && open.has(node.path)) walk(node.children, depth + 1);
    });
    walk(roots, 1);
    return out;
  }, [roots, open]);
  const tabStop = visible.some((v) => v.node.path === focused) ? focused : visible[0]?.node.path;

  const toggle = (path: string, value?: boolean) => setOpen((prev) => {
    const next = new Set(prev);
    if (value ?? !next.has(path)) next.add(path); else next.delete(path);
    return next;
  });
  const focus = (path: string | undefined) => {
    if (!path) return;
    setFocused(path);
    refs.current.get(path)?.focus();
  };

  const startRename = (node: Node) => {
    setDeleting(null); setError(null);
    setEdit({ mode: "rename", from: node.path, folder: node.folder, value: node.path });
  };
  const startDelete = (node: Node) => {
    setEdit(null); setError(null); setDeleting({ path: node.path, folder: node.folder });
  };

  const onKey = (e: KeyboardEvent<HTMLButtonElement>, node: Node) => {
    const i = visible.findIndex((v) => v.node.path === node.path);
    const go = (j: number) => focus(visible[Math.max(0, Math.min(visible.length - 1, j))]?.node.path);
    switch (e.key) {
      case "ArrowDown": go(i + 1); break;
      case "ArrowUp": go(i - 1); break;
      case "Home": go(0); break;
      case "End": go(visible.length - 1); break;
      case "ArrowRight":
        if (node.folder && !open.has(node.path)) toggle(node.path, true);
        else if (node.folder && node.children.length) go(i + 1);
        break;
      case "ArrowLeft":
        if (node.folder && open.has(node.path)) toggle(node.path, false);
        else focus(parentFolder(node.path) || undefined);
        break;
      case "Enter":
      case " ":
        if (node.folder) toggle(node.path); else props.onOpen(node.path);
        break;
      case "F2":
        if (props.readOnly) return;
        startRename(node);
        break;
      case "Delete":
        if (props.readOnly) return;
        startDelete(node);
        break;
      default:
        return;
    }
    e.preventDefault();
  };

  const run = async (action: () => Promise<string | null>) => {
    setBusy(true);
    setError(null);
    const message = await action();
    setBusy(false);
    if (message) setError(message);
    else {
      setEdit(null);
      setDeleting(null);
    }
  };
  const submit = () => {
    if (!edit) return;
    const value = edit.value.trim().replace(/^\/+/, "").replace(/\/+$/, "");
    if (!value) return;
    if (edit.mode === "rename" && edit.from) {
      if (value === edit.from) { setEdit(null); return; }
      void run(() => props.onRename(edit.from as string, value));
    } else {
      void run(() => props.onCreate(value, edit.mode === "folder"));
    }
  };
  const startCreate = (mode: "file" | "folder") => {
    const base = focused ? (visible.find((v) => v.node.path === focused)?.node.folder
                            ? focused : parentFolder(focused)) : "";
    setDeleting(null);
    setError(null);
    setEdit({ mode, value: base ? `${base}/` : "" });
  };

  return (
    <div className="flex flex-col gap-1 p-2 text-sm">
      {!props.readOnly && (
        <div className="flex flex-wrap gap-1">
          <Button variant="ghost" icon={<FilePlus className="h-4 w-4" aria-hidden />} onClick={() => startCreate("file")}>
            {t.projects.newFile}
          </Button>
          <Button variant="ghost" icon={<FolderPlus className="h-4 w-4" aria-hidden />} onClick={() => startCreate("folder")}>
            {t.projects.newFolder}
          </Button>
        </div>
      )}
      {edit && (
        <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <input
            autoFocus
            aria-label={t.projects.pathLabel}
            value={edit.value}
            onChange={(e) => setEdit({ ...edit, value: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); setEdit(null); setError(null); } }}
            className="min-h-tap w-full rounded-card border border-line bg-surface px-3 font-mono text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          />
          <Button type="submit" loading={busy}>{t.projects.save}</Button>
          <Button variant="ghost" onClick={() => { setEdit(null); setError(null); }}>{t.projects.cancel}</Button>
        </form>
      )}
      {deleting && (
        <div className="flex flex-wrap items-center gap-2 rounded-card border border-danger-line bg-danger-soft p-2">
          <span className="min-w-0 flex-1 break-all text-ink">{t.projects.removeConfirm(deleting.path)}</span>
          <Button variant="danger" loading={busy}
                  onClick={() => void run(() => props.onDelete(deleting.path, deleting.folder))}>
            {t.projects.confirm}
          </Button>
          <Button variant="secondary" onClick={() => { setDeleting(null); setError(null); }}>{t.projects.cancel}</Button>
        </div>
      )}
      {error && <p role="alert" className="whitespace-pre-line break-words text-sm text-danger">{error}</p>}
      <ul role="tree" aria-label={t.projects.explorer} className="flex flex-col">
        {visible.map(({ node, depth }) => {
          const isOpen = node.folder && open.has(node.path);
          const Icon = icon(node, isOpen);
          const spec = node.folder && SPEC_FOLDER.test(node.path) ? props.tree.specs[node.path] : undefined;
          return (
            <li key={node.path} role="none" className="group flex items-center">
              <button
                ref={(el) => { if (el) refs.current.set(node.path, el); else refs.current.delete(node.path); }}
                type="button"
                role="treeitem"
                aria-level={depth}
                aria-expanded={node.folder ? isOpen : undefined}
                aria-selected={node.path === props.activePath}
                aria-keyshortcuts={props.readOnly ? undefined : "F2 Delete"}
                tabIndex={node.path === tabStop ? 0 : -1}
                onFocus={() => setFocused(node.path)}
                onKeyDown={(e) => onKey(e, node)}
                onClick={() => { setFocused(node.path); if (node.folder) toggle(node.path); else props.onOpen(node.path); }}
                style={{ paddingLeft: `${(depth - 1) * 14 + 6}px` }}
                className={`flex min-h-[2rem] min-w-0 flex-1 flex-wrap items-center gap-1.5 rounded py-1 pr-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                  node.path === props.activePath ? "bg-accent-soft text-accent-strong" : "text-ink hover:bg-subtle"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
                <span className="min-w-0 truncate">{node.name}</span>
                {spec?.kind && <Badge tone="blue">{t.projects.kind[spec.kind] ?? spec.kind}</Badge>}
                {spec?.stage && <Badge tone="gray">{t.projects.stage[spec.stage] ?? spec.stage}</Badge>}
                {spec?.converged && <Badge tone="amber">{t.projects.converged}</Badge>}
                {node.folder && isOpen && node.children.length === 0 && (
                  <span className="text-xs text-ink-soft">{t.projects.emptyFolder}</span>
                )}
              </button>
              {!props.readOnly && (
                // Pointer shortcuts only: keyboard users press F2 / Delete on the item (the tree may
                // own only treeitems).
                <span aria-hidden="true" className="flex shrink-0 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100">
                  <button type="button" aria-label={`${t.projects.rename} ${node.path}`} tabIndex={-1}
                          onClick={() => startRename(node)}
                          className="rounded p-1 text-ink-muted hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                    <Pencil className="h-3.5 w-3.5" aria-hidden />
                  </button>
                  <button type="button" aria-label={`${t.projects.remove} ${node.path}`} tabIndex={-1}
                          onClick={() => startDelete(node)}
                          className="rounded p-1 text-ink-muted hover:bg-subtle hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
