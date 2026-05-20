# ADR 0001: Python backend with Pipecat, not NestJS

**Status:** Accepted

**Context:** Take-home requirement specifies Pipecat for voice input. Pipecat is Python-only (no TS pipeline SDK). Options: (a) all-Python backend, (b) hybrid Python voice + NestJS state.

**Decision:** All-Python (FastAPI + Pipecat). TypeScript appears in the React frontend only.

**Reasons:**
- Hybrid = 3 services to deploy, inter-service auth, 2 Dockerfiles — kills day 2
- Pipecat examples and docs are Python-first; fighting the stack wastes time
- camb.ai is a voice AI company; Python/Pipecat competency is probably valued
- TypeScript still demonstrated via React frontend, Zod-typed hooks, strict tsconfig

**Consequences:**
- Single Python process owns voice pipeline + REST API + event bus + WS
- Scales horizontally only with sticky sessions (fine for demo); for prod, pipeline would move to worker pool
