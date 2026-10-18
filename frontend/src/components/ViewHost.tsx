import {
  createContext,
  useCallback,
  useContext,
  useId,
  useLayoutEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactElement,
  type ReactNode,
} from "react";

/** A mounted, portal-ready view slot in the document. */
interface HostEntry {
  key: string;
  depth: number;
  slot: HTMLElement;
}

/** An open view and the host it currently renders into. */
interface ViewEntry {
  id: string;
  hostKey: string;
  historyToken?: string;
}

interface ViewStoreState {
  hosts: HostEntry[];
  views: ViewEntry[];
}

const initialState: ViewStoreState = { hosts: [], views: [] };

let storeState: ViewStoreState = initialState;
const storeListeners = new Set<() => void>();

function emitStoreChange() {
  for (const listener of storeListeners) {
    listener();
  }
}

function setStoreState(updater: (state: ViewStoreState) => ViewStoreState) {
  storeState = updater(storeState);
  emitStoreChange();
}

function subscribe(listener: () => void): () => void {
  storeListeners.add(listener);
  return () => {
    storeListeners.delete(listener);
  };
}

function getSnapshot(): ViewStoreState {
  return storeState;
}

/** Register a mounted host's view slot. */
function registerHost(host: HostEntry): void {
  setStoreState((state) => {
    const hosts = [...state.hosts.filter((h) => h.key !== host.key), host];
    return { ...state, hosts };
  });
}

/** Unregister a mounted host's view slot. */
function unregisterHost(key: string): void {
  setStoreState((state) => ({
    ...state,
    hosts: state.hosts.filter((h) => h.key !== key),
  }));
}

/**
 * Register an open view. If the view already exists, its host is updated
 * without changing its position in the opening order, and an existing
 * history token is preserved unless a new one is supplied.
 */
export function registerView(
  id: string,
  hostKey: string,
  historyToken?: string,
): void {
  setStoreState((state) => {
    const existing = state.views.some((v) => v.id === id);
    const views = existing
      ? state.views.map((v) =>
          v.id === id
            ? {
                ...v,
                hostKey,
                historyToken: historyToken ?? v.historyToken,
              }
            : v,
        )
      : [...state.views, { id, hostKey, historyToken }];
    return { ...state, views };
  });
}

/** Unregister an open view. */
export function unregisterView(id: string): void {
  setStoreState((state) => ({
    ...state,
    views: state.views.filter((v) => v.id !== id),
  }));
}

/**
 * Update the history token for an open view, if it exists.
 */
export function setViewHistoryToken(
  id: string,
  token: string | null,
): void {
  setStoreState((state) => ({
    ...state,
    views: state.views.map((v) =>
      v.id === id ? { ...v, historyToken: token ?? undefined } : v,
    ),
  }));
}

/**
 * Get the history tokens of all currently registered open views, in opening
 * order, excluding views without a token.
 */
export function getOpenHistoryTokens(): string[] {
  return storeState.views.flatMap((v) =>
    v.historyToken ? [v.historyToken] : [],
  );
}

/** The innermost mounted host, if any. */
function selectTopHost(state: ViewStoreState): HostEntry | null {
  if (state.hosts.length === 0) return null;

  let top = state.hosts[0];
  for (let i = 1; i < state.hosts.length; i += 1) {
    const host = state.hosts[i];
    if (
      host.depth > top.depth ||
      (host.depth === top.depth &&
        state.hosts.indexOf(host) > state.hosts.indexOf(top))
    ) {
      top = host;
    }
  }
  return top;
}

/** The most recently opened view id, if any. */
function selectTopViewId(state: ViewStoreState): string | null {
  if (state.views.length === 0) return null;
  return state.views[state.views.length - 1].id;
}

/**
 * Subscribe to the innermost mounted view host.
 *
 * Returns a stable object while the top host does not change.
 */
export function useTopHost(): { key: string; slot: HTMLElement } | null {
  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const topHost = selectTopHost(state);
  return useMemo(() => {
    if (!topHost) return null;
    return { key: topHost.key, slot: topHost.slot };
  }, [topHost?.key, topHost?.slot]);
}

/** Subscribe to the most recently opened view id. */
export function useTopViewId(): string | null {
  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  return useMemo(() => selectTopViewId(state), [state]);
}

interface ViewHostContextValue {
  depth: number;
}

const ViewHostContext = createContext<ViewHostContextValue>({ depth: 0 });

/**
 * Defines a portal target for full-page `View` components.
 *
 * The surrounding content stays mounted while a view is open so its state is
 * preserved. Hosts can be nested; views render into the innermost host.
 */
export function ViewHost({ children }: { children: ReactNode }): ReactElement {
  const key = useId();
  const parentDepth = useContext(ViewHostContext).depth;
  const depth = parentDepth + 1;
  const [slot, setSlot] = useState<HTMLElement | null>(null);

  const slotRef = useCallback((element: HTMLDivElement | null) => {
    setSlot(element);
  }, []);

  useLayoutEffect(() => {
    if (!slot) return;
    registerHost({ key, depth, slot });
    return () => {
      unregisterHost(key);
    };
  }, [key, depth, slot]);

  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const viewOpen = state.views.some((v) => v.hostKey === key);

  const contextValue = useMemo<ViewHostContextValue>(
    () => ({ depth }),
    [depth],
  );

  return (
    <ViewHostContext.Provider value={contextValue}>
      <div hidden={viewOpen}>{children}</div>
      <div ref={slotRef} />
    </ViewHostContext.Provider>
  );
}
