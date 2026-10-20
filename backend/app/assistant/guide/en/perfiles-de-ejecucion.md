# Run profiles

## What it is for

A profile saves a run contract —how far the assistant may go in Auto mode, with which sources and
which limits— so a routine run does not have to be typed again.

## Who can use it

The super user only, like the whole Assistant.

## How it is done

1. Open Administration → AI → Run profiles.
2. Type the profile's name and its limits: applies per run, previews and minutes.
3. Press “New profile”.
4. In a conversation, set the mode to “Auto”: the contract offers the profile and fills the fields.
5. Confirm the contract with your password (and the two-step code when the installation is
   `internet`).

## Options

- A profile authorises nothing: every run still asks for your password.
- The run's goal is always your request; the profile never stores it.
- Deleting a profile is recorded in the audit trail.
- For Auto mode and its limits, see [The assistant chat](app:/admin/ia).
