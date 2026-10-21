# Team selection pane

The owner requested a Draft a New Team dropdown option in place of the separate
New team button, and access to counter-team/delete actions without scrolling to the
bottom of a long team panel.

The existing blank select value now opens an empty draft through the same openTeam
handler. Switching away from unsaved work retains the discard confirmation, and
saved teams continue to use their existing IDs. The separate button is removed.

The pane uses a viewport-constrained flex column: its selected Pokémon list scrolls,
while the picker, name and action area remain visible. The list is keyboard focusable
and labelled. Stats and type chips remain present for every selected Pokémon. Compact
action spacing removes the repeated counter-preview hint from the visual layout.
Desktop height accounts for the page header; mobile height accounts for section
navigation. On very short screens a sticky action area provides a fallback.

Browser coverage exercises drafting from the dropdown, cancelling a switch with
unsaved work, saving/switching/deleting teams and reaching counter/delete actions on
390×844 mobile and 1440×720 desktop viewports. Component and full regular browser
suites run in the isolated Docker stack, alongside the production frontend build.
No backend or database change is required.

Screenshot review found that grid rows compressed within the scrolling list, letting
stats overlap the following member. Explicit max-content row sizing fixes this; the
browser flow now checks that stats fit inside the first row and that the next row
starts below it. The catalog-loading component test hit its existing short wait under
parallel suite contention; running the same expectations with one Vitest worker passed.

Final build, 25 component tests and six regular browser flows passed, including the
row-boundary assertion; the legacy separate-demo test stayed skipped. Screenshots were
reviewed on mobile and desktop. Only the development frontend was replaced; backend,
scanner, teams and demo state were left running intact. Reports: test-artifacts/team-pane/.
Commit: “Keep team actions visible and draft from team dropdown”.
