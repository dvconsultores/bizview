import { act } from "react";
import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { beforeEach, afterEach, describe, expect, it } from "vitest";
import { Badge } from "../../src/components/Badge";
import { Breadcrumbs } from "../../src/components/Breadcrumbs";
import { CodeChip } from "../../src/components/CodeChip";
import { HubCard } from "../../src/components/HubCard";
import { StatTile } from "../../src/components/StatTile";
import { WelcomeBanner } from "../../src/components/WelcomeBanner";
import { t } from "../../src/i18n/es";

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
});

const render = async (node: React.ReactNode) => {
  await act(async () => {
    root.render(<StrictMode>{node}</StrictMode>);
  });
  return container;
};

describe("Badge", () => {
  it("does not wrap by default", async () => {
    await render(<Badge>demo</Badge>);
    const span = container.querySelector("span");
    expect(span).not.toBeNull();
    expect(span!.classList.contains("whitespace-nowrap")).toBe(true);
    expect(span!.classList.contains("whitespace-normal")).toBe(false);
  });

  it("wraps when wrap is true", async () => {
    await render(<Badge wrap>demo</Badge>);
    const span = container.querySelector("span");
    expect(span).not.toBeNull();
    expect(span!.classList.contains("whitespace-normal")).toBe(true);
    expect(span!.classList.contains("break-words")).toBe(true);
    expect(span!.classList.contains("max-w-full")).toBe(true);
    expect(span!.classList.contains("whitespace-nowrap")).toBe(false);
  });
});

describe("StatTile", () => {
  it("renders label, value and footnote text", async () => {
    const el = await render(<StatTile label="Ventas" value={42} footnote="Total del mes" />);
    expect(el.textContent).toContain("Ventas");
    expect(el.textContent).toContain("42");
    expect(el.textContent).toContain("Total del mes");
  });

  it("renders positive delta with es locale decimal and success colour", async () => {
    const el = await render(
      <StatTile label="Ventas" value={42} delta={{ value: 12.5, suffix: "%", label: "vs. mes anterior" }} />,
    );
    const deltaRow = el.querySelector(".text-success");
    expect(deltaRow).not.toBeNull();
    expect(deltaRow?.textContent).toContain("+12,5%");
    expect(deltaRow?.textContent).toContain("vs. mes anterior");
  });

  it("renders negative delta with danger colour and a minus sign", async () => {
    const el = await render(<StatTile label="Ventas" value={42} delta={{ value: -3 }} />);
    const deltaRow = el.querySelector(".text-danger");
    expect(deltaRow).not.toBeNull();
    expect(deltaRow?.textContent).toMatch(/[-−]3/);
  });

  it("uses danger when a positive value is considered bad", async () => {
    const el = await render(
      <StatTile label="Errores" value={7} delta={{ value: 4, positiveIsGood: false }} />,
    );
    expect(el.querySelector(".text-danger")).not.toBeNull();
  });

  it("shows zero delta as muted without a sign", async () => {
    const el = await render(<StatTile label="Ventas" value={42} delta={{ value: 0 }} />);
    const deltaRow = Array.from(el.querySelectorAll(".text-ink-muted")).find(
      (node) => node.tagName === "DIV" && node.classList.contains("font-semibold"),
    );
    expect(deltaRow).not.toBeNull();
    expect(deltaRow?.textContent).toBe("0");
    expect(deltaRow?.textContent).not.toMatch(/[+\-−]/);
  });
});

describe("Breadcrumbs", () => {
  const items = [
    { label: "Administración", to: "/admin" },
    { label: "Usuarios", to: "/admin/usuarios" },
    { label: "Ana" },
  ];

  it("renders back link, nav label, hrefs and current page marker", async () => {
    const el = await render(
      <MemoryRouter>
        <Breadcrumbs back="/admin" items={items} />
      </MemoryRouter>,
    );

    const backLink = Array.from(el.querySelectorAll("a")).find((a) => a.textContent === t.common.back);
    expect(backLink).not.toBeNull();
    expect(backLink?.getAttribute("href")).toBe("/admin");

    const nav = el.querySelector("nav");
    expect(nav?.getAttribute("aria-label")).toBe(t.design.breadcrumbs);

    const current = el.querySelector('[aria-current="page"]');
    expect(current).not.toBeNull();
    expect(current?.textContent).toBe("Ana");
    expect(current?.tagName.toLowerCase()).not.toBe("a");

    const navLinks = Array.from(el.querySelectorAll("nav a"));
    expect(navLinks.map((a) => a.getAttribute("href"))).toEqual(["/admin", "/admin/usuarios"]);
  });
});

describe("WelcomeBanner", () => {
  it("renders welcome heading with name, time and correct aria-labelledby", async () => {
    const el = await render(
      <WelcomeBanner name="Ana" date={new Date(2026, 9, 1)} subtitle="Todo en orden" />,
    );
    const h1 = el.querySelector("h1");
    expect(h1?.textContent).toBe("Bienvenido de nuevo, Ana");
    expect(el.querySelector("section")?.getAttribute("aria-labelledby")).toBe(h1?.id);
    const time = el.querySelector("time");
    expect(time?.getAttribute("dateTime")).toBe("2026-10-01");
    expect(time?.textContent?.charAt(0)).toBe(time?.textContent?.charAt(0)?.toUpperCase());
    expect(time?.textContent).toContain("2026");
  });

  it("renders only the welcome string when name is blank", async () => {
    const el = await render(<WelcomeBanner name="   " />);
    expect(el.querySelector("h1")?.textContent).toBe(t.design.welcomeBack);
  });
});

describe("HubCard", () => {
  it("renders a single link with correct accessible name and description", async () => {
    const el = await render(
      <MemoryRouter>
        <HubCard to="/tableros/ventas" title="Ventas" description="Resumen mensual" />
      </MemoryRouter>,
    );

    const links = el.querySelectorAll("a");
    expect(links).toHaveLength(1);
    const link = links[0];
    expect(link.getAttribute("href")).toBe("/tableros/ventas");

    const labelledby = link.getAttribute("aria-labelledby");
    expect(labelledby).toBeTruthy();
    const titleEl = labelledby ? document.getElementById(labelledby) : null;
    expect(titleEl?.textContent).toBe("Ventas");

    const describedby = link.getAttribute("aria-describedby");
    expect(describedby).toBeTruthy();
    const descriptionEl = describedby ? document.getElementById(describedby) : null;
    expect(descriptionEl?.textContent).toBe("Resumen mensual");
  });
});

describe("CodeChip", () => {
  it("renders a code element containing its children", async () => {
    const el = await render(<CodeChip>ABC-123</CodeChip>);
    const code = el.querySelector("code");
    expect(code).not.toBeNull();
    expect(code?.textContent).toBe("ABC-123");
  });
});
