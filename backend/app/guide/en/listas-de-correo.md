# Mailing lists

## What it is for

A list is a named group of addresses: you write it once and use it in any send, scheduled sends
included.

## Who can use it

Anybody with an account sees their own lists and the shared ones. Only an **Administrator** or the
**Superuser** create **Shared** lists and role lists; every user creates their own.

## How to

1. Open **My lists** in the menu. Administrators also have **Mailing lists** inside
   **Administration**, with every list in the installation.
2. Press **New list**, write the **Name** and, if you want, the **Description (optional)**.
3. Choose the **Visibility**: **Personal** or **Shared** (only if you may share).
4. In **Members**, paste one address per line as `address,name`, or press **Import CSV** and pick a
   file with the `address,name` columns.
5. Press **Save list**. To change the members of an existing list, edit the text, press
   **Save members** and check the answer.

## Options

- **Pause** keeps a person in the list without sending them anything; **Resume** includes them
  again. Sends and scheduled sends always skip whoever is **Paused**.
- **Export CSV** downloads the list with the `address,name,paused` columns.
- A **By role (resolved at send time)** list has no fixed members: it reaches the users of the role
  you choose at the moment of the send.
- **Delete** asks for confirmation in the same card. Scheduled sends that use the list are paused
  with the reason; they are not deleted.
- A list holds up to 1,000 members. Addresses never leave Bizview: the history shows the masked
  address.
- In **Send by email** lists appear as buttons with their name and how many people they reach;
  picking them adds to the recipient counter.

## Common problems

- «A list with that name already exists»: the name must be unique among your lists.
- CSV lines that cannot be read are reported one by one; the rest is imported all the same.
- If a shared list shows no **Edit**, it belongs to somebody else: you may use it, not change it.

## Related

- Send by email
- Scheduled sends
- Roles and permissions
- [Open My lists](app:/mis-listas)
