import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { Compartment, EditorState, type Extension } from "@codemirror/state";
import { drawSelection, EditorView, highlightActiveLine, keymap, lineNumbers } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import { bracketMatching, defaultHighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { type Diagnostic, linter, lintGutter } from "@codemirror/lint";
import { yaml } from "@codemirror/lang-yaml";
import { sql } from "@codemirror/lang-sql";
import { markdown } from "@codemirror/lang-markdown";
import { json } from "@codemirror/lang-json";
import type { ProjectIssue } from "../../api/types";

export interface CodeEditorHandle {
  goToLine(line: number): void;
  focus(): void;
}

interface CodeEditorProps {
  value: string;
  path: string;
  readOnly?: boolean;
  problems?: ProjectIssue[];
  onChange?: (v: string) => void;
  onSave?: () => void;
  ariaLabel: string;
}

function language(path: string): Extension {
  const ext = path.split(".").pop()?.toLowerCase();
  if (ext === "yaml" || ext === "yml") return yaml();
  if (ext === "sql") return sql();
  if (ext === "md") return markdown();
  if (ext === "json") return json();
  return [];
}

function clamp(line: number, lines: number): number {
  return Math.min(Math.max(1, line), lines);
}

/** Problems with a line become lint markers (the message carries the fix). */
function lint(problems: ProjectIssue[]): Extension {
  return linter((view) => problems.flatMap((p): Diagnostic[] => {
    if (typeof p.line !== "number" || p.line < 1) return [];
    const line = view.state.doc.line(clamp(p.line, view.state.doc.lines));
    return [{ from: line.from, to: line.to, severity: "error",
              message: p.fix ? `${p.message} — ${p.fix}` : p.message }];
  }));
}

/** CodeMirror 6 editor: language by extension, line numbers, search, history, lint markers. */
export const CodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function CodeEditor(
  { value, path, readOnly = false, problems = [], onChange, onSave, ariaLabel }, ref,
) {
  const host = useRef<HTMLDivElement | null>(null);
  const view = useRef<EditorView | null>(null);
  const external = useRef(false);
  const handlers = useRef({ onChange, onSave });
  handlers.current = { onChange, onSave };
  const parts = useRef({ readOnly: new Compartment(), language: new Compartment(),
                         lint: new Compartment() });

  useImperativeHandle(ref, () => ({
    goToLine(line: number) {
      const v = view.current;
      if (!v) return;
      const pos = v.state.doc.line(clamp(line, v.state.doc.lines)).from;
      v.dispatch({ selection: { anchor: pos },
                   effects: EditorView.scrollIntoView(pos, { y: "center" }) });
      v.focus();
    },
    focus() {
      view.current?.focus();
    },
  }), []);

  useEffect(() => {
    if (!host.current) return;
    const p = parts.current;
    const v = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbers(), highlightActiveLine(), drawSelection(), history(), lintGutter(),
          highlightSelectionMatches(), bracketMatching(),
          syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
          keymap.of([{ key: "Mod-s", run: () => { handlers.current.onSave?.(); return true; } },
                     ...defaultKeymap, ...historyKeymap, ...searchKeymap, indentWithTab]),
          p.readOnly.of(EditorState.readOnly.of(readOnly)),
          p.language.of(language(path)),
          p.lint.of(lint(problems)),
          EditorView.updateListener.of((u) => {
            if (u.docChanged && !external.current) handlers.current.onChange?.(u.state.doc.toString());
          }),
          EditorView.contentAttributes.of({ "aria-label": ariaLabel }),
        ],
      }),
    });
    view.current = v;
    return () => {
      v.destroy();
      view.current = null;
    };
    // The view is created once; props below are applied through compartments.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const v = view.current;
    if (!v || v.state.doc.toString() === value) return;
    external.current = true;
    v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    external.current = false;
  }, [value]);

  useEffect(() => {
    view.current?.dispatch({ effects: parts.current.readOnly.reconfigure(
      EditorState.readOnly.of(readOnly)) });
  }, [readOnly]);

  useEffect(() => {
    view.current?.dispatch({ effects: parts.current.language.reconfigure(language(path)) });
  }, [path]);

  useEffect(() => {
    view.current?.dispatch({ effects: parts.current.lint.reconfigure(lint(problems)) });
  }, [problems]);

  return <div ref={host} className="bizview-cm h-full" />;
});
