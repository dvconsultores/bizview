## Bizview vibe reporting — read before specifying

This workspace holds BI **projects** (`projects/<slug>/`). Every source, integration, report and
distribution is a Spec Kit spec; the Bizview engine refuses anything without a complete,
approved spec.

1. **Decide the kind**: `fuente`, `integracion`, `reporte`, or `distribucion`. Ask the user if it
   is unclear. A report that needs missing data first requires a `fuente` or `integracion` spec;
   a distribution requires an existing report id.
2. **Work inside the current project folder** `projects/<slug>/`. The new folder is
   `specs/<NNN>-<short-name>` where `NNN` is the highest existing number in this project + 1,
   formatted with three digits (001, 002, …). Short names use lowercase letters, digits and
   hyphens. Set `SPECIFY_FEATURE_DIRECTORY` to that path.
3. **Write spec.md** from the Bizview spec template. Keep the `**Tipo**:` line matching the kind
   (or `**Type**:` in English) and only the section for that kind.
4. **Status** stays `Draft` until the user approves it (then `Approved`; after implementation
   `Implemented`).
5. **Describe sources with `bizview describe`**: structure and catalogue names only; never
   credentials, tokens or row values.
6. **Define report metrics exactly**: id, label, exact definition, format and better direction.
