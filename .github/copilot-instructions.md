# Copilot instructions

## Source of truth and scope

- Treat `SPEC.md` as the authoritative feature specification. Do not silently change its behavior, defaults, errors, formulas, or output paths.
- Follow the implementation order and dependencies in `PLAN.md`. Keep module interfaces consistent with that plan and existing callers/tests.
- Make only the changes needed for the current task. Keep changes small, focused, and clear; do not modify unrelated files or functionality.
- Do not remove, weaken, skip, or rewrite existing tests merely to make them pass. If a test conflicts with `SPEC.md`, report the conflict instead of quietly changing the test or specification.

## Python and data structures

- Use only the Python standard library. Do not add external dependencies.
- Implement the core hash tables directly. Do not use Python `dict`, `set`, or built-in `hash()` to store, index, or locate hash-table keys.
- Use the Horner string hash specified by `SPEC.md`: start at zero and, for each character from left to right, calculate `h = (h * 31 + ord(character)) % capacity`.
- Implement separate chaining and linear probing directly, following the data structures and interfaces in `SPEC.md` and `PLAN.md`. Do not substitute Python collection types or library hash tables for either collision strategy.
- Preserve the distinct measurement units: separate chaining counts stored-key equality comparisons; linear probing counts inspected slots, including the empty slot that terminates an unsuccessful search. Never label or compare these as if they were the same unit.

## Test-driven development

- Follow TDD for each implementation step: write focused tests first, run them and confirm the expected failure, implement the smallest change that satisfies them, then rerun the tests and confirm they pass.
- Keep tests deterministic and cover the specified normal and boundary cases, including successful and unsuccessful searches.
- Preserve the existing `Makefile` command interface: `make test`, `make serve` (with `PORT`), and `make experiment`. Do not change these commands unless the task explicitly requires it and `SPEC.md` is updated by request.
- After completing implementation work, run `make test` and report the actual result. Do not claim tests passed if they were not run or failed.

## Completion

- Check the final diff for unrelated changes and formatting issues.
- Summarize changed files and validation results. Do not commit or push unless explicitly requested.

## Feature branches, issues, and integration

- Implement project work on a feature branch; do not make feature changes directly on the default branch. Prefer `feature/<issue-number>-<short-name>` when an issue exists.
- Associate each feature branch and pull request with the relevant issue. Confirm the issue's acceptance criteria against `SPEC.md` before implementation; do not create duplicate issues.
- Keep commits small, coherent, and descriptive. Include the relevant issue reference when one exists, and commit only after the focused tests and required project checks pass.
- Do not push or merge directly to the default branch. Open a pull request and merge only after required review and checks pass.
- Do not create commits, push branches, open or merge pull requests unless the user explicitly requests that GitHub operation.
