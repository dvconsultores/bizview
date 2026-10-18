import type { ReportView } from "../api/types";
import { t } from "../i18n/live";
import { localized } from "./labels";

export type CsvValue = string | number | boolean | Date | null | undefined;

export interface CsvColumn {
  id: string;
  label: string;
}

export interface CsvTable {
  title: string;
  columns: CsvColumn[];
  rows: Record<string, CsvValue>[];
}

export const CSV_BOM = "﻿";
export const CSV_SEPARATOR = ";";

function isFormulaPrefix(ch: string): boolean {
  return ch === "=" || ch === "+" || ch === "-" || ch === "@" || ch === "\t" || ch === "\r";
}

function numberToString(value: number): string {
  if (Number.isNaN(value) || !Number.isFinite(value)) return "";
  if (Object.is(value, -0)) return "0";
  const abs = Math.abs(value);
  if (abs >= 1e21) {
    return String(value);
  }
  const str = String(value);
  if (!str.includes("e")) return str;

  // Expand scientific notation without exponent.
  const [mantissaPart, exponentPart] = str.split("e");
  const exponent = parseInt(exponentPart, 10);
  const negative = mantissaPart.startsWith("-");
  const mantissa = negative
    ? mantissaPart.slice(1)
    : mantissaPart;
  const [integerPart, decimalPart = ""] = mantissa.split(".");
  const digits = integerPart + decimalPart;
  const pointPosition = integerPart.length + exponent;

  let expanded: string;
  if (pointPosition <= 0) {
    expanded = `0.${"0".repeat(-pointPosition)}${digits}`;
  } else if (pointPosition >= digits.length) {
    expanded = `${digits}${"0".repeat(pointPosition - digits.length)}`;
  } else {
    expanded = `${digits.slice(0, pointPosition)}.${digits.slice(pointPosition)}`;
  }

  expanded = expanded.replace(/\.?0+$/, "");
  if (expanded === "" || expanded === "-") expanded = "0";
  return negative ? `-${expanded}` : expanded;
}

export function csvCell(v: CsvValue): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (Number.isNaN(v) || !Number.isFinite(v)) return "";
    return numberToString(v);
  }
  if (v instanceof Date) {
    const isLocalMidnight =
      v.getHours() === 0 &&
      v.getMinutes() === 0 &&
      v.getSeconds() === 0 &&
      v.getMilliseconds() === 0;
    const text = isLocalMidnight
      ? `${v.getFullYear()}-${String(v.getMonth() + 1).padStart(2, "0")}-${String(v.getDate()).padStart(2, "0")}`
      : v.toISOString();
    return csvCell(text);
  }

  let text = String(v);
  if (typeof v === "string" && text.length > 0 && isFormulaPrefix(text[0])) {
    text = `'${text}`;
  }
  return quoteCsvValue(text);
}

function quoteCsvValue(text: string): string {
  if (
    text.includes(CSV_SEPARATOR) ||
    text.includes('"') ||
    text.includes("\r") ||
    text.includes("\n") ||
    text !== text.trim()
  ) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function toCsv(
  columns: CsvColumn[],
  rows: Record<string, CsvValue>[],
  opts: { bom?: boolean } = {},
): string {
  const withBom = opts.bom !== false;
  const header = columns.map((column) => csvCell(column.label)).join(CSV_SEPARATOR);
  const lines = [header];

  for (const row of rows) {
    const cells = columns.map((column) => csvCell(row[column.id] ?? null));
    lines.push(cells.join(CSV_SEPARATOR));
  }

  const body = lines.join("\r\n") + "\r\n";
  return withBom ? CSV_BOM + body : body;
}

export function toCsvSections(tables: CsvTable[]): string {
  const sections: string[] = [];
  for (const table of tables) {
    const titleLine = csvCell(table.title) + "\r\n";
    const body = toCsv(table.columns, table.rows, { bom: false });
    sections.push(titleLine + body.replace(/\r\n$/, ""));
  }
  return CSV_BOM + sections.join("\r\n\r\n") + "\r\n";
}

export function viewCsvTable(view: ReportView): CsvTable | null {
  if (view.type === "table") {
    return {
      title: localized(view, "title") ?? t.reportParams.detailTitle,
      columns: view.columns.map((column) => ({ id: column.id, label: localized(column, "label") })),
      rows: view.rows,
    };
  }

  if (view.type === "ranking") {
    const columns: CsvColumn[] = [
      { id: "key", label: localized(view, "dimension_label") },
      { id: "value", label: localized(view, "label") },
      { id: "share", label: t.reportParams.display.shareColumn },
    ];

    const hasPrevious = view.items.some((item) => item.previous !== null);
    if (hasPrevious) {
      columns.push({ id: "previous", label: t.reportParams.display.previousPeriodColumn });
      columns.push({ id: "change", label: t.reportParams.display.changeColumn });
    }

    const rows = view.items.map((item) => {
      const row: Record<string, CsvValue> = {
        key: item.key,
        value: item.value,
        share: item.share,
      };
      if (hasPrevious) {
        row.previous = item.previous;
        row.change = item.change?.pct ?? null;
      }
      return row;
    });

    return { title: localized(view, "title"), columns, rows };
  }

  return null;
}

export function csvFileName(base: string): string {
  const normalized = base
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
  const slug = normalized
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${slug || "reporte"}.csv`;
}

export function downloadCsv(filename: string, text: string): void {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
