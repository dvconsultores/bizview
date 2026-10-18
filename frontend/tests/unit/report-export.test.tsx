import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReportView } from "../../src/api/types";
import { CardMenu } from "../../src/components/report/CardMenu";
import { DataTable } from "../../src/components/report/DataTable";
import { ExportSection } from "../../src/components/report/ExportSection";
import { RankingTable } from "../../src/components/report/RankingTable";

type TableView = Extract<ReportView, { type: "table" }>;
type RankingView = Extract<ReportView, { type: "ranking" }>;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  container.remove();
  vi.restoreAllMocks();
});

function render(node: ReactNode) {
  act(() => {
    root.render(node);
  });
}

function buttonsMatching(predicate: (el: HTMLButtonElement) => boolean): HTMLButtonElement[] {
  return Array.from(container.querySelectorAll("button")).filter(predicate);
}

function findButtonByText(text: string): HTMLButtonElement | null {
  return buttonsMatching((b) => b.textContent?.trim() === text)[0] ?? null;
}

async function readBlob(blob: Blob): Promise<string> {
  const bytes = await blob.arrayBuffer();
  const firstThree = new Uint8Array(bytes.slice(0, 3));
  expect(Array.from(firstThree)).toEqual([0xef, 0xbb, 0xbf]);
  return new TextDecoder("utf-8", { ignoreBOM: true }).decode(bytes);
}

describe("CardMenu", () => {
  it("opens on click, focuses the CSV action, and returns focus after the action", () => {
    const onDownloadCsv = vi.fn();
    render(<CardMenu title="Ventas por marca" onDownloadCsv={onDownloadCsv} />);

    const trigger = container.querySelector<HTMLButtonElement>("button[aria-label='Opciones de Ventas por marca']");
    expect(trigger).not.toBeNull();
    expect(trigger!.getAttribute("aria-expanded")).toBe("false");

    act(() => {
      trigger!.click();
    });
    expect(trigger!.getAttribute("aria-expanded")).toBe("true");

    const csvButton = findButtonByText("Descargar CSV");
    expect(csvButton).not.toBeNull();
    expect(document.activeElement).toBe(csvButton);

    act(() => {
      csvButton!.click();
    });
    expect(onDownloadCsv).toHaveBeenCalledTimes(1);
    expect(findButtonByText("Descargar CSV")).toBeNull();
    expect(trigger!.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(trigger);
  });

  it("closes with Escape and outside pointerdown", () => {
    const onDownloadCsv = vi.fn();
    render(<CardMenu title="Ventas por marca" onDownloadCsv={onDownloadCsv} />);

    const trigger = container.querySelector<HTMLButtonElement>("button[aria-label='Opciones de Ventas por marca']")!;

    act(() => {
      trigger.click();
    });
    const csvButton = findButtonByText("Descargar CSV")!;

    act(() => {
      csvButton.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
    });
    expect(findButtonByText("Descargar CSV")).toBeNull();
    expect(document.activeElement).toBe(trigger);

    act(() => {
      trigger.click();
    });
    expect(findButtonByText("Descargar CSV")).not.toBeNull();

    act(() => {
      const event =
        typeof PointerEvent !== "undefined"
          ? new PointerEvent("pointerdown", { bubbles: true })
          : new Event("pointerdown", { bubbles: true });
      document.body.dispatchEvent(event);
    });
    expect(findButtonByText("Descargar CSV")).toBeNull();
  });
});

describe("DataTable CSV download", () => {
  const tableView: TableView = {
    type: "table",
    title: "Detalle por día",
    columns: [
      { id: "day", label: "Día", kind: "dimension" },
      { id: "net", label: "Ventas netas", kind: "metric", format: "currency" },
    ],
    rows: [
      { day: "2026-09-01", net: 1234.5 },
      { day: "2026-09-02", net: null },
    ],
  };

  it("downloads the table CSV with the expected filename and contents", async () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    const createObjectURL = vi.fn((_blob: Blob) => "blob:x");
    const revokeObjectURL = vi.fn();

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: revokeObjectURL,
    });

    let downloadName: string | null = null;
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        downloadName = this.download;
      });

    try {
      render(
        <DataTable
          view={tableView}
          currency="USD"
          csvFileBase="ventas-2026-09-01-2026-09-30"
        />,
      );

      const trigger = container.querySelector<HTMLButtonElement>("button[aria-label='Opciones de Detalle por día']")!;
      act(() => {
        trigger.click();
      });
      const csvButton = findButtonByText("Descargar CSV")!;

      act(() => {
        csvButton.click();
      });

      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(downloadName).toBe("ventas-2026-09-01-2026-09-30-detalle-por-dia.csv");
      expect(createObjectURL).toHaveBeenCalledTimes(1);

      const blob = createObjectURL.mock.calls[0][0] as Blob;
      const text = await readBlob(blob);
      expect(text.startsWith("﻿")).toBe(true);
      expect(text).toBe("﻿Día;Ventas netas\r\n2026-09-01;1234.5\r\n2026-09-02;\r\n");
    } finally {
      clickSpy.mockRestore();
      Object.defineProperty(URL, "createObjectURL", {
        configurable: true,
        writable: true,
        value: originalCreateObjectURL,
      });
      Object.defineProperty(URL, "revokeObjectURL", {
        configurable: true,
        writable: true,
        value: originalRevokeObjectURL,
      });
    }
  });
});

