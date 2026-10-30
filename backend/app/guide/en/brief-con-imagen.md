# A mockup as the brief

## What it is for

Attaching an image —a mockup or an example screenshot— to ask for a report "like this one" without
describing the layout in words.

## Who can use it

Only the **Superuser**, and only when the configured model can read images (`AI_VISION`).

## How to

- In the chat composer press the clip 📎 (**Attach a brief**). You can also drag the image onto the text box or paste
  it with Ctrl+V. The thumbnail appears above the text and you can remove it before sending with
  the ✕.
- PNG, JPEG, WebP and GIF, up to 5 MB per image (`ATTACHMENTS_MAX_MB`) and 4 images waiting to be
  sent in the conversation (`ATTACHMENTS_MAX_PER_MESSAGE`).
- The first time you send an image the chat shows a notice and waits for your confirmation: the
  image goes to the configured AI provider, so use mockups or examples and never screenshots with
  customer data.
- Write your request together with the image, or send the image alone, and the agent writes the
  specs with the command you are in, exactly as with any other message.
- The images stay in the conversation: you can open them or remove them later. Removing an image
  changes neither the project nor the text of the message.

## Options

- The images are stored outside the project folder (`ATTACHMENTS_DIR`); they are not part of the
  project export, the Git mirror or the applied version, and they are deleted when the project is
  purged or 24 hours after an upload that never became a message.
- The image is a structure and labelling brief, never a data source: the agent does not read
  figures out of it and does not build tables from it.
- When the configured model cannot read images, the button is disabled and the chat explains it;
  the rest of the chat keeps working as usual.
