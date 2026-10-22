Data Layer
- How to setup, how to debug
- Insert diagram of schema design
- Talk about why postgres was selected, why alembic/sqlachemy is used
- Any Tradeoffs?

Ingestion Process
- How to setup, how to debug
- Talk about ingestion process, how it is scheduled
- Any tradeoffs?

Backend Service:
- How to setup, how to debug
- Authentication - FastAPI Users, why was it used?
- uv package manager
- What endpoints are available and how they are called?
- How does counter calculations/simulation work? (Can briefly describe but link to in-depth overview)
- Any tradeoffs?

Frontend:
- How to setup, how to debug
- Why React/TypeScript was chosen
- Any special unique solutions used?
- Any tradeoffs?

Infrastructure and CI/CD:
- Explain terraform, how secrets are managed, how github actions are used
- How testing is done, what sort of testing is there and for which components, why do we use those frameworks?
- Any tradeoffs?

Demo:
- Administrative API Endpoints (Could put behind admin portal)
- Steps on how to run?
- How do we know this means it will definitely work in production??

Backlog/Future Improvements:
- Admin portal for adminstrative actions
- Use Entra or equivalent for Authz/Authn
- Observability/Monitoring - RUM?
- Added features for counters/simulations
- Anything else you can think of? Maybe how to push notifications rather than pull?
