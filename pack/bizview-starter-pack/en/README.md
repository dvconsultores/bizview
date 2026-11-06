# {{name}} — BizView starter pack

1. Fill in `REQUEST.md` (5 minutes).
2. Give this folder to your AI, or paste `PROMPT.md` + `REQUEST.md` (and `sources/…/structure.md` when
   there is one) into the chat, and ask for the project.
3. Import the zip it returns into BizView: **Projects → Import project**.

```
REQUEST.md      what you want, in your own words
PROMPT.md       the rules for your AI (the same for Claude Code, Codex or ChatGPT)
project.yaml    project name, slug and date
specs/001-…     the spec, the plan and the tasks
integrations/   the read of the source (only when there is an integration)
reports/        the dashboard
.bizview/       the schemas BizView validates against
```

File by file: `CONTENTS.md`. What happens on import and on apply: `WHAT-BIZVIEW-DOES.md`. If you
prefer another tool, `CLAUDE.md` and `AGENTS.md` carry the same text as `PROMPT.md`.
