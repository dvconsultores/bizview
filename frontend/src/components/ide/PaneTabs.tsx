import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Group, Panel, Separator, type Layout } from "react-resizable-panels";
import { useT } from "../../i18n";

export type PaneId = "files" | "editor";

const PANES: PaneId[] = ["files", "editor"];
const DEFAULT_LAYOUT: Layout = { files: 30, editor: 70 };
const MIN_SIZE: Record<PaneId, string> = { files: "12%", editor: "25%" };
const WIDE = "(min-width: 1024px)";

function readLayout(key: string, panes: PaneId[]): Layout {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) ?? "null");
    if (parsed && panes.every((p) => typeof parsed[p] === "number" && parsed[p] > 0)) {
      return parsed as Layout;
    }
  } catch {
    /* storage unavailable or corrupt: defaults */
  }
  return DEFAULT_LAYOUT;
}

/** True from 1024 px, where the IDE shows its panes side by side. */
export function useWideLayout(): boolean {
  return useWide();
}

function useWide(): boolean {
  const [wide, setWide] = useState(
    () => typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(WIDE).matches,
  );
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(WIDE);
    const update = () => setWide(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, []);
  return wide;
}

/** Phones and tablets: one pane at a time behind tabs. From 1024 px: two resizable panes
 * (keyboard-resizable separators; sizes remembered per browser). */
export function PaneTabs(props: {
  files: ReactNode;
  editor: ReactNode;
  active: PaneId;
  onActive: (p: PaneId) => void;
  storageKey?: string;
}) {
  const t = useT();
  const { active, onActive, storageKey = "bizview.ide.panes" } = props;
  const wide = useWide();
  const panes = PANES;
  const tabs = useRef<Record<PaneId, HTMLButtonElement | null>>({ files: null, editor: null });
  const labels: Record<PaneId, string> = { files: t.projects.files, editor: t.projects.editor };
  const content: Record<PaneId, ReactNode> = { files: props.files, editor: props.editor };
  const shown: PaneId = panes.includes(active) ? active : "files";

  const onKey = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1 + panes.length, Home: 0,
                   End: panes.length - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    const pane = panes[next % panes.length];
    onActive(pane);
    tabs.current[pane]?.focus();
  };

  if (!wide) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div role="tablist" aria-label={t.projects.panes} className="flex border-b border-line bg-subtle">
          {panes.map((pane, index) => (
            <button
              key={pane}
              ref={(el) => { tabs.current[pane] = el; }}
              type="button"
              role="tab"
              id={`pane-tab-${pane}`}
              aria-selected={shown === pane}
              aria-controls={`pane-panel-${pane}`}
              tabIndex={shown === pane ? 0 : -1}
              onClick={() => onActive(pane)}
              onKeyDown={(e) => onKey(e, index)}
              className={`min-h-tap flex-1 border-b-2 px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                shown === pane ? "border-accent text-accent-strong" : "border-transparent text-ink-muted"
              }`}
            >
              {labels[pane]}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`pane-panel-${shown}`} aria-labelledby={`pane-tab-${shown}`}
             className="min-h-0 flex-1 overflow-auto">
          {content[shown]}
        </div>
      </div>
    );
  }

  const save = (layout: Layout) => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(layout));
    } catch {
      /* storage unavailable: sizes are not remembered */
    }
  };
  const layout = readLayout(storageKey, panes);
  return (
    <Group orientation="horizontal" defaultLayout={layout} onLayoutChanged={save} className="h-full">
      {panes.map((pane, index) => (
        <PaneSlot key={pane} pane={pane} first={index === 0} size={layout[pane]}
                  label={t.projects.resizePanes}>
          {content[pane]}
        </PaneSlot>
      ))}
    </Group>
  );
}

function PaneSlot(props: { pane: PaneId; first: boolean; size: number; label: string;
                           children: ReactNode }) {
  return (
    <>
      {!props.first && (
        <Separator aria-label={props.label}
                   className="w-1.5 bg-line hover:bg-line-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" />
      )}
      <Panel id={props.pane} defaultSize={`${props.size}%`} minSize={MIN_SIZE[props.pane]}>
        <div className="h-full min-h-0 overflow-auto">{props.children}</div>
      </Panel>
    </>
  );
}
