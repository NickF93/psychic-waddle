# Repository Agent Instructions

These instructions are mandatory for every automated or assisted change in this
repository.

## Project Scope

This repository implements a small recruiter-facing Portfolio RAG Assistant.
It is not a generic autonomous agent platform.

The assistant must retrieve verified context, apply deterministic answer policy,
and use the LLM only to phrase approved answers.

`docs/architecture.md` is the authoritative architecture contract. Planned or
implemented changes must not contradict it unless the contract is updated in the
same change.

## Engineering Constraints

- Keep the system simple, clean, solid, reliable, bounded, and task-specific.
- Apply SOLID practice as a non-negotiable requirement.
- Prefer SOLID boundaries over DRY.
- Do not merge unrelated authorities just to remove repeated code.
- Keep components decoupled and explicitly defined.
- Do not mix provider I/O, retrieval, answer policy, answer generation, storage,
  ingestion, analytics, and API concerns.
- Do not add legacy code, compatibility shims, deprecated paths, shortcuts, or
  workarounds.
- Do not add hidden fallback behavior.
- Do not add generic agent loops, tool-call loops, or unbounded model-driven
  execution unless a future explicit plan changes the project scope.
- Provider-specific payloads must stay inside provider implementations.
- Configuration must be explicit. Do not add legacy aliases for configuration
  names.
- Tests are required for implemented behavior.
- Documentation must be updated when contracts, architecture, configuration, or
  public behavior changes.

## Data and Privacy Constraints

- The reviewed knowledge base is the only source of truth.
- Visitor questions are improvement signals only.
- Visitor questions must never be automatically promoted into facts.
- Store no visitor identity.
- Do not store IP addresses, user agents, cookies, session identifiers, email
  addresses, phone numbers, names, company names, photos, or raw transcripts.
- If question collection is implemented, store only redacted question text and
  non-identifying answer metadata needed to improve retrieval quality.

## Git-Flow Rules

- `main` is for releases only.
- `develop` is for development integration only.
- Never commit directly on `main` or `develop`.
- Never push directly to `main` or `develop`.
- If the current branch is `main` or `develop`, create or switch to a working
  branch before making changes.
- Use branch names with clear prefixes:
  - `feature/<short-name>`
  - `fix/<short-name>`
  - `docs/<short-name>`
  - `test/<short-name>`
  - `refactor/<short-name>`
  - `chore/<short-name>`
  - `release/<version>`
  - `hotfix/<short-name>`
- Normal work targets `develop`.
- Every completed item or sprint must be committed immediately after its
  validation step.
- Do not leave a completed item or sprint uncommitted unless the user explicitly
  stops the work before completion.
- Commit messages must always use the `type(scope): summary` format.
- Keep commit scope names short and concrete, for example
  `docs(architecture): define milestone 0 contract`.
- After the first commit for a normal work branch, open a draft pull request to
  `develop`.
- Release work uses `release/<version>` branches and may target `main` only with
  explicit release approval.
- Tags must use the `v` prefix, for example `v0.1.0`.
- Merge only through pull requests.
- Use `gh` outside the sandbox for PR operations when required.
- Never merge automatically.
- Never merge without explicit user consent.
- Never squash merge.
- Never rebase merge.
- Use merge commits for PR merges.
- Never delete the source branch after merge.
- Do not perform local direct merges into `main` or `develop`.

## Worktree Safety

- Inspect the current branch and worktree before editing.
- Preserve user changes.
- Do not revert or overwrite changes made by the user unless explicitly asked.
- Keep edits scoped to the requested task.
- If a required action conflicts with these rules, stop and ask for explicit
  instruction.
