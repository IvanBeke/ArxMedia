# CLAUDE.md

This file is kept for compatibility. The canonical harness workflow now lives in `AGENTS.md`.

## Current rules

- Process tasks directly from user requests.
- Keep changes minimal and scoped.
- Never run app/UI tooling on host; use Docker commands from repo root.
- Run `./init.sh` before declaring success.
- Define ad-hoc verification checks from the task and touched code paths.

## Reference docs

- `AGENTS.md`
- `docs/architecture.md`
- `docs/conventions.md`
- `docs/verification.md`
- `CHECKPOINTS.md`
