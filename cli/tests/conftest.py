"""A small valid workspace (Customer B-like) that tests break on purpose."""
import textwrap
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _spanish_messages(monkeypatch):
    """Tests assert Spanish messages whatever the developer's locale (feature 022)."""
    monkeypatch.setenv("BIZVIEW_LANG", "es")

SPEC = """# {title}

**Spec type**: {kind}

**Status**: {status}

Body.
"""


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def spec_folder(root: Path, kind: str, folder: str, *, status="Implemented", open_task=False):
    base = f"specs/{kind}s/{folder}"
    write(root, f"{base}/spec.md", SPEC.format(title=folder, kind=kind, status=status))
    write(root, f"{base}/plan.md", "# Plan\n")
    pending = "- [ ] T002 pendiente\n" if open_task else ""
    write(root, f"{base}/tasks.md", "- [X] T001 hecho\n" + pending)


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "cliente-b-bizview"
    write(root, "bizview.yaml", "name: cliente-b\n")
    spec_folder(root, "integration", "001-ventas")
    write(root, "integrations/ventas/integration.yaml", """
        id: ventas
        spec: specs/integrations/001-ventas
        source: Origen ERP
        schedule: "*/30 * * * *"
        timezone: America/Caracas
        datasets:
          sale_lines:
            primary_key: [document_id, line_no]
            date_column: local_date
            columns:
              document_id: {type: text, nullable: false}
              line_no: {type: integer, nullable: false}
              line_kind: {type: text, nullable: false, enum: [sale, return]}
              local_date: {type: date, nullable: false}
              product_code: {type: text, nullable: false}
              quantity: {type: numeric}
              net_amount: {type: numeric}
            extract:
              query: queries/sale_lines.sql
              params: [window_start, window_end]
            incremental: {window_days: 7, full_rebuild_cron: "0 3 * * *", slice: month}
            checks:
              - {type: not_null, columns: [document_id]}
          products:
            primary_key: [product_code]
            columns:
              product_code: {type: text, nullable: false}
              name: {type: text}
            extract: {query: queries/products.sql}
            incremental: {mode: full}
    """)
    write(root, "integrations/ventas/queries/sale_lines.sql", """
        SELECT d.id AS document_id, l.n AS line_no, 'sale' AS line_kind,
               d.fecha::date AS local_date, l.codigo AS product_code, l.cant AS quantity,
               l.total AS net_amount
        FROM documentos d JOIN lineas l ON l.doc = d.id
        WHERE d.fecha >= :window_start AND d.fecha < :window_end
    """)
    write(root, "integrations/ventas/queries/products.sql",
          "SELECT codigo AS product_code, nombre AS name FROM productos\n")
    spec_folder(root, "report", "001-resumen")
    write(root, "reports/resumen/report.yaml", """
        id: resumen
        spec: specs/reports/001-resumen
        title: Ventas
        uses:
          lines: ventas.sale_lines
          products: ventas.products
        joins: [{left: lines.product_code, right: products.product_code}]
        date: lines.local_date
        metrics:
          net_sales: {label: Ventas netas, sql: "sum(lines.net_amount)", format: currency}
          orders: {label: Pedidos, sql: "count(distinct lines.document_id)", format: integer}
          ticket: {label: Ticket, formula: net_sales / orders, format: currency}
        dimensions:
          product: {label: Producto, sql: products.name}
        views:
          - {type: kpis, metrics: [net_sales, orders, ticket]}
          - {type: trend, metric: net_sales}
          - {type: ranking, dimension: product, metric: net_sales, limit: 10}
        filters: [product]
        ai_narrative: {enabled: true, inputs: [net_sales, orders]}
    """)
    return root
