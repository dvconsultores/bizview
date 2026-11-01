# Contract — version and naming

## The value

`VERSION` at the repository root holds one SemVer value (`0.2.0` for this release). It is the only
place a human edits the number.

## Consumers and how they get it

| Consumer | Mechanism | Checked by |
|---|---|---|
| Backend runtime (`/api/health`, `/api/config`, footer) | `app/config.py::_file_version` reads `VERSION` | `07-version.sh` (file), and the health half when a backend answers |
| Images (`deploy.sh`, Dockerfiles) | `VERSION` → `--build-arg BIZVIEW_VERSION` → `ENV` + OCI label | `07-version.sh` (file only; the label is derived, not copied) |
| Backend package (`backend/pyproject.toml`) | a copy | `07-version.sh` compares |
| Frontend package (`frontend/package.json`) | a copy | `07-version.sh` compares |
| CLI package (`cli/pyproject.toml`) | a copy | `07-version.sh` compares |
| CLI `bizview version` (`cli/bizview_cli/__init__.py::__version__`) | a copy, because the package is installed standalone | `07-version.sh` compares |

## The gate's contract

```
sh scripts/gates/07-version.sh
  prints each copy and its value
  exit 0  when every copy equals VERSION and (if a backend answers) /api/health agrees
  exit 1  listing the copies that disagree, with the value found
  exit 0  with a stated reason when no backend is reachable (the file half still ran)
```

## Naming

- The product name default is `Bizview` (`PRODUCT_NAME`), in the backend settings and in the
  frontend's branding fallback.
- `AI Powered` MUST NOT appear in the repository's own documents, strings, titles, manifests or
  package descriptions. The check greps the tree; an installation's rendered screens are out of
  scope because `PRODUCT_NAME` is a setting.
- The footer format stays `© YEAR <product> · Version <version> · AGPL-3.0 · GlobalDV`, with
  `<product>` and `<version>` from configuration.
