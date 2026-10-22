# Demo walkthrough

Use the [hosted app](https://pokemon-team-builder-f4w6.onrender.com/) or follow the [local setup](development.md).

1. Register, sign in, and save a team containing Bulbasaur (catalog ID `1`). Reorder
   members, save, then sign out/in to check persistence.
2. Generate a counter preview, inspect its explanation and replay, then save it as a
   separate team. The original lineup is unchanged.
3. While signed in, open `/docs` on the **same origin**. Execute
   `POST /api/admin/demo/changes` with this body; choose a different attack value if
   the current value is already 60:

   ```json
   {"pokemon":[{"pokemon_id":1,"stats":{"attack":60}}]}
   ```

4. Hosted request mode returns the operation result; verify its `status`, not just
   HTTP 200. Local worker mode returns 202; watch `scanner` logs for completion.
   Refresh the catalog and alerts to see the changed stat and affected team.
5. Repeat the same payload to check that unchanged values do not duplicate history.
   Execute `POST /api/admin/demo/reset` to restore the demonstration changes.

**This is a shared sandbox:** enabled demo mutations accept ordinary signed-in users
and affect everyone's catalog. Full refresh and job inspection remain superuser-only;
the hosted live refresh runs through Actions. Reset refuses to overwrite conflicting
newer source data. An admin UI and isolated demo state are future improvements.

**What this proves:** the automated suites exercise the packaged application and
important persistence/failure paths. They do **not** guarantee production reliability,
validate live hosting credentials, establish load capacity, or replace restore testing.
The walkthrough is evidence of behavior, not a production-readiness claim.
