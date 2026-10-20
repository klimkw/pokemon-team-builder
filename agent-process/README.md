# Agent coding process

This folder explains how the Pokémon Team Builder was developed with an AI coding
assistant and how its main technical pieces work. It is intended to help the project
owner review the decisions and explain the application from browser to database.

- [Build journal](01-build-journal.md): chronological requirements, decisions,
  implementation increments, verification, and Git milestones.
- [PostgreSQL and Alembic walkthrough](02-postgres-and-alembic.md): what creates the
  database, what creates the tables, how requests use them, and how upgrades preserve data.
- [Workspace UX](06-workspace-ux.md): compact screens, catalog filters, secure profile
  updates and persistent unread alerts.
- [Admin scanner controls](05-admin-scanner-controls.md): the current same-app API-doc
  demonstration, live refresh, job status, admin setup, and reset boundaries.
- [Alerts and demo](04-alerts-and-demo.md): relevance rules, fixture stages, expected UI,
  isolation, and the future hosted walkthrough.
- [Python workflow with uv](03-python-with-uv.md): project metadata, the lockfile,
  virtual environments, Docker installation, and everyday development commands.

The initial Git commit already contained accounts, ingestion, team APIs, and their
tests. The early steps in the journal are reconstructed from HANDOFF.md, the working
README, and the retained source; they are not separate commits. Later milestones link
to the actual commits created during this conversation. Test counts describe the
stated milestone, rather than implying that every earlier run used the current suite.

The user chose the feature scope, reviewed proposed behavior and architecture, and
requested the uv workflow and this journal. The assistant implemented the agreed
increments, ran verification, reported results, and committed/pushed completed work.
This is a record of decisions and observable work, not a verbatim chat transcript.
Credentials, cookies, local environment files, and raw browser traces do not belong here.

Public hosting and the final one-page
submission README remain unfinished. See HANDOFF.md for the current continuation state.

For future increments, add the concrete requirement, the chosen behavior and reason,
the affected application layers, the tests actually run, the outcome, and the commit.
Keep the journal distinct from the concise final assignment README.
