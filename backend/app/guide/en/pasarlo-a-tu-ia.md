# Hand it to your AI

## What it is for

Any AI can write the project: ChatGPT, Claude, Gemini, DeepSeek, Copilot or a coding tool with the
folder open. Bizview needs no key and no connection: your AI works outside and you bring the result
in.

## Who can use it

Only the **Superuser**, with their own access to whichever AI they prefer.

## How to

1. Open a new conversation.
2. Paste all of `PROMPT.md`.
3. Paste the filled-in `REQUEST.md`.
4. When there is a source, paste `sources/<source>/structure.md` too.
5. Ask: "Write the project following the rules and give me one zip with the files at the root".
6. Download the zip and keep it zipped.

With a coding tool it is shorter: open the pack's folder and ask it to read `PROMPT.md` and
`REQUEST.md` and write the project. `CLAUDE.md` and `AGENTS.md` carry the same text.

## Options

- If the AI cannot return a zip, ask for the files one by one and assemble them with those paths; the
  zip is convenient, not required.
- By hand: the files are YAML and SQL; `CONTENTS.md` says what each one is.

## Common problems

- Answers with sample data inside the SQL: ask it to remove the rows; the project describes the read.
- A zip with one folder wrapping everything: Bizview strips it when it is a single one, but ask for
  the files at the root.
- The AI invents tables: give it the structure again and ask it to use only what appears there.

## Related

- Write the request
- Validate before importing
- Fix the problems