describe("RankingTable menu availability", () => {
  const rankingView: RankingView = {
    type: "ranking",
    metric: "net",
    dimension: "brand",
    title: "Ventas por marca",
    label: "Ventas netas",
    dimension_label: "Marca",
    format: "currency",
    items: [{ key: "Acme", value: 10, share: 1, previous: null, change: null }],
  };
  const emptyRankingView: RankingView = { ...rankingView, items: [] };

  it("shows no menu when there are no items", () => {
    render(
      <RankingTable
        view={emptyRankingView}
        currency="USD"
        compared={false}
        better="higher"
      />,
    );
    expect(
      container.querySelector("button[aria-label='Opciones de Ventas por marca']"),
    ).toBeNull();
  });

  it("shows the menu when there are items", () => {
    render(
      <RankingTable
        view={rankingView}
        currency="USD"
        compared={false}
        better="higher"
      />,
    );
    expect(
      container.querySelector("button[aria-label='Opciones de Ventas por marca']"),
    ).not.toBeNull();
  });
});

describe("ExportSection", () => {
  it("defaults to PDF, can switch to CSV, and triggers the matching callback", () => {
    const onPdf = vi.fn();
    const onCsv = vi.fn();
    render(
      <ExportSection
        pdfAvailable
        csvAvailable
        ready
        pdfBusy={false}
        onPdf={onPdf}
        onCsv={onCsv}
      />,
    );

    const radios = Array.from(container.querySelectorAll<HTMLInputElement>("input[type='radio']"));
    expect(radios).toHaveLength(2);
    expect(radios.find((r) => r.value === "pdf")?.checked).toBe(true);

    act(() => {
      findButtonByText("Generar reporte")!.click();
    });
    expect(onPdf).toHaveBeenCalledTimes(1);
    expect(onCsv).not.toHaveBeenCalled();

    act(() => {
      radios.find((r) => r.value === "csv")!.click();
    });
    expect(radios.find((r) => r.value === "pdf")?.checked).toBe(false);
    expect(radios.find((r) => r.value === "csv")?.checked).toBe(true);

    act(() => {
      findButtonByText("Generar reporte")!.click();
    });
    expect(onCsv).toHaveBeenCalledTimes(1);
    expect(onPdf).toHaveBeenCalledTimes(1);
  });

  it("disables generate and shows the not-ready hint when not ready", () => {
    render(
      <ExportSection
        pdfAvailable
        csvAvailable
        ready={false}
        pdfBusy={false}
        onPdf={vi.fn()}
        onCsv={vi.fn()}
      />,
    );
    expect(findButtonByText("Generar reporte")!.disabled).toBe(true);
    expect(container.textContent).toContain(
      "Espera a que el reporte termine de cargar.",
    );
  });

  it("renders nothing when neither format is available", () => {
    render(
      <ExportSection
        pdfAvailable={false}
        csvAvailable={false}
        ready
        pdfBusy={false}
        onPdf={vi.fn()}
        onCsv={vi.fn()}
      />,
    );
    expect(container.children).toHaveLength(0);
  });

  it("shows only CSV and checks it when PDF is unavailable", () => {
    render(
      <ExportSection
        pdfAvailable={false}
        csvAvailable
        ready
        pdfBusy={false}
        onPdf={vi.fn()}
        onCsv={vi.fn()}
      />,
    );
    const radios = Array.from(container.querySelectorAll<HTMLInputElement>("input[type='radio']"));
    expect(radios).toHaveLength(1);
    expect(radios[0].value).toBe("csv");
    expect(radios[0].checked).toBe(true);
  });
});
