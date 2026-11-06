# From source to distribution

## What it is for

It is the full path for a new dashboard with data from an operational system, from the source to
the email in people's inboxes.

## Who can use it

Only the **Superuser**.

## How to

1. Register and test the source in [Open Data sources](app:/admin/fuentes).
2. Create a project in [Open Projects](app:/proyectos) and write its specs in the editor (or
   import them from the repository you wrote them in).
3. **Source** spec: describes the source; it is met when the source exists and its test passes.
4. **Integration** spec: which data to load and how often.
5. **Report** spec: the dashboard's metrics, dimensions and views.
6. **Distribution** spec (optional): the scheduled sends by role.
7. When the editor says **Ready to apply**, press **Apply project**.
8. Check the first load in [Open Integrations](app:/admin/integraciones) (you can use
   **Run now**).
9. Give access to the dashboard in each user's **Dashboard access**
   ([Open Users](app:/admin/usuarios)).
10. Share it with **Share** or **Send by email** if needed.

## Related

- Define an integration
- Define a report
- Distributions
