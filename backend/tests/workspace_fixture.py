"""A small vibe-reporting workspace over the `origin_sales` fixture table, shared by the API
tests and the browser tests (`python -m tests.e2e_schema seed`). No conftest import here."""
import textwrap
from pathlib import Path

SPEC = "# {title}\n\n**Spec type**: {kind}\n\n**Status**: Implemented\n"
def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def spec(root: Path, kind: str, folder: str) -> None:
    write(root, f"specs/{kind}s/{folder}/spec.md", SPEC.format(title=folder, kind=kind))
    write(root, f"specs/{kind}s/{folder}/plan.md", "# Plan\n")
    write(root, f"specs/{kind}s/{folder}/tasks.md", "- [X] T001 hecho\n")


REPORT = """
    id: ventas
    spec: specs/reports/001-ventas
    title: {title}
    description: Resumen de ventas
    icon: chart-line
    uses:
      lines: ventas-prueba.sale_lines
      products: ventas-prueba.products
    joins: [{{left: lines.product_code, right: products.product_code, type: left}}]
    date: lines.local_date
    metrics:
      net_sales:
        label: Ventas netas
        format: currency
        better: higher
        sql: >-
          sum(case when lines.line_kind = 'sale' then lines.net_amount
          else -lines.net_amount end)
      orders:
        label: Pedidos
        format: integer
        sql: >-
          count(distinct case when lines.line_kind = 'sale' then lines.document_id end)
      avg_ticket: {{label: Ticket promedio, formula: net_sales / orders, format: currency}}
    dimensions:
      product: {{label: Producto, sql: products.product_code}}
    periods: {{default: mtd, allowed: [mtd, last_7_days, custom]}}
    compare: {{default: previous_period, allowed: [none, previous_period, previous_year]}}
    views:
      - {{type: kpis, metrics: [net_sales, orders, avg_ticket]}}
      - {{type: trend, metric: net_sales, grain: auto}}
      - {{type: ranking, dimension: product, metric: net_sales, limit: 5}}
    filters: [product]
    pdf: {{enabled: true}}
    ai_narrative: {{enabled: true, inputs: [net_sales, orders], with_comparison: true,
                   instructions: Resume en 2 frases.}}
"""


LAYOUT_REPORT = """
    id: ventas-layout
    spec: specs/reports/002-ventas-layout
    title: {title} (layout)
    description: Resumen de ventas con layout declarado
    icon: chart-line
    uses:
      lines: ventas-prueba.sale_lines
      products: ventas-prueba.products
    joins:
      - left: lines.product_code
        right: products.product_code
        type: left
    date: lines.local_date
    metrics:
      net_sales:
        label: Ventas netas
        format: currency
        better: higher
        sql: >-
          sum(case when lines.line_kind = 'sale' then lines.net_amount
          else -lines.net_amount end)
      orders:
        label: Pedidos
        format: integer
        sql: >-
          count(distinct case when lines.line_kind = 'sale' then lines.document_id end)
      avg_ticket:
        label: Ticket promedio
        formula: net_sales / orders
        format: currency
    dimensions:
      product:
        label: Producto
        sql: products.product_code
    periods:
      default: mtd
      allowed: [mtd, last_7_days, custom]
    compare:
      default: previous_period
      allowed: [none, previous_period, previous_year]
    views:
      - id: resumen
        type: kpis
        metrics: [net_sales, orders, avg_ticket]
      - id: diaria
        type: trend
        metric: net_sales
        grain: auto
      - id: productos
        type: ranking
        dimension: product
        metric: net_sales
        limit: 5
      - id: detalle
        type: table
        dimensions: [product]
        metrics: [net_sales, orders]
        limit: 50
    filters: [product]
    pdf:
      enabled: true
    layout:
      web:
        gutter: md
        components:
          - id: resumen_kpi
            type: kpi
            view: resumen
            metric: net_sales
            span: 12
          - id: tendencia
            type: line
            view: diaria
            x: day
            series: [net_sales]
            span: 8
          - id: ranking
            type: bar
            view: productos
            x: product
            series: [net_sales]
            orientation: horizontal
            span: 4
          - id: detalle
            type: table
            view: detalle
            columns: [product, net_sales, orders]
            totals: true
            page_size: 25
            span: 12
      pdf:
        page:
          size: a4
          orientation: portrait
        blocks:
          - id: cabecera
            type: header
            title: true
            subtitle: true
            period: true
          - id: kpis
            type: kpi_row
            view: resumen
            items: [net_sales, orders]
          - id: grafico
            type: chart
            view: diaria
            kind: line
            x: day
            series: [net_sales]
          - id: tabla
            type: table
            view: detalle
            columns: [product, net_sales]
            widths: [2, 1]
            totals: true
          - id: pie
            type: footer
            page_numbers: true
"""


def integration_yaml() -> str:
    return """
        id: ventas-prueba
        spec: specs/integrations/001-ventas-prueba
        source: Origen prueba
        schedule: "*/30 * * * *"
        timezone: America/Caracas
        time_limit_minutes: 5
        datasets:
          sale_lines:
            primary_key: [document_id, line_no, line_kind]
            date_column: local_date
            columns:
              document_id: {type: text, nullable: false}
              line_no: {type: integer, nullable: false}
              line_kind: {type: text, nullable: false, enum: [sale, return]}
              completed_at: {type: timestamptz, nullable: false}
              local_date: {type: date, nullable: false}
              product_code: {type: text, nullable: false}
              net_amount: {type: numeric, nullable: false, min: 0}
            extract: {query: queries/lines.sql, params: [window_start, window_end]}
            incremental: {window_days: 7, full_rebuild_cron: "0 3 * * *"}
            checks:
              - {type: reconcile, query: queries/totals.sql, compare: [local_date, net_amount]}
          products:
            primary_key: [product_code]
            columns:
              product_code: {type: text, nullable: false}
            extract: {query: queries/products.sql}
            incremental: {mode: full}
    """


def queries(origin: str) -> dict[str, str]:
    """Integration SQL over the origin table (a qualified name, e.g. "app_test_x".origin_sales)."""
    return {
        "lines.sql": (f"SELECT doc AS document_id, line AS line_no, kind AS line_kind, "
                      f"completed_at, "
                      f"(completed_at AT TIME ZONE 'America/Caracas')::date AS local_date, "
                      f"product AS product_code, amount AS net_amount FROM {origin} "
                      f"WHERE completed_at >= :window_start AND completed_at < :window_end\n"),
        "totals.sql": (f"SELECT (completed_at AT TIME ZONE 'America/Caracas')::date AS local_date, "
                       f"sum(amount) AS net_amount FROM {origin} "
                       f"WHERE completed_at >= :window_start AND completed_at < :window_end "
                       f"GROUP BY 1\n"),
        "products.sql": f"SELECT DISTINCT product AS product_code FROM {origin}\n",
    }


def build(root: Path, origin: str, *, source: str = "Origen prueba", title: str = "Ventas") -> Path:
    write(root, "bizview.yaml", "name: cliente\ncurrency: USD\n")
    spec(root, "integration", "001-ventas-prueba")
    write(root, "integrations/ventas-prueba/integration.yaml",
          integration_yaml().replace("source: Origen prueba", f"source: {source}"))
    for name, sql in queries(origin).items():
        write(root, f"integrations/ventas-prueba/queries/{name}", sql)
    spec(root, "report", "001-ventas")
    write(root, "reports/ventas/report.yaml", REPORT.format(title=title))
    spec(root, "report", "002-ventas-layout")
    write(root, "reports/ventas-layout/report.yaml", LAYOUT_REPORT.format(title=title))
    return root
