# Re-import a project

## What it is for

Importing a project that is already in BizView. Every correction arrives as a new `.zip` of the same
project, and that zip becomes a revision of the project that already exists — not a separate
project — so its links, its grants, its dashboards and its history stay where they were.

## Who can use it

The **Superuser** only, and your password is asked for.

## How to

1. Fix the project folder and zip it again: `zip -r ventas.zip ventas/`.
2. Open [Open Projects](app:/proyectos) and press **Import project**.
3. Choose the `.zip`. BizView compares the archive with the revision the project has and shows the
   summary: files added, changed and removed, specs and ids added or removed, and the two import
   allowances.
4. Press **Import now**. The zip is stored as a new draft revision and the **project does not apply
   itself**: the dashboards keep showing the applied revision.
5. When you want to publish the changes, open the project and press **Apply project**.

A re-import replaces: what the zip does not carry leaves the draft, images included. Nothing is
merged. Revision 1 is compared with the zip; revision 2 with revision 1, and so on.

## Options

- **Import as a copy**: creates a separate project with its own slug and its own ids (`cripto`
  becomes `cripto-2`), for a variant that has to live apart.
- **Replace draft**: if you saved editor changes since the last import, BizView asks before
  overwriting them. What you saved stays in the file history; the draft is replaced.
- **Revisions**: on the project page, every import and every editor save is a revision, with its
  date, who did it, where it came from and how many files it changed. Each row can be downloaded as
  a zip with the same shape Export produces.
- Go back to the previous revision: writes the previous revision's files as a new revision and
  applies it. The audit log records the import, the apply and the revert.
- The last 20 revisions of each project are kept, plus the applied one and the previous one. The
  number is `PROJECT_REVISIONS_KEEP` in the installation.
- `bizview import ventas.zip` shows the mode (`created` or `reimported`) and the diff against the
  workspace folder where you run it, without uploading anything.

## Common problems

- I changed the project's slug in `project.yaml`: then it is another project and a new one is
  created; the previous one is untouched. The slug is the project's identity.
- The summary says files will be removed: the zip does not carry them. Zip the whole folder
  again, not only what changed.
- Apply fails after importing: the revision is a draft and the project has problems; open it to
  see them. Nothing of the draft reaches the dashboards until it is applied.
- An image does not come back on a revert: images are stored by hash, not by content, so one
  that left the folder cannot be recovered; BizView says so when it reverts.
