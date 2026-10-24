/** Feature 030 (US5, FR-008): Administración → Apariencia lists every preset with a two-theme
 * preview, saves through the API and reports failures. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string, public fields: Record<string, string> = {}) {
      super(message);
    }
  },
}));

vi.mock("../../src/components/Toast", () => ({
  useToast: () => vi.fn(),
}));

import { api, ApiError } from "../../src/api/client";
import { Appearance } from "../../src/pages/admin/Appearance";
import { t } from "../../src/i18n/es";
import { PRESET_IDS } from "../../src/theme/palette";

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

async function render() {
  await act(async () => {
    root?.render(
      <MemoryRouter initialEntries={["/admin/apariencia"]}>
        <Appearance />
      </MemoryRouter>,
    );
  });
  await act(async () => {
    await Promise.resolve();
  });
}

describe("Appearance page", () => {
  it("offers every preset with a light and a dark preview", async () => {
    vi.mocked(api.get).mockResolvedValue({ palette_preset: "impacto", presets: [...PRESET_IDS] });
    await render();
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/admin/appearance");
    const radios = document.querySelectorAll('[role="radio"]');
    expect(radios).toHaveLength(PRESET_IDS.length);
    expect(document.querySelectorAll("[data-theme-preview]")).toHaveLength(PRESET_IDS.length * 2);
  });

  it("marks the installation preset as in use", async () => {
    vi.mocked(api.get).mockResolvedValue({ palette_preset: "clasico", presets: [...PRESET_IDS] });
    await render();
    const checked = document.querySelector('[role="radio"][aria-checked="true"]');
    expect(checked?.textContent).toContain(t.palette.clasico);
    expect(document.body.textContent).toContain(t.appearance.current);
  });

  it("saves the chosen preset", async () => {
    vi.mocked(api.get).mockResolvedValue({ palette_preset: "impacto", presets: [...PRESET_IDS] });
    vi.mocked(api.put).mockResolvedValue({ palette_preset: "contraste" });
    await render();
    const target = Array.from(document.querySelectorAll('[role="radio"]')).find((el) =>
      el.textContent?.includes(t.palette.contraste),
    ) as HTMLButtonElement;
    await act(async () => target.click());
    const save = Array.from(document.querySelectorAll("button")).find(
      (el) => el.textContent === t.common.save,
    ) as HTMLButtonElement;
    expect(save.disabled).toBe(false);
    await act(async () => save.click());
    expect(vi.mocked(api.put)).toHaveBeenCalledWith("/api/admin/appearance", { palette_preset: "contraste" });
  });

  it("keeps Guardar disabled until something changes", async () => {
    vi.mocked(api.get).mockResolvedValue({ palette_preset: "impacto", presets: [...PRESET_IDS] });
    await render();
    const save = Array.from(document.querySelectorAll("button")).find(
      (el) => el.textContent === t.common.save,
    ) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
  });

  it("shows the server message when saving fails", async () => {
    vi.mocked(api.get).mockResolvedValue({ palette_preset: "impacto", presets: [...PRESET_IDS] });
    vi.mocked(api.put).mockRejectedValue(new ApiError(422, "validation", "Paleta desconocida"));
    await render();
    const target = Array.from(document.querySelectorAll('[role="radio"]')).find((el) =>
      el.textContent?.includes(t.palette.daltonico),
    ) as HTMLButtonElement;
    await act(async () => target.click());
    const save = Array.from(document.querySelectorAll("button")).find(
      (el) => el.textContent === t.common.save,
    ) as HTMLButtonElement;
    await act(async () => save.click());
    expect(document.body.textContent).toContain("Paleta desconocida");
  });
});
