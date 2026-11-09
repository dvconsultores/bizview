import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Feature 062 — US5. Until 062 the source form's actions were `sticky bottom-20` on a translucent
 * blur bar: 80 px above the bottom (the tab bar's old height), floating over the fields it saves.
 * The owner reversed that, so the assertions are about position in the document and about the
 * absence of any positioned ancestor — the two things a CSS class alone cannot promise.
 */

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  },
  qs: () => "",
}));

vi.mock("../../src/components/Toast", () => ({ useToast: () => vi.fn() }));

import { api } from "../../src/api/client";
import { SourceForm } from "../../src/pages/admin/SourceForm";
import { t } from "../../src/i18n/es";

const types = {
  postgresql: {
    label: "PostgreSQL",
    http_allowed: true,
    available: true,
    reason: "",
    fields: [
      { name: "host", label: "Servidor", type: "string", required: true, secret: false,
        default: "", options: [], help: "", min: null, max: null, show_if: {} },
    ],
  },
};

const source = {
  id: 7,
  name: "ERP",
  kind: "postgresql",
  description: "",
  enabled: true,
  direct_reports: false,
  settings: { host: "db.example" },
  secret_fields: [],
  imported: false,
  last_test: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
};

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

async function renderForm(entry: string) {
  (api.get as ReturnType<typeof vi.fn>).mockImplementation(async (path: string) => {
    if (path === "/api/sources/types") return types;
    if (path.startsWith("/api/sources/")) return source;
    return null;
  });
  await act(async () => {
    root?.render(
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/admin/fuentes/nueva" element={<SourceForm />} />
          <Route path="/admin/fuentes/:id" element={<SourceForm />} />
        </Routes>
      </MemoryRouter>,
    );
  });
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });
}

describe("source form actions (feature 062)", () => {
  it("keeps the actions static, at the end of the form, in the order Guardar → Probar → Eliminar", async () => {
    await renderForm("/admin/fuentes/7");
    const actions = container.querySelector("[data-source-actions]") as HTMLElement;
    expect(actions, "the actions block must be identifiable and static").not.toBeNull();
    expect(actions.className).not.toContain("sticky");
    expect(actions.className).not.toContain("fixed");
    expect(actions.className).not.toContain("backdrop");
    // It is the last block of the page, so nothing floats over the fields it saves.
    const page = actions.parentElement as HTMLElement;
    const lastChild = Array.from(page.children).filter(
      (node) => !(node as HTMLElement).classList?.contains("hidden"),
    ).at(-1);
    expect(lastChild).toBe(actions);

    const buttons = Array.from(actions.querySelectorAll("button")).map(
      (button) => (button.textContent ?? "").trim(),
    );
    const save = buttons.indexOf(t.admin.sourceForm.save);
    const test = buttons.indexOf(t.admin.sourceForm.test);
    const remove = buttons.indexOf(t.admin.sourceForm.delete);
    expect(save).toBeGreaterThanOrEqual(0);
    expect(save).toBeLessThan(test);
    expect(test).toBeLessThan(remove);
  });

  it("leaves no sticky or fixed element on the screen", async () => {
    await renderForm("/admin/fuentes/7");
    const offenders = Array.from(container.querySelectorAll("*")).filter((node) => {
      const className = node.getAttribute("class") ?? "";
      return /\b(sticky|fixed)\b/.test(className);
    });
    expect(offenders.map((node) => node.className)).toEqual([]);
  });

  it("keeps clearance for the phone's bottom tab bar", async () => {
    await renderForm("/admin/fuentes/7");
    const actions = container.querySelector("[data-source-actions]") as HTMLElement;
    // 16 px at least, and the safe-area inset where the device has one.
    expect(actions.className).toContain("pb-[max(1rem,env(safe-area-inset-bottom))]");
  });
});
