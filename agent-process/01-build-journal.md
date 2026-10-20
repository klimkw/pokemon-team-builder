# Build journal

The application was developed in reviewable increments so the owner could understand
and present each layer. The case study asks for a responsive Pokémon catalog, multiple
persistent ordered teams, an explainable equal-sized counter team, observed data-change
alerts, a deterministic demonstration, a public frontend, and a one-page technical README.

## Requirements and scope

The case study PDF was treated as the assignment reference. The owner asked for
walkthroughs before feature implementation, small tested milestones, and frequent
GitHub commits. The implementation therefore separated account setup, team data/API,
ingestion, team UI, counter generation, and scanner/history instead of building all
remaining features in one pass. The remaining alert and demo work has been discussed,
but is not represented as completed functionality.

## Initial backend and account baseline

The retained handoff describes the work that existed before the first Git commit.
Python/FastAPI was selected for the API, async SQLAlchemy with PostgreSQL for storage,
and React/TypeScript/Vite for the frontend. Nginx serves the compiled frontend and
proxies `/api` to FastAPI, allowing browser requests to use a single origin.

Accounts use FastAPI Users rather than a custom authentication implementation. The
library's internal email field stores a normalized lowercase username; no email,
recovery, or OAuth routes are exposed. Passwords use Argon2. Login creates an opaque
seven-day session in an HttpOnly SameSite=Lax cookie. The browser stores no token in
local storage. The library strategy stores raw session tokens in the database, a
recorded trade-off; expiry cleanup and login rate limiting remain future work.

The account UI handles registration, login, session restoration, connection failures,
and logout. Registration returns to login instead of implicitly signing in. Tests
exercise rejected credentials, independent sessions, cookie attributes, and replay
rejection after logout. Same-origin checks protect browser mutation requests.

## Team schema and API

The data model separates Pokémon, teams, and ordered team memberships. Pokémon retain
their upstream IDs. Teams have UUIDs and an account owner; membership position is part
of the key and is constrained to slots zero through five. PostgreSQL JSONB stores
structured types and stats. Deleting a team removes memberships, never Pokémon.

The owner agreed that empty teams and duplicate Pokémon are valid. A save submits
a name and the complete ordered ID array. PUT validates all IDs and locks the parent
team row, replaces its memberships, and commits atomically. The last successful save
wins. Tests include an injected failure during replacement to prove the name and old
memberships survive a rollback. Ownership checks are enforced by the API on every team
operation, rather than trusting an owner ID supplied by the browser.

Alembic revisions 0001 and 0002 establish account tables and then catalog/team tables.
The current Python models describe the expected schema; migrations describe the
ordered changes needed to get a database there. Tests compare migrations with the
models and exercise upgrade/downgrade and verified adoption of an older account schema.

## Catalog ingestion

The importer discovers the complete paginated PokéAPI catalog before writing. It
checks expected resource URLs, repeated pagination, and reported count consistency.
It fetches up to five details concurrently, with bounded retries for transient errors.
Validation requires the expected ID, usable name, one or two types, all six stats, and
a valid or missing sprite URL. Fields the application does not use are ignored.

Database writes are sequential per-record transactions. Initial inserts establish a
baseline, repeats are unchanged, and existing records update in place. Failed details
preserve old data. Records absent from discovery are reported without being deleted.
A sample import is explicitly marked partial scope. Importing never runs inside the
API request process; it is a backend command shared with the later scanner.

## Docker verification and the first Git commit

The project remained in its Windows-mounted checkout. Docker installed dependencies
inside images, avoiding reuse of Windows node_modules or a Windows Python environment
from Linux. The Docker daemon was reachable after approved access outside the sandbox.

An initial Docker build failed while reading metadata for backend/.pytest_cache,
even though the folder was ignored by Docker. A temporary source copy under /tmp,
excluding host caches and environments, allowed the build. Source files were not moved,
development volumes were not reset, and host permissions were not changed.

The isolated test stack used project pokemon-team-builder-tests, PostgreSQL pokemon_test
in tmpfs, and ports separate from development. Backend fixtures used random per-test
schemas. At this milestone, 51 PostgreSQL tests and the Chromium account E2E passed;
seven frontend component checks and the build had also been verified in the earlier
handoff. The Docker run closed the previous Nginx/orchestration verification gap.

The owner created a private GitHub repository after the available connector could not
create one. Git was initialized locally, source was staged explicitly, and local secrets,
agent settings, environments, caches, reports, and screenshots were excluded. Windows
Git used its existing credential manager for pushes; no authentication files were copied.

