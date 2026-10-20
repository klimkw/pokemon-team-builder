# Sorting, range sliders and team comparison

The owner requested stat sorting, sliders instead of empty range boxes, shared type
styling and visible stats for selected Pokémon. The catalog now offers Index plus low
to high/high to low ordering for all six base stats. Index remains the default, and
index ascending breaks equal-stat ties consistently. Sorting is applied in SQL after
filtering and before pagination; changing the sort returns to page one.

GET /api/pokemon accepts `sort=index`, `hp_asc`, `hp_desc`, and the equivalent suffixes
for attack, defense, special_attack, special_defense and speed. Unsupported choices
are rejected by the API's enum. The response also includes stat_maxima computed over
the whole catalog, independent of current filtering. Each slider's upper domain is
at least 255 and expands for larger stored/demo values. An empty filtered result does
not shrink the slider domain or prevent widening the range again.

Each stat uses a shared-track pair of native range controls, labelled minimum and
maximum, with a visible numeric output. Keyboard controls and pointer dragging are
supported; handles clamp instead of crossing. Default endpoints omit query bounds so
clearing filters restores the unbounded view. Slider changes retain the search debounce
and stale-request cancellation. The range query's inclusive semantics remain unchanged.

TypeBadge/TypeBadges are shared by catalog cards, filter options and team slots, so
font, color and background styles are consistent. Selection state is indicated by
the filter option outline/checkbox rather than replacing its type color. StatList is
also shared: all six labels/values are visible inside each occupied team slot, matching
the catalog's order and terminology. Catalog cards gain a selection outline and an
“In team” count, including repeated slots. This count sits outside document flow to
avoid shifting cards when a Pokémon is selected.

Backend tests check all twelve stat sort directions, numeric ordering, index tie breaks,
pagination/filter combinations, invalid options and global slider maxima. Component
checks verify accessible range values and clamping. Chromium verifies the sort request,
keyboard and pointer slider interaction, selection counts, six team stats, matching
computed type styles across the three surfaces, and mobile width. Existing team,
profile, account, counter and admin-alert flows remain covered.


Visual review caught a duplicate selected-count label in team slots, which was
positioned against an outer panel. It was removed so only catalog cards display the
count, and the browser test now checks there is exactly one badge for the selected
catalog entry even when two team slots contain it. The final frontend checks were
rerun after that correction. Verification totals: 127 PostgreSQL, 112 SQLite with 15
skips, 23 component tests and six regular Chromium flows.
