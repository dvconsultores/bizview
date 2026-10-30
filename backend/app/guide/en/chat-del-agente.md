# Agent chat

## What it is for

The chat is where you work with the BI agent: you describe a report or an integration and it
writes the project's specs and files with the Spec Kit commands.

## Who can use it

Only the **Superuser**, when AI is configured in the installation.

## How to

1. Press **Open assistant** in the header. On a computer a panel opens on the right: **Expand**
   makes it bigger and **Open in full page** takes the whole screen. Each project's editor also
   has a **Chat** panel.
2. Type your request. In the first message of a new conversation, choose or create its project.
3. Type `/` to see the list of commands and pick one with the arrows and Enter.
4. While it works the indicator says **Working**; when done, **Ready**. **Stop** halts the work in
   progress without losing what is done.

## Options

- **New conversation**, **Conversations** and **Search conversations** organize the chats; each
  one can be renamed or archived.
- **Agent map** shows live which tools the agent uses.
- **Working notes** keeps the goal, the decisions and the next step; **Readiness** says what is
  missing to apply.
- Each command shows as a card with its status and the files it changed; a command waiting for
  your answer is closed with **Finish**.
- **Preview** and **Preview PDF** show the result before applying.

## Common problems

- The conversation answers "The stored conversation cannot be sent to the provider again": a tool
  result is missing the call that asked for it. Press **Repair conversation** in the notice (or in
  the **More conversation actions** menu of the header): the product pairs the results again and
  tells you how many it paired and how many it dropped. Nothing you wrote is lost, and the AI is
  not needed to repair it.
- If the notice shows up in an old conversation after upgrading, the upgrade already did that
  repair once; the button is for one specific conversation.
