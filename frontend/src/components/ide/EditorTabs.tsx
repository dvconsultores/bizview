import { X } from "lucide-react";
import { useT } from "../../i18n";
import { Button } from "../Button";

export interface OpenTab { path: string; dirty: boolean }

export const MAX_TABS = 8;

/** Opening a file: the oldest clean tab makes room; when every tab has unsaved changes the
 * new file is refused (the caller shows `t.projects.tooManyTabs`). */
export function openTab(tabs: OpenTab[], path: string, max = MAX_TABS): { tabs: OpenTab[]; refused: boolean } {
  if (tabs.some((tab) => tab.path === path)) return { tabs, refused: false };
  if (tabs.length < max) return { tabs: [...tabs, { path, dirty: false }], refused: false };
  const clean = tabs.findIndex((tab) => !tab.dirty);
  if (clean < 0) return { tabs, refused: true };
  return { tabs: [...tabs.slice(0, clean), ...tabs.slice(clean + 1), { path, dirty: false }], refused: false };
}

const fileName = (path: string) => path.slice(path.lastIndexOf("/") + 1) || path;

export function EditorTabs(props: {
  tabs: OpenTab[];
  active: string | null;
  onSelect: (path: string) => void;
  onClose: (path: string) => void;
  closing: string | null;
  onSaveClose: () => void;
  onDiscardClose: () => void;
  onCancelClose: () => void;
  notice: string | null;
}) {
  const t = useT();
  return (
    <div className="flex flex-col gap-1">
      <div role="tablist" aria-label={t.projects.tabs} className="flex overflow-x-auto border-b border-line">
        {props.tabs.map((tab) => {
          const active = tab.path === props.active;
          return (
            <div key={tab.path}
                 className={`flex shrink-0 items-center border-b-2 ${active ? "border-accent bg-accent-soft" : "border-transparent hover:bg-subtle"}`}>
              <button type="button" role="tab" aria-selected={active} title={tab.path}
                      onClick={() => props.onSelect(tab.path)}
                      className={`flex min-h-tap items-center gap-1.5 pl-3 pr-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${active ? "text-accent-strong" : "text-ink-2"}`}>
                <span className="max-w-[12rem] truncate">{fileName(tab.path)}</span>
                {tab.dirty && (
                  <>
                    <span className="h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden />
                    <span className="sr-only">{t.projects.unsaved}</span>
                  </>
                )}
              </button>
              <button type="button" aria-label={t.projects.closeTab(tab.path)} onClick={() => props.onClose(tab.path)}
                      className="mr-1 rounded p-1 text-ink-muted hover:bg-fill hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          );
        })}
      </div>
      {props.closing && (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-card border border-warning-line bg-warning-soft p-2 text-sm text-warning-deep">
          <span className="min-w-0 flex-1 break-all">{t.projects.unsavedClose(props.closing)}</span>
          <Button onClick={props.onSaveClose}>{t.projects.save}</Button>
          <Button variant="secondary" onClick={props.onDiscardClose}>{t.projects.discard}</Button>
          <Button variant="ghost" onClick={props.onCancelClose}>{t.projects.cancel}</Button>
        </div>
      )}
      {props.notice && !props.closing && (
        <p role="status" className="rounded-card border border-warning-line bg-warning-soft p-2 text-sm text-warning-deep">
          {props.notice}
        </p>
      )}
    </div>
  );
}
