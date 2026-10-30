# Contract — project assets

The published contract an author (person or external agent) works against. It is checked by
`bizview validate`, by the import path and by the editor, so all three must agree with this document.

## The folder

```text
projects/<slug>/
└── assets/
    ├── coins/
    │   ├── BTC.png
    │   ├── ETH.svg
    │   └── SOL.webp
    └── vendors/acme.png
```

- **Allowed extensions**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`. The bytes must match the
  extension.
- **Limits**: 300 KB per file, 25 MB for the whole `assets/` folder, ≤ 2000 files.
- **Paths**: relative to the project; no `..`, no absolute paths, no symlinks, same rules as every
  other project file.
- **Any other file type or location** is still refused with the existing message
  (`path_not_allowed`, which lists the allowed paths).

## Lookup by key

A row whose key is `BTC` resolves, in order:

1. `assets/<folder>/BTC.png` (exact case),
2. the same name with a different case (`btc.png`),
3. `BTC.svg`, `BTC.webp`, `BTC.jpg`, in that order, each with the same case rules,
4. the fallback from the image set.

Keys are normalised for lookup: `/` and spaces become `_`. A key that normalises to an empty string
uses the fallback.

## Serving

`GET /api/projects/{slug}/assets/{path}`

| Aspect | Value |
|---|---|
| Auth | same as `GET /api/projects/{slug}/file`: super user, project scope enforced by the existing resolver |
| Success | `200` with the sniffed content type and the file bytes |
| Caching | `ETag: "<sha256>"`, `Cache-Control: private, max-age=31536000, immutable` (content is versioned with the project) |
| Conditional | `If-None-Match` answering `304` with no body |
| Not found | `404 projects.file_not_found` |
| Out of scope | `422 path_outside_project` / `path_unsafe`, exactly as the file route |
| Listing | none: there is no directory index over `assets/` |

Share links and the report's TV mode read the same route in the same origin; nothing is served
publicly and no cache header ever becomes `public`.

## Editing and versioning

- The editor and the import write through the same path as any other project file, so every asset
  change is one `project_file_revision` row and appears in **Historial** like any other file.
- `assets/` travels in the zip export and is restored by the import.
- An older installation that does not know `assets/` refuses the files with the existing message and
  **still applies the project without them** — no silent drop, no half-imported project.

## Errors an author will meet

| Situation | Message key | Meaning |
|---|---|---|
| wrong extension or bytes | `projects.path_not_allowed` | the path list is shown |
| file over 300 KB | `assets.too_large` | names the file and the limit |
| folder over 25 MB | `assets.project_too_large` | names the current total and the limit |
| SVG with `<script>` or an external `href` | `assets.svg_refused` | names the element or attribute |
| two files differing only by case | `assets.case_duplicate` | validation **warning**, the exact case wins |
