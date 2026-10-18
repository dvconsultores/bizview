# Quickstart & Validation: Vibe Reporting

**Feature**: [spec.md](./spec.md) | **Contracts**: [artifacts](./contracts/artifacts.md), [api](./contracts/api.md)

## The vibe reporting loop

```bash
uv tool install bizview-cli                     # from the release
bizview init ~/work/cliente-b-bizview --name cliente-b
cd ~/work/cliente-b-bizview && code .          # or claude
# in the agent:
/speckit-specify  Integration: ventas y productos desde el origen "Origen ERP" …
/speckit-plan     →  /speckit-tasks  →  /speckit-implement     (after_implement hook: bizview validate)
/speckit-specify  Report: Ventas, usa la integración erp-ventas …
…
git push                                          # private repository
# on the server: git -C /opt/bizview/workspace pull; super user → Espacio de trabajo → Validar → Aplicar
```

Structure for the AI: `export BIZVIEW_URL=http://localhost:8080 BIZVIEW_TOKEN=…;
bizview describe "Origen ERP"`.

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | `bizview init` in an empty folder | workspace layout (research R2), preset + extension installed, `specify preset resolve spec-template` → bizview | US1, FR-005 |
| 2 | Agent asked "haz un reporte de ventas" without a spec | agent starts `/speckit-specify` (instructions) | FR-004 |
| 3 | Artifact whose spec has an open task | `bizview validate` exit 1 `open_tasks`; apply refuses | FR-001, FR-002 |
| 4 | Edit `report.yaml` after validate | apply → `lock_mismatch` | FR-002, US4 |
| 5 | Integration SQL with `DELETE` / `pg_read_file` / two statements | `unsafe_sql` | FR-009 |
| 6 | Integration referencing an unknown source | `unknown_source` at apply | FR-017 |
| 7 | Apply Customer B workspace; run integration | datasets in `ds_erp_ventas`, checks ok, run recorded | US2, FR-010 |
| 8 | Two reports on one integration | one extraction per schedule; both dashboards render | US3, SC-003 |
| 9 | Report at 320/375 px, three engines | KPIs/trend/rankings, no horizontal scroll, axe clean | FR-015 |
| 10 | PDF vs screen for a selection | same figures | FR-016 |
| 11 | AI narrative on / off | uses only listed aggregates (captured prompt) / hidden | FR-003 |
| 12 | Rollback | previous version active < 1 min | SC-005 |
| 13 | Describe with token / revoked token | structure only / 401 | FR-019, SC-006 |
| 14 | Search workspace repo, AI prompts, describe output for marker row values and credentials | none | SC-006 |
