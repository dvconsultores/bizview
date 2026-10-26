# Contract: applying a deterministic fix

## Validation payload (read)

`POST /api/projects/{slug}/validate` (and every endpoint returning `validation`) publishes each
problem with:

```json
{
  "entry": "reports/panorama-cripto",
  "code": "unjoined_sets",
  "message": "Conjuntos sin unión: altseason",
  "file": "reports/panorama-cripto/report.yaml",
  "path": "/uses",
  "line": 12,
  "project": "coinmarketcap",
  "fix": "declara joins: [{left: assets.snapshot_at, right: altseason.snapshot_at}] para unirlos",
  "fix_data": {"file": "reports/panorama-cripto/report.yaml", "json_path": "/joins",
               "op": "append",
               "value": {"left": "assets.snapshot_at", "right": "altseason.snapshot_at",
                          "type": "left"}},
  "problem_id": "unjoined_sets:reports/panorama-cripto/report.yaml:/uses"
}
```

`fix_data` and `problem_id` are absent when the problem has no deterministic correction — the
interface then shows no button.

## Apply (write)

```http
POST /api/projects/{slug}/fix        (super user, recent re-auth)
{"fixes": [{"file": "…", "json_path": "/joins", "op": "append",
            "value": {…}, "base_sha256": "…"}]}
200 {"results": [{"file": "…", "op": "append", "json_path": "/joins",
                  "revision_id": 41, "diff": "- …\n+ …"}],
     "validation": {…}, "readiness": {…}, "project": {…}}
409 {"error": {"code": "fix_stale",
               "message": "El archivo cambió desde la validación; vuelve a comprobar los problemas.",
               "errors": []}}
409 {"error": {"code": "fix_not_applicable",
               "message": "Ese arreglo ya no se puede aplicar: <detalle>. Vuelve a comprobar los problemas."}}
422 {"error": {"code": "validation", …}}     # malformed body
```

**Rules**

1. Each fix is applied to the **current** file, re-read inside the request; `base_sha256` (sent by
   the client, from the validation it saw) must match, else `fix_stale` and **nothing is written**.
2. Operations are JSON Pointer based: `set` creates parents, `append` appends to (or creates) a
   list, `insert` inserts at `value.index`. A pointer whose parent does not exist is
   `fix_not_applicable`.
3. Writes go through the same path as a manual edit (`fs.apply_ops`): a revision per file, the
   project row updated, audited as `project_fix_applied` with the operation, the file and the
   problem code.
4. One validation runs at the end for the whole batch; the response carries it so the panel updates
   without a second round trip.
5. Applying several fixes to the same file is allowed: they are applied in order to the text built
   so far, and committed once.
6. The endpoint works with AI off — it never touches the provider.

## Assistant tool

`apply_fix(problem_id)` — same rules, resolved server-side against the current validation of the
conversation's project; returns the applied operation, the diff and the new validation. Offered only
when the conversation has a project. The command prompt tells the model to prefer it over
`edit_draft` for problems that publish a `fix_data`.
