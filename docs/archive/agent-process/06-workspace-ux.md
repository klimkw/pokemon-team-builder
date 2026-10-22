# Compact workspace, profile and unread alerts

The owner requested less copy, consistent alignment, page-size controls, richer filters,
header account actions, an editable profile, and a closed alerts tray with an unread badge.

The existing paper/olive/red palette is retained. Marketing paragraphs, decorative
captions and repeated save instructions were removed. Sign-in and registration now
share the same fields, help-row spacing and card frame. Header actions contain the
alerts icon, profile icon and sign-out button. The builder keeps its state while the
Profile page is open, so visiting it does not discard a team draft.

## Catalog controls

Page sizes are 12, 24, 48 and 96. Type checkboxes support **any** selected type or **all**
selected types. Min/max filters cover all six base stats, inclusive of their boundaries.
Search, types and stat ranges combine; filter/page-size changes return to page one.
The Filters section is collapsed by default, and Clear filters resets types and ranges
without changing the selected page size. Requests retain debouncing and cancellation.

The GET /api/pokemon endpoint supports repeated `types=fire&types=water`, `type_match`,
and stat parameters such as `attack_min` and `attack_max`. The existing `type` query
parameter remains compatible. Validation rejects unknown types, out-of-bounds values,
and reversed ranges. Database filtering happens before counting and pagination; the
same JSON-index expressions work in PostgreSQL and the SQLite test fallback.

## Profile

The header profile button opens the Profile view at #profile. Account controls edit
username/password and require the current password. Usernames keep the registration
rules and normalize to lowercase. Duplicate usernames fail without changing data.
User ID and team ownership stay fixed across a rename. A password change revokes all
existing sessions, including the current one, and returns the UI to sign-in. New
passwords follow the same 8–128 character policy. No privilege fields are accepted.

PATCH /api/profile authenticates the owner, enforces same-origin requests, locks and
refreshes the account row, verifies the current hash, and commits credential changes
and token revocation together. The profile team list shows current saved memberships;
Edit opens that team in the builder, while Delete uses confirmation and the same owned
team API. Existing unsaved-team confirmation rules still apply when replacing a draft.

## Alerts

The header bell shows a red count only when relevant unread changes exist. The tray is
closed by default and uses a native modal dialog with a close button and Escape support.
Opening it marks the displayed page's events as read after a successful acknowledgement.
Additional pages remain unread until displayed. Reading does not remove change history.

Migration 0005 adds alert_reads keyed by user and change IDs, with cascading deletion
when an account/event is removed. GET /api/alerts reports unread_total and each event's
is_read flag. POST /api/alerts/read acknowledges only IDs in the current user's relevant
feed, is idempotent, and uses the usual authentication/origin checks. Read state survives
reload, sign-out and a username change. Badge counts use the configured alert window
and current saved membership, just like the feed. No browser-only read marker is used.

The client refreshes on saved-membership changes, explicit refresh, window focus and a
60-second timer. This is polling rather than instant server push. Failed acknowledgements
retain the unread count and offer retry via refresh. The tray keeps only the relevant
before/after values, affected team slots and detection time, with warnings for an
incomplete scan instead of long default explanations. Manually generated events keep
their demo label.

## Verification

Backend checks cover combined filters, range validation, profile verification/rename,
password revocation, duplicate names, privilege-field rejection and persistent per-user
read acknowledgements. Component tests check closed-by-default behavior, unread badges,
acknowledgement failures and pagination. Chromium checks the account card dimensions,
header position, advanced filtering, draft preservation across Profile, rename/password
changes, saved-team deletion and mobile width. The admin browser flow checks real unread
badges before opening the tray, acknowledgement and persistence after reload.

An existing test still expected “All changes saved” after the copy became “Saved”; its
assertion was updated. A profile browser check found that a stale #profile route survived
password-triggered sign-out; sign-out now clears that view so a new login starts in the
Pokédex. Historical separate-demo tooling remains opt-in; the same-app admin controls
continue to provide the demonstration workflow.


During the local deployment, the scanner's previous startup behavior began a live scan
while a manual scenario was active. The worker was stopped; only the two reversals
created by that interrupted startup run were restored in a checked transaction, and
only its new history entries were removed. The owner's original scenario, two events
and any read markers were retained. The interrupted audit was preserved and recovery
was recorded. Worker startup now calculates the remaining configured interval from
the most recent completed full live scan, ignoring manual scenarios and reset/recovery
audits. A regression test covers the remaining delay and an overdue scan. Explicit
admin refreshes still run on request regardless of that timer.
