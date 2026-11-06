# Download the starter pack

## What it is for

It is the folder your AI needs to write a BizView project: the rules, the request, the spec, the
artifact skeletons and the schemas BizView validates against. You download it ready-made and hand it
over as it is.

## Who can use it

Only the **Superuser**, from Projects.

## How to

1. Open [Proyectos](app:/proyectos) and press **New project** (or **Download starter pack**
   when there is none yet).
2. Type the name. It also decides the identifier: lowercase letters, digits and dashes.
3. Choose the source when the project will read one. Its structure is added — never a credential or
   a row.
4. Choose the language of the documents and the kind of the first spec.
5. Press **Download starter pack**: it downloads `bizview-starter-<identifier>.zip`.

Inside the zip are `PROMPT.md` (the rules), `REQUEST.md` (the request you fill in), `project.yaml`,
`specs/001-…`, `integrations/…`, `reports/…` and `.bizview/`. `CONTENTS.md` explains every file and
`WHAT-BIZVIEW-DOES.md`, what happens on import and on apply.

## Options

- **Download general template**: the same pack with placeholders, no name and no source, to reuse
  or to distribute.
- The general template is also in the repository and in every release.
- On a machine with the CLI: `bizview init project "Sales"` writes the same pack.

## Common problems

- A name made only of symbols: no identifier can be formed and the notice names the field.
- The source does not answer: the zip downloads anyway, without its structure, and the notice says
  so.

## Related

- Write the request
- Hand it to your AI
- The five steps
