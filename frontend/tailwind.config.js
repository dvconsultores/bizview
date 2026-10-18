/** Steel-teal design system (feature 010, Customer A look). Brand colours are CSS variables
 * (src/index.css) so a deployment could change the primary colour without rebuilding the
 * component code. */
const brand = (n) => `rgb(var(--brand-${n}) / <alpha-value>)`;

/** Semantic colour tokens (feature 006, specs/006-dark-mode/contracts/theme-tokens.md): each is a
 * CSS variable with a light and a dark value in src/index.css, so one class serves both themes. */
const TOKENS = [
  "canvas", "surface", "subtle", "surface-2", "fill", "line-soft", "line", "line-strong",
  "ink", "ink-2", "ink-3", "ink-muted", "ink-soft", "ink-faint",
  "accent-bright", "accent", "accent-strong", "accent-deep", "accent-soft", "accent-soft-2",
  "accent-line", "accent-line-strong", "primary", "primary-hover", "primary-active", "focus",
  "danger-bright", "danger", "danger-strong", "danger-deep", "danger-soft", "danger-line",
  "danger-border", "danger-focus", "danger-solid", "danger-solid-hover", "danger-solid-active",
  "success-bright", "success", "success-strong", "success-deep", "success-soft", "success-line",
  "warning", "warning-strong", "warning-deep", "warning-soft", "warning-line",
  "backdrop", "toast", "chart-1", "chart-2", "chart-grid", "chart-axis", "chart-label",
  "field", "field-focus", "line-accent", "on-primary",
];
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: Object.fromEntries(
          [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map((n) => [n, brand(n)]),
        ),
        ...Object.fromEntries(TOKENS.map((name) => [name, token(name)])),
      },
      fontFamily: {
        sans: [
          "Plus Jakarta Sans", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial",
          "Noto Sans", "sans-serif",
        ],
        mono: [
          "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace",
        ],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1rem",
        card: "var(--radius-card)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        raised: "var(--shadow-raised)",
      },
      minHeight: { tap: "44px" },
      minWidth: { tap: "44px" },
    },
  },
  plugins: [],
};