Commit: [5a79c3f Establish tested baseline](https://github.com/klimkw/pokemon-team-builder/commit/5a79c3f).

## Team builder UI

The owner reviewed the catalog-beside-editor design before implementation. Catalog
cards show name, types, sprite, and all six base stats, with search, a type filter, and
24-record pagination. The editor supports selecting/creating multiple teams, names,
six ordered slots, add/remove, and accessible up/down controls.

Drafts live in React memory until Save team. Failures retain edits. Team switching,
starting a new draft, and sign-out ask before discarding changes; refresh/close uses
the browser warning. Saving is explicit rather than autosaved, and mutation controls
are locked while a request is in flight. Missing or broken sprites have a placeholder.

The mobile sections stack. Screenshot review showed the editor could be far below the
catalog, so jump links were added. A disposable 25-record synthetic catalog fixture was
added for browser verification; it is guarded against non-test databases and does not
populate development. At this milestone, 51 PostgreSQL tests, 13 component tests, two
Chromium E2E tests, TypeScript, and production build passed.

Commit: [41bc33a Add team builder UI](https://github.com/klimkw/pokemon-team-builder/commit/41bc33a).

## Persistent development environment

The owner asked to click through the complete application. A missing local .env was
created with a generated password, remaining ignored. The development database, API,
and frontend were started at localhost:8080. The database was initially empty, so the
full importer inserted 1,351 discovered Pokémon with zero failures. The catalog API
returned actual names, types, stats, and sprite URLs.

Development data uses the persistent pokemon-team-builder_postgres_data volume. The
frontend is a production build served locally, without hot reload. Test data remains
in the separate disposable project. Development services were intentionally left running.

Commit: [e8a5178 Record development setup](https://github.com/klimkw/pokemon-team-builder/commit/e8a5178).

## Counter team definition and implementation

The owner and assistant discussed what optimal should mean before coding. The approved
priority order is: maximize safe assigned matchups, then total matchup strength, then
relative stats. Safe means outgoing type effectiveness at least 2× and the opponent's
best assumed return effectiveness at most 1×. Matchup strength is outgoing minus incoming.

The model assumes each side can attack using either own type and takes its best choice
against the defender's full typing. Both defender-type multipliers multiply; the
attacker's two types are alternatives. Immunities stay zero. Moves, abilities, items,
levels, switching, and battle simulation are outside this model. All local entries,
including special forms and legendary Pokémon, are eligible.

A bitmask dynamic program finds the exact best distinct-candidate assignment under
these additive priorities, for up to six opponents. Stats compare attack potential,
HP/defense durability, and speed using bounded relative scores. Stable ordered-ID
breaking makes tied results deterministic. Exhaustive small-catalog assignments test
the optimizer independently of its dynamic-programming strategy.

View optimal counter team previews the current editor lineup, including unsaved member
edits. It explains safe/risky pairings, both effectiveness directions, and optional
base-stat/method details. Save as new team creates a separate resource; closing or
saving never overwrites the original draft. Native dialog behavior, mobile width,
retry, duplicate-save prevention, and source preservation are tested.

A test initially expected Ground's ½× return attack where Rock was the stronger 1×
option. The implementation was correct; the expectation was corrected and strengthened
to assert the chosen return type. The completed increment passed 69 PostgreSQL tests,
18 component tests, three browser tests, TypeScript, and build checks. A read-only
six-member generation across all 1,351 development entries took approximately 0.35
seconds in this environment, a sample measurement rather than a latency guarantee.

Commit: [d8a9a9a Add explained counter generation](https://github.com/klimkw/pokemon-team-builder/commit/d8a9a9a).

## Scanner and observed change history

The owner chose shared backend code with a separate scanner process, rather than
scheduling inside the API or creating a separate repository. The scanner uses only
PokéAPI, checking Pokémon details and standard type relationships. Pokémon Database
was used to understand the chart, not as a second scraping source.

CATALOG_SCAN_INTERVAL_HOURS defaults to 24. The service scans on startup and waits that
interval after completion. CHANGE_ALERT_WINDOW_DAYS defaults to 7 and is available for
the upcoming alert query. Both require positive integers. The window will filter alerts;
it does not delete history or determine scan frequency.

Migration 0003 adds scan audit records, append-only catalog changes, and a singleton
active type chart seeded from the previously observed snapshot. The counter API reads
the database chart per request, so completed type updates need no API restart.

Changed Pokémon and their field-level history commit together. All 18 type rows are
validated before one transaction replaces the chart and appends changed-row history.
Initial Pokémon inserts produce no change entries; repeated identical scans do not
duplicate history. The observation timestamp does not claim when upstream edits occurred.

Manual imports and scheduled runs share a PostgreSQL advisory lock. All scan writes
stay on the physical connection holding it. Lost connections cannot silently resume
writes without a lock. Overlap attempts are audited as skipped. Graceful shutdown
cancels active work; the next lock holder marks abandoned running audits interrupted.

The completed scanner passed 93 PostgreSQL tests, 84 SQLite tests with nine PostgreSQL
skips, and all three browser regressions. The first live service scan found all 1,351
Pokémon and 18 type rows unchanged, with zero failures/history events. Existing accounts
and teams were preserved, and the scanner was left waiting for its next interval.

Commit: [ab7280a Add scanner and history](https://github.com/klimkw/pokemon-team-builder/commit/ab7280a).

## Python tooling and process documentation

The owner requested uv to demonstrate familiarity with modern Python tooling, plus a
folder explaining the development process. The backend was migrated from pip
requirements files to pyproject.toml, a committed uv.lock, a Python 3.12 declaration,
and a development dependency group. Docker builds use a pinned official uv binary and
locked dependency synchronization. Runtime images omit test-only packages.

This increment also adds the PostgreSQL/Alembic and uv walkthroughs in this folder.
The migration preserved all 43 previously installed package versions. The new test
environment passed 93 PostgreSQL tests, 84 SQLite tests with nine skips, and all three
browser regressions. Inspection confirmed the image-local interpreter and exclusion
of test-only dependencies from the runtime. The lock consistency check passed offline.
A command review caught that the source application needs module-based test invocation;
the documented command is uv run --locked python -m pytest, preserving the earlier
Python-module test behavior rather than introducing packaging changes.

## Backend responsibility separation

The owner asked whether separating database code from backend service code would
make maintenance easier, then approved the refactor. Database connection/session
setup and SQLAlchemy models now live in `app/db/`; routes and authentication in
`app/api/`; reusable scoring and synchronization code in `app/services/`; import
and scanner orchestration in `app/jobs/`. Shared validation contracts live in
`app/schemas/`, so jobs and services can use them without importing HTTP routes.

Imports, Alembic metadata registration, test fixtures, scanner startup, and current
walkthrough paths were updated together. The bundled type chart remains in app/data,
with its loader adjusted for the deeper service module path. Thin legacy CLI entry
points retain existing import/scan commands and their exit codes. Historical
migration revisions and database schema were left intact. This is code organization;
PostgreSQL already runs as a separate service, and both Python processes continue
to use the same database layer.

Verification passed: 93 PostgreSQL tests, 84 SQLite tests with nine skips, 18 frontend
component tests, and three Chromium flows. Alembic check found no new upgrade
operations. After updating the development API and scanner images, the startup scan
succeeded with all 1,351 Pokémon and 18 type rows unchanged. The existing two teams,
one account, zero catalog-change rows, and migration head 0003 were preserved.
This increment is committed as “Separate backend API, database, services and jobs”.

## Recent-change alerts and deterministic demo

The owner approved alerts and the deterministic demonstration after the scanner and
history foundation. Alerts are computed from the user's current saved memberships
and recent append-only changes; they are not copied into per-user notification rows.
The response includes grouped affected slots/teams, field differences and observation
timestamps. Type changes match both offensive and defensive relevance under the
existing model. The UI refreshes after a successful team change and supports explicit
refresh, loading, empty/error states, pagination and scanner freshness context without
replacing drafts. No dismissal/unread workflow was introduced.

The offline demonstration uses the actual PokéAPI client's normalization and scanner,
with fixture HTTP responses. It runs in a separate memory-backed PostgreSQL Compose
stack. Baseline records three Pokémon and no change events; the changed fixtures
alter Bulbasaur's Attack and Fire-versus-Grass effectiveness. The repeat stage proves
that identical inputs do not add history. The CLI rejects non-demo database targets,
and a distinct session cookie lets the owner stay logged into both local apps.
The UI labels the demo's changes as fictional.

The owner then asked how the demo should work on free public hosting. The recommended
future adaptation is a browser-guided scenario with temporary data isolated per visitor,
reusing the deployed API/database server. That public control flow is not implemented
in this increment; the offline scenario is the reusable foundation. The full scanner
remains a separate job, independent from the small on-demand fixture demonstration.

Verification passed 106 PostgreSQL tests, 96 SQLite tests with ten skips, 22 component
tests, and the three ordinary Chromium flows. The separate Docker demo ran baseline,
change, repeat and its dedicated real-browser flow. The initial browser selector
ambiguously matched two sign-in buttons; narrowing it to the form submit button fixed
the test without application changes. The walkthrough in 04-alerts-and-demo.md explains
the commands, expected evidence and isolation boundaries.
The milestone is committed as “Add saved-team change alerts and isolated deterministic demo”.

## Same-app API-doc scanner controls

The owner asked to apply changes and run full source refreshes through API docs, then
clarified that the existing app should be used instead of a separate demo page. This
supersedes the earlier plan for a browser-controlled isolated demo. The existing full
catalog and sprites remain the normal user experience. The older isolated scenario
is retained for historical/offline testing, and its running stack was stopped.

Admin-only endpoints now queue bounded stat/type changes, reset the active scenario,
request a full live refresh, and report job status. Migration 0004 adds a durable job
queue and a snapshot of only the demo-owned fields. The separate scanner worker polls
the queue and retains scheduled scans. Shared advisory locks serialize operations;
restart and cancellation expose interrupted jobs instead of silently replaying them.

Manual inputs pass through normal scanner synchronization and tagged history. Repeat
inputs produce no additional history. Reset restores captured fields and removes only
tagged demo events, preserving teams, accounts, unrelated data and normal history.
It refuses to overwrite values changed by a later scan. A live refresh records source
differences and reversals as ordinary history. The UI labels manually generated events.

The same frontend now proxies docs/OpenAPI. Existing cookies authorize the docs after
normal app login; a local CLI explicitly grants/revokes admin access and registration
never grants it. Demo writes require a separate configuration flag in both processes.
The owner account was granted admin access for local review, without adding a new
account or changing its password. The implementation is committed as “Add same-app
admin scanner controls and durable refresh jobs”.

Verification passed 114 PostgreSQL tests, 99 SQLite tests with 15 skips, 22 component
tests and four regular Chromium flows. The new browser test proves real API-to-worker
execution, same-app alerts, idempotence and safe reset; the isolated test stack is
cleaned up. The deployed queued live refresh also succeeded with 1,351 Pokémon and
all 18 type rows unchanged, zero failures, and existing accounts/teams preserved.
No fictional changes are active in the development app. See 05-admin-scanner-controls.md
for review steps and operational details.

## Compact UI, profile and persistent unread alerts

The owner requested less copy, consistent account-card alignment, selectable catalog
page size, multiple type/stat filters, header sign-out/profile/alerts actions and an
unread badge. The workspace retains the existing palette, with short labels and an
initially closed native alerts drawer. Filters offer any/all type matching and all
six inclusive stat ranges; size/filter changes return to page one.

Profile preserves the mounted builder draft, exposes saved teams for editing/deletion,
and supports username/password changes with current-password verification. Password
changes revoke all sessions atomically. Migration 0005 adds per-user alert reads so
badges persist across sessions and only displayed events become read. Polling/focus
refresh keeps counts current without a realtime channel.

Verification passed 120 PostgreSQL tests, 105 SQLite tests with 15 skips, 22 component
tests and five normal browser flows. Card dimensions, header placement, filter behavior,
profile/account actions, mobile layout and unread persistence were checked in Chromium.
The old saved-copy assertion was updated; stale profile navigation after sign-out was
fixed. Deployment exposed the scanner's startup refresh interfering with an active
manual scenario; its two reversals were restored and its generated events removed,
retaining the original scenario/history. Restart scheduling now respects the last full
live scan, with an additional regression test. See 06-workspace-ux.md for details.
This increment is committed as “Refine workspace UX with filters, profiles and unread alerts”.

## Catalog comparison refinements

The owner requested default index sorting plus all six stat directions, paired range
sliders, consistent type chips and visible selected-member stats. Sorting now occurs
before pagination with deterministic index ties. Global catalog stat maxima provide
stable slider domains; native minimum/maximum handles share a track and support both
keyboard and pointer interaction. Shared type/stat components keep the three surfaces
consistent, and selected catalog entries show a count while team slots expose six stats.

Tests cover numeric ordering, filtering, pagination and slider maxima; Chromium checks
requests, pointer/keyboard controls, matching computed styles, selection counts and
mobile layout. Visual review found a duplicated count label positioned outside a team
slot; it was removed and a regression assertion added. Final checks passed 127
PostgreSQL tests, 112 SQLite tests with 15 skips, 23 components and six regular browser
flows. See 07-catalog-comparison.md. The milestone is committed as “Add stat sorting,
range sliders and selected-team comparisons”.

## Remaining assignment work

Public deployment and the final one-page technical README remain. Known Vitest
development-tool advisories, session cleanup, and login rate limiting are also
recorded follow-ups. A separate public demo page is no longer requested.
