# Documentation

The root [README](../README.md) is the reviewer overview. These guides provide the
working details without turning that overview into a runbook.

| Guide | Purpose |
| --- | --- |
| [Architecture](architecture.md) | Subsystems, diagrams, tradeoffs and links to implementation/tests |
| [Development](development.md) | Local setup, developer workflows and repository layout |
| [Deployment](deployment.md) | Render, Neon, scheduled scans, secrets and release operations |
| [Troubleshooting](troubleshooting.md) | Diagnose common setup, session, scanner and deployment failures |
| [Demo walkthrough](demo.md) | Review team persistence, counters and controlled catalog changes |
| [Testing](testing.md) | Isolated suites, coverage, browser tests and validation boundaries |
| [Counter model](counter-model.md) | Exact scoring rules, illustrative simulation and limitations |
| [Architecture decisions](adr/README.md) | Focused records of significant technical choices |

Contributor workflow lives in [CONTRIBUTING.md](../CONTRIBUTING.md). Coding-agent
instructions live in [AGENTS.md](../AGENTS.md). Provider-specific infrastructure
instructions remain beside the code in [infra/terraform](../infra/terraform/README.md).

The app renders architecture.md at `/architecture` and counter-model.md at
`/counter-method` from these same files. Do not create separate frontend copies.
Frontend Docker builds use the repository root as their context to include them.

## Historical material

[Implementation reference](reference/project-guide.md), [build journals](archive/agent-process/README.md),
[testing notes](archive/testing-notes.md) and [handoff history](archive/handoff.md)
preserve earlier decisions and results. They are historical context rather than
current setup instructions. The original [README outline](archive/readme-outline.md)
is retained as the author's planning artifact.
