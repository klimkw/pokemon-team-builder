# App info, secrets review and calculation evidence

The owner requested confirmation of unit/E2E coverage, an explanation of secret
handling before hosting, stronger calculation transparency/tests and a header info
popup with release/refresh/repository details.

Tests already covered backend units/integration, real PostgreSQL behavior, components
and Chromium E2E flows. New checks compare ratio rounding against exact fractions,
exercise score bounds/monotonicity and target/candidate permutation invariance, compare
damage rounding with fractions at boundaries, and conserve HP across turn logs. Existing
exhaustive assignment comparisons, priorities, duplicates and battle edge cases remain.
These establish conformance to the declared model; they do not validate it as a real
Pokémon battle engine. No test suite can justify a blanket bug-free claim. There is no
GitHub Actions workflow yet; Docker suites are automated but currently invoked manually.

The README includes a short actual selection excerpt and a tested numerical example.
CounterPreview adds a Show score arithmetic disclosure with the pair's actual inputs,
R(a,b) rounding, durability products and component sum. The detailed Markdown model
guide remains authoritative, preserving the final one-page README as a later task.

AppInfo is a lazy-loading native dialog in the header, available before/after sign-in.
Its public /api/info endpoint returns only an explicit schema: release version from
backend/pyproject.toml, model versions, repository URL, catalog count, schedule/window
settings, latest full live refresh and last successful full live refresh. Demo/sample
runs are excluded; failed/partial/running latest activity does not erase last success.
It exposes no settings dump, database URL, user/session data, scan payload/summary or
raw errors. It is no-store, refreshes on demand and states the interval is not a live
countdown or worker-health guarantee. Refresh info does not enqueue a scan.

Secret review checked configuration and tracked filenames without printing the real
.env. Root .env is ignored; only .env.example is tracked. Compose injects runtime DB
credentials; that is not encrypted vault storage and container operators can inspect
it. The frontend needs no backend secret. Both image build contexts now exclude .env
variants recursively. Authentication uses opaque DB sessions rather than a JWT secret;
raw session-token DB storage is an existing documented trade-off. Production managed
runtime secrets, fresh credentials, access/rotation controls and HTTPS secure cookies
are hosting work, not claimed as configured. The README links OWASP guidance.

Verification covers public info allowlisting, no-cache behavior, exclusion of fake
private errors/payloads, real vs manual refresh timestamps, dialog retry/close, links,
anonymous/signed-in access, mobile header width and desktop/mobile screenshots.

Final verification: 141 PostgreSQL, 125 SQLite (16 skips), 29 component tests and six
regular Chromium flows passed; production build passed. The new info test's missing
catalog fixture was corrected before rerunning. Desktop/mobile popup screenshots
reviewed; reports: test-artifacts/info-audit/. Deployment health/schema checks and live
metadata allowlist passed; database counts and worker schedule remained unchanged.
Commit: “Add safe app info and strengthen calculation transparency”.
