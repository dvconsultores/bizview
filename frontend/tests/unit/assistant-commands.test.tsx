/** Feature 021 T038/T039/T041: `/` menu, chips, suggestions and spec picker in the chat. */
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
      public fields: Record<string, string> = {},
      public retryAfter?: number,
      public details: Record<string, unknown> = {},
    ) {
      super(message);
    }
  },
  qs: () => "",
}));
vi.mock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({ ai_enabled: true }),
}));

import { api, ApiError } from "../../src/api/client";
import type { AssistantSession, CommandDef } from "../../src/api/types";
import { AssistantChat } from "../../src/components/assistant/AssistantChat";
import { __resetCommandsCache } from "../../src/components/assistant/useCommands";
import { t } from "../../src/i18n/es";

const commands: CommandDef[] = [
  { name: "speckit-specify", description: "Crea la spec", argument_hint: "<descripción>", needs_spec: false, needs_args: true },
  { name: "speckit-plan", description: "Escribe el plan técnico", argument_hint: "<detalles>", needs_spec: true, needs_args: false },
  { name: "speckit-tasks", description: "Genera tareas a partir del plan", argument_hint: "<indicaciones>", needs_spec: true, needs_args: false },
];

const base: AssistantSession = {
  id: 7,
  title: "Prueba",
  status: "open",
  draft: null,
  validation: null,
  preview: null,
  applied_version_id: null,
  tokens_used: 0,
  token_budget: 1000,
  created_at: "2026-10-11T10:00:00Z",
  updated_at: "2026-10-11T10:00:00Z",
  messages: [],
  busy: false,
  current_spec: null,
  command_runs: [],
  active_command: null,
};

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.clearAllMocks();
  __resetCommandsCache();
  vi.mocked(api.get).mockImplementation(async (path: string) =>
    path === "/api/assistant/commands" ? { items: commands } : base,
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

function Harness({ initial }: { initial: AssistantSession }) {
  const [s, setS] = useState<AssistantSession | null>(initial);
  return <AssistantChat session={s} onSession={setS} />;
}
async function renderChat(initial: AssistantSession = base) {
  await act(async () => root.render(<Harness initial={initial} />));
}
const textarea = () => container.querySelector("textarea") as HTMLTextAreaElement;
async function type(raw: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
  await act(async () => {
    setter.call(textarea(), raw);
    textarea().dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => new Promise((r) => setTimeout(r, 0)));
}
async function key(name: string) {
  await act(async () => {
    textarea().dispatchEvent(new KeyboardEvent("keydown", { key: name, bubbles: true }));
  });
}
async function click(el: Element | undefined | null) {
  await act(async () => (el as HTMLElement).click());
  await act(async () => new Promise((r) => setTimeout(r, 0)));
}
const buttonWith = (text: string) =>
  Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes(text));

describe("command menu in the composer", () => {
  it("opens on /, moves with the keys and inserts without sending", async () => {
    await renderChat();
    await type("/pl");
    const ta = textarea();
    expect(ta.getAttribute("role")).toBe("combobox");
    expect(ta.getAttribute("aria-expanded")).toBe("true");
    const options = container.querySelectorAll('[role="option"]');
    expect(Array.from(options).map((o) => o.textContent)).toEqual([
      expect.stringContaining("/speckit-plan"),
      expect.stringContaining("/speckit-tasks"),
    ]);
    expect(ta.getAttribute("aria-activedescendant")).toBe(options[0].id);
    await key("ArrowDown");
    expect(ta.getAttribute("aria-activedescendant")).toBe(options[1].id);
    await key("Enter");
    expect(ta.value).toBe("/speckit-tasks ");
    expect(api.post).not.toHaveBeenCalled();
    expect(container.textContent).toContain(
      t.assistant.commands.argumentHint.replace("{hint}", "<indicaciones>"),
    );
  });

  it("Escape closes the menu and keeps the text", async () => {
    await renderChat();
    await type("/spe");
    await key("Escape");
    expect(container.querySelector('[role="listbox"]')).toBeNull();
    expect(textarea().value).toBe("/spe");
    expect(textarea().getAttribute("aria-expanded")).toBe("false");
  });

  it("plain text never fetches the commands", async () => {
    await renderChat();
    await type("hola");
    expect(api.get).not.toHaveBeenCalled();
  });
});

describe("command errors", () => {
  it("needs_spec shows the spec picker, sets the spec and resends", async () => {
    vi.mocked(api.post)
      .mockRejectedValueOnce(
        new ApiError(409, "needs_spec", "Elige la spec", {}, undefined, {
          command: "speckit-plan",
          specs: [{ folder: "001-ventas", title: "Ventas", kind: "reporte", stage: "especificada" }],
        }),
      )
      .mockResolvedValueOnce({ messages: [], session: { ...base, current_spec: "001-ventas" } });
    vi.mocked(api.patch).mockResolvedValueOnce({ ...base, current_spec: "001-ventas" });
    await renderChat();
    await type("/speckit-plan");
    await click(buttonWith(t.assistant.send));
    expect(container.querySelector("[data-spec-picker]")).not.toBeNull();
    await click(buttonWith("001-ventas"));
    expect(api.patch).toHaveBeenCalledWith("/api/assistant/sessions/7", { current_spec: "001-ventas" });
    expect(vi.mocked(api.post).mock.calls[1]).toEqual([
      "/api/assistant/sessions/7/messages",
      { text: "/speckit-plan" },
    ]);
    expect(container.querySelector("[data-spec-picker]")).toBeNull();
  });

  it("unknown_command lists the commands as insert buttons", async () => {
    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiError(422, "unknown_command", "Comando desconocido: /x", {}, undefined, {
        commands: ["speckit-plan", "ayuda"],
      }),
    );
    await renderChat();
    await type("/x algo");
    await click(buttonWith(t.assistant.send));
    expect(container.textContent).toContain(t.assistant.commands.unknownCommand);
    const inserts = container.querySelectorAll("[data-command-suggestion]");
    expect(inserts).toHaveLength(2);
    await click(inserts[0]);
    expect(textarea().value).toBe("/speckit-plan ");
  });
});

