# Feature Specification: An image brief in the report chat

**Feature Branch**: `024-image-brief-chat`

**Created**: 2026-10-12

**Status**: Implemented (closed 2026-10-13, backend + frontend + e2e suites green; the
opt-in live brief eval of T027 has not been run)

**Input**: Owner, 2026-10-12: "does the chat can receive attached images as example, I mean I want a
report to look like the attached image" — and, on the same day, "the AI already can process images".

**Builds on**: 017 (agentic chat), 020 (projects), 021 (Spec Kit commands, BI-only scope, untrusted
data), 023 (guide), 022 (languages). Today the chat is text-only: `ChatMessage` is `role` + text,
the assistant API has no upload route and providers receive text only.

**Constitution**: **VIII (AI optional and private)** decides the hard part — an image is only a
*design reference*; the product MUST NOT send customer data to the AI, so a picture that looks like
real data needs an explicit decision from the person attaching it, and images never travel to a
provider otherwise. **IX (spec-driven)** means the image ends up as authored artifacts (spec, report
definition), never as an opaque instruction. No new stack component: images travel in the existing
provider payloads.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "Make the report look like this picture" (Priority: P1)

An implementer has a mockup of the report they need — a screenshot from another tool, a drawing, or
a photo of a whiteboard — and attaches it to the project chat with a short sentence ("like this,
sales by branch and month, with a target line"). The assistant reads the picture as a *design
brief*: which views (KPIs, trend, ranking, table), which dimensions and metrics, the layout and the
look it implies, and it turns that into the project's specs and declarative artifacts. From then on
the brief is just another input of the conversation: the person can correct it, and the artifacts —
not the picture — are what the project applies.

**Why this priority**: it is the whole point of the feature; without it the request is answered by
describing the layout in words, which is exactly what the owner is trying to avoid.

**Independent Test**: attach a mockup image to a new project conversation and send it with one
sentence; the assistant produces (or updates) a report spec whose views, dimensions and metrics
match the mockup, and the project validates.

**Acceptance Scenarios**:

1. **Given** a project conversation and a mockup image, **When** the person attaches it with a short
   request, **Then** the assistant answers with what it understood from the picture (views,
   dimensions, metrics, layout) and writes the corresponding spec files through the command in use.
2. **Given** the same image and a follow-up correction in words ("no, ranking by product, not by
   branch"), **When** the person sends it, **Then** the artifacts change accordingly and the image is
   still part of the conversation's context.
3. **Given** an image that is not a report mockup (a photo, a logo), **When** it is attached,
   **Then** the assistant says it cannot read a report brief from it and asks for what it needs,
   without inventing a report.

---

### User Story 2 - A model without vision never fails silently (Priority: P1)

The installation may be configured with a model that cannot see images (a local model, or a
text-only endpoint). The person attaching an image must be told, before or at send time, that this
model cannot read pictures, and the message must still be sent with the text part — never dropped,
never quietly ignored.

**Why this priority**: a silent drop is the worst outcome: the person believes the assistant saw the
picture and would trust the artifacts it invents from words alone.

**Independent Test**: configure a text-only provider, attach an image and send; the answer states
that the image was not read, the rest of the message is answered, and nothing is claimed about the
picture.

**Acceptance Scenarios**:

1. **Given** a text-only provider, **When** an image is attached, **Then** the composer warns before
   sending and the send still delivers the text.
2. **Given** a provider that supports images, **When** the image is too large or in an unsupported
   format, **Then** the rejection names the limit or the accepted formats, in the viewer's language.
3. **Given** any provider, **When** an image is attached with no text, **Then** the assistant asks
   what is wanted with it instead of guessing.

---

### User Story 3 - Customer data never leaves without a decision (Priority: P1)

An image can contain real figures. The product's rule is that the AI sees no detailed customer data,
so the app must be honest about what is being sent: a picture is treated as an *untrusted brief*, the
person is reminded that anything visible in it goes to the configured AI provider, and the audit
records that an image was used (count, size, hash — never its content).

**Why this priority**: Privacy is a product promise (constitution VIII); a chat that quietly
uploads screenshots breaks it.

**Independent Test**: attach an image and inspect what is stored, what is sent and what the audit
records; then run the same with AI disabled (nothing leaves, the composer is disabled as today).

**Acceptance Scenarios**:

1. **Given** an image attached for the first time in an installation, **When** it is sent, **Then**
   the person has seen a one-time notice that images go to the AI provider and can cancel.
2. **Given** a sent image, **When** the security overview and the audit log are read, **Then** they
   show the attachment (session, size, hash, provider) and never its content.
3. **Given** AI turned off, **When** the chat is opened, **Then** attaching images is unavailable
   exactly as chatting is.

---

### User Story 4 - The brief is part of the project's story (Priority: P2)

Months later the person wants to know why the report looks the way it does: the conversation shows
the attached image in its place in the history, with its own name, and it can be opened or removed
while the conversation still makes sense without it.

**Why this priority**: traceability is what makes the spec-driven promise real; it is not needed to
get value from the first three stories.

**Independent Test**: send an image, reopen the conversation after a restart, find the image in the
same message, then remove it and check the conversation remains readable and the artifacts are
untouched.

**Acceptance Scenarios**:

1. **Given** a conversation with an image, **When** it is reopened, **Then** the image is shown in
   the message it was sent with, with a name and a link to open it.
2. **Given** the same conversation, **When** the image is removed, **Then** the message text stays
   and the project's files are unchanged.
3. **Given** a project exported as a zip, **When** it is opened elsewhere, **Then** the project does
   not contain the chat's images (the brief belongs to the conversation, not to the project).

---

### Edge Cases

- An image larger than the limit, an animated image, a multi-page or vector file, a format the
  browser cannot render: refused with a message that names the limit or the accepted formats.
- Several images in one message, or an image plus a command (`/speckit-specify`): the images belong
  to that message's run and the command's rules still decide what may be written.
- A message with more than the allowed number of images, or a burst of messages while the assistant
  is working: the same back-pressure the chat has today.
- An image-only message, or a caption that contradicts the picture: the assistant asks or states the
  conflict instead of silently choosing one.
- A picture of real data (a dashboard screenshot) versus a mockup: the notice covers it, and the
  guide explains the difference.
- The provider changes between messages (a model with vision, then one without): the answer is always
  explicit about whether the picture was read.
- An upload that fails or is interrupted: no half message, no orphan file.
- The conversation is deleted, the user stops the run, or the installation is restored from a
  backup: attachments follow the conversation's life.
- An image whose text tries to give the assistant new instructions (a prompt hidden in the picture):
  it stays a brief, never an instruction, and the scope gate still applies.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A message MUST be able to carry one or more images together with its text, and the
  conversation MUST show them in the message they were sent with.
- **FR-002**: Images MUST be attached from the composer (choose from the device, or paste/drop) with
  a visible preview, a way to remove one before sending, and no image sent before the person sends
  the message.
- **FR-003**: The product MUST state the accepted formats and the per-image and per-message limits,
  and MUST reject anything outside them with a message in the viewer's language that names the limit.
- **FR-004**: When the configured model cannot read images, the person MUST be told before sending —
  the attach control states it and a send that carries images is refused with that reason — and the
  chat MUST keep working for text-only messages; the assistant MUST NOT answer as if it had seen the
  picture.
- **FR-005**: Images MUST reach the model as *untrusted brief data* — labelled as such, never as
  instructions — and the BI-only scope gate of the chat MUST apply to a message whose only content
  is an image.
- **FR-006**: On the first image a person sends in an installation, the app MUST show a one-time
  notice that the picture goes to the configured AI provider and that it should not contain customer
  data; the person MUST be able to cancel.
- **FR-007**: The audit trail and the security overview MUST record that an attachment was used
  (conversation, size, hash, provider, model) and MUST NOT record or log its content, name or bytes.
- **FR-008**: Attachment bytes MUST be stored outside the project folder and outside anything the
  project export or the workspace Git repository contains, and MUST be removed when their
  conversation is deleted.
- **FR-009**: The stored attachment MUST be retrievable by the viewer who owns the conversation (and
  by an administrator) through the app, and MUST NOT be reachable by anyone else, including through
  a share link.
- **FR-010**: Removing an attachment MUST leave the message text and the project's artifacts intact.
- **FR-011**: The chat MUST keep working exactly as today when no image is involved, and a project
  validation or apply MUST be unaffected by the presence of images in the conversation.
- **FR-012**: With AI disabled, attaching images MUST be unavailable, and the composer MUST explain
  that the assistant is off, as it does today for messages.
- **FR-013**: Every new user-visible string (limits, notices, errors, "not read") MUST exist in
  Spanish and English, and the notice MUST be understandable without technical knowledge.
- **FR-015**: The attach control MUST be a single icon (a clip) with the explanation in its
  accessible name and tooltip — no visible text — so the composer's toolbar stays quiet in the
  narrow docked panel.
- **FR-017**: The app's text size MUST follow the reference app's scale (13 px from 1024 px,
  13.5 px from 1536 px, percentages so a browser font-size preference still applies), with a larger
  base on phones so the 16 px form controls stay proportional.
- **FR-018**: Every "back" MUST be the same control — an arrow and "Volver" — and MUST NOT name the
  destination.
- **FR-019**: The project page's actions MUST be one compact tool strip, the words living in the
  tooltip and the accessible name, with the primary action standing out and the destructive one
  quiet; each control MUST keep a 44 px touch target under a finger.
- **FR-020**: A screen reached only by address MUST NOT keep an Administración tile (the workspace),
  and the guide MUST NOT list a tile the app no longer shows.
- **FR-021**: The footer MUST credit who publishes the installation (`FOOTER_CREDIT`) after the
  license, and lists MUST use the width they have (up to four columns).
- **FR-016**: The project page MUST offer a full-screen mode that hides the app chrome (sidebar,
  top bar, footer) and asks the browser for real full screen, leaving the explorer, the editor and
  the chat on the whole screen; leaving it (the same control or Esc) restores the chrome, and the
  mode MUST be a URL state so a reload keeps it and the back button leaves it.
- **FR-014**: The feature MUST be observable by the owner: which conversations used images, how many,
  how large, and which model read them — without exposing the images themselves.

### Key Entities

- **Attachment**: one image belonging to a message: conversation, message, media type, byte size,
  checksum, original name (for the viewer), stored location, who added it and when.
- **Conversation message**: today text (and tool payloads); gains zero or more attachments.
- **Brief**: what the assistant understood from an image — expressed as the project's artifacts
  (report spec, report definition: views, dimensions, metrics, layout), never as free-form memory.
- **Provider capability**: whether the configured model can read images, decided at send time and
  surfaced to the person.
- **Privacy notice**: the one-time record that a person has been told images go to the AI provider.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a mockup and one sentence, **at least 8 of 10** reference mockups produce a
  report spec whose views, dimensions and metrics match what the mockup shows, in **≤ 3** assistant
  rounds (measured with the opt-in live evaluation used for the guide).
- **SC-002**: With a text-only model, **100 %** of sends that carry an image state that the image was
  not read, and no artifact claims to follow it.
- **SC-003**: **Zero** image bytes, names or contents appear in logs, audit events or error
  messages (asserted by the secret/payload leak tests).
- **SC-004**: **Zero** attachments appear in a project export, the workspace Git repository or the
  applied version; deleting a conversation leaves no attachment behind.
- **SC-005**: An image within the limit is attached and sent in **under 2 seconds** on the reference
  machine, and the chat's existing behaviour (text, commands, tool payloads, readiness) shows no
  regression.
- **SC-006**: A first-time notice is shown once per person before their first image leaves the
  installation, and it is dismissible/cancellable (verified by test and by the guide's topics).

## Assumptions

- **The image is a design brief, not data.** Reading *values* out of a screenshot to build a dataset
  is explicitly out of scope (that is extraction work, and it would violate the "no customer data to
  the AI" rule); the feature only reads *intent and layout*.
- **Mechanism is the plan's decision.** Candidates for the plan to compare and choose: images sent
  as content parts in the provider payload (base64 in the existing JSON bodies, no new dependency),
  versus a reference the provider fetches (rejected for our providers, but recorded); capability
  detection either configured per installation or probed once and remembered.
- **Storage follows the conversation** on the installation's disk (as project files and the guide
  data already do), with size limits, a checksum and no transformation other than what the viewer
  needs; backups include it like the rest of the session data.
- **Limits chosen to start** (the plan may tune them with a reason): up to 4 images per message,
  5 MB each, PNG/JPEG/WebP (static GIF accepted as a single frame), no SVG and no PDF.
- **The models in play**: the installation's configured provider decides; the feature must be honest
  with the ones that cannot see, including local models.
- **Out of scope**: editing images, extracting tables or figures from screenshots, multi-page
  documents, video, audio, and any change to the report/PDF engine or to the project folder layout.

## Decisions taken while implementing (2026-10-12/13)

- **The brief stays layout-only — confirmed.** The picture is read for intent, structure and
  labelling (what blocks the report has, how they are grouped, what the person called them); the
  product never asks a model to extract values, tables or figures from it, and an image alone never
  produces a dataset. The labelled untrusted-data block, the BI-only scope gate (an image-only
  message runs through it like any other) and the "no invented report" rule of FR-004 are the
  enforced consequences of this decision.
- **The notice wording is accepted as shipped** (es: "Las imágenes se envían al proveedor de IA
  configurado. No adjuntes capturas con datos de clientes: usa bocetos o ejemplos."; en: "Images are
  sent to the configured AI provider. Do not attach screenshots with customer data: use mockups or
  examples."). It is shown once per account, before the first image is sent, and the user can
  cancel; the acknowledgement is `POST /api/me/attachments-notice` (see the contract).
