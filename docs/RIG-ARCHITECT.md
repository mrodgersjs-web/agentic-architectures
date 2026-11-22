# RIG Architect Integration Layer

This fork extends [theaiautomators/agentic-architectures](https://github.com/theaiautomators/agentic-architectures) (MIT, built over [FareedKhan-dev/all-agentic-architectures](https://github.com/FareedKhan-dev/all-agentic-architectures)) with a governed, machine-readable pattern layer for RIG repositories (`job-search-os`, `rig-gtm-studio-v2`, `rig-company-os`).

## What Was Added
- `patterns/build_registry.py` + `patterns/registry.json`: Deterministic generator and catalog covering all 36 runnable classes (35 numbered patterns across 8 families) with `lane` + `reconcile_owner` pass-through keys and `draft_only_default: true`.
- `patterns/rig_guards.py`: Pure fail-closed F1-F8 + lane-isolation guard engine using universal exit codes (`0=PASS`, `1=HOLD`, `2=BLOCK`) and exact-text Gate-D `sha12` hashing.
- `patterns/composer.py`: Executable LangGraph multi-pattern composer (`compile_blueprint_to_langgraph`, `run_blueprint_dry_run`), SHA-256 hash-chained `proof_chain`, deterministic pattern recommender with anti-pattern misfit warnings, and universal Canvas-to-Blueprint compiler (`compile_canvas_to_blueprint`).
- `patterns/goodbad_suite.py`: Executable 24-case adversarial GOOD/BAD gate suite (12 GOOD + 12 BAD across `JOB`, `RIG`, and `COMPANY_OS`).
- `patterns/job_os_adapter.py`: Reusable `PatternBackedHooks` implementing `job-search-os` `PipelineHooks` (`offline_deterministic`, RIG LiteLLM `:18770/v1`, or Codex CLI shim `:8035/v1`; fail-closed on hosted Jev).
- `patterns/rig_architect_router.py` + `dashboard/static/architect.html`: FastAPI endpoints (`GET /api/patterns`, `POST /api/patterns/recommend`, `POST /api/patterns/{id}/dry-run`, `GET /api/blueprints`, `POST /api/blueprints/{name}/dry-run`, `GET /api/goodbad`, `GET /api/architect/health`, `GET /architect`).
- `patterns/cli.py`: BAMA-compliant Agent CLI + stdio JSON-RPC 2.0 MCP server (`rig-patterns`).
- `blueprints/`: Verified blueprints for `job-search-os` (8 nodes), `gtm-studio` (5 loops), `company-os` (6 intake nodes), and `repo-rollout-matrix.json`.
- `tests/test_rig_architect_contract.py`: 9 contract, LangGraph composer, 24-case GOOD/BAD, and Canvas parity tests.