describe("chips and suggestions", () => {
  const withRun: AssistantSession = {
    ...base,
    current_spec: "001-ventas",
    messages: [
      { id: 1, role: "user", content: "/speckit-clarify", created_at: "" },
      {
        id: 2,
        role: "assistant",
        content: "¿Periodo?",
        created_at: "",
        suggestions: [{ command: "speckit-plan", arguments: "" }],
      },
    ],
    command_runs: [
      {
        id: 5,
        message_id: 1,
        command: "speckit-clarify",
        spec: "001-ventas",
        status: "waiting",
        files: [{ path: "specs/001-ventas/spec.md", action: "write", revision_id: 9 }],
        tokens: 10,
        started_at: "",
        ended_at: null,
      },
    ],
    active_command: { id: 5, command: "speckit-clarify", spec: "001-ventas", status: "waiting", pending: null },
  };

  it("renders the run chip after its message and Terminar finishes it", async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ...withRun, active_command: null });
    await renderChat(withRun);
    const chip = container.querySelector('[data-command-run="5"]');
    expect(chip?.textContent).toContain("Ejecutando /speckit-clarify en 001-ventas");
    await click(buttonWith(t.assistant.commands.finish));
    expect(api.post).toHaveBeenCalledWith("/api/assistant/sessions/7/command/finish");
  });

  it("an Insertar suggestion fills the composer", async () => {
    await renderChat(withRun);
    await click(container.querySelector("[data-command-suggestion]"));
    expect(textarea().value).toBe("/speckit-plan ");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("a filled suggestion does not take focus, so a stray Enter cannot send it", async () => {
    await renderChat(withRun);
    await click(container.querySelector("[data-command-suggestion]"));
    expect(textarea().value).toBe("/speckit-plan ");
    expect(document.activeElement).not.toBe(textarea());
    expect(api.post).not.toHaveBeenCalled();
  });
});
