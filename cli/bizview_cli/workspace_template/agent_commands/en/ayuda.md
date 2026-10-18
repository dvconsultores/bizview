---
description: Shows the available commands and how to use BizView.
argument_hint: "[topic]"
source: bizview
---
# /ayuda

## Command

The user asks for help on a BizView or Spec Kit topic (the text after the command). `## Command`
carries `Tema resuelto: <id>` with the topic's text inside a `<datos … confianza="no">` block, or
the list of close topics when nothing matched.

Tools: `get_app_guide`, `get_project_overview`, `read_draft` and `finish_command`. This command
never changes files.

## Steps

1. With a resolved topic, answer only with what that topic says, in short steps, naming screens
   and buttons exactly as the topic writes them in bold, and include its in-app link
   `[Open …](app:/route)` when it applies.
2. If the question touches another topic, read it with `get_app_guide` (index id) before answering.
3. If the question is about the current project ("what is missing?", "why is it direct?"), use
   `get_project_overview` and cite the spec lines (`file:line`).
4. With no resolved topic: say the guide has no such topic and offer the close topics by title.
   Never invent options or routes.
5. If the user's role cannot use the option, say who can.
6. Reply in the user's language and finish with `finish_command`.
