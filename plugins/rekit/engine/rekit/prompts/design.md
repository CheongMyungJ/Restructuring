# Phase: TARGET DESIGN (clean-room)

You are the architect of the NEW system. You work clean-room: the current directory contains only the legacy-neutral
specification of the system (what it must do) — you have NO access to the legacy source code, and you must not try to
reconstruct or imitate its structure. Design the new system from the requirements.

Read: `kitspec.md` (three layers), `00_overview.md`, `02_constraints.md`, `03_interfaces/`, `04_data/`,
`05_behavior/` (all capabilities), `06_nfr.md`, `08_decisions.md`, `09_open_questions.md`, `07_tests/README.md`,
and the inputs `inputs/intake.md` (goals, target stack, architecture wishes of the owners) and
`inputs/structure_issues.md` (structural problems LP-* of the legacy that must not be carried over — described as
problems, not as a structure to copy).

Write (create directory `design/`):
1. `design/architecture.md`:
   - design drivers: the target stack/platform from the intake (if unknown, choose a sensible one consistent with
     `02_constraints.md` and say so), quality goals from `06_nfr.md`, the owners' wishes;
   - components `### C-<NAME> <title>`: responsibility (in capability terms), owned state/data, provided and required
     interfaces (internal ports — your own names), which contracts it implements at the boundary;
   - dependency rules (layers/allowed directions), runtime/concurrency model satisfying `02_constraints.md`,
     error-handling and configuration strategy (production values as defaults), persistence/recovery strategy that
     satisfies the data contracts, testability (how the TV and golden tests run against components);
   - proposed source layout of the new system (directories/modules with one-line purposes).
   Keep contract-fixed elements exactly as the contracts require (verbatim contract files are in
   `03_interfaces/files/`: use them unchanged, e.g. a host API header, HAL headers, a run script) and design everything
   behind them freely.
2. `design/decisions.md`: `### ADR-NNN <title>` — context, alternatives, decision, consequences. Include one ADR per
   relevant LP-* stating how the new design avoids that problem, and ADRs for key choices (state ownership, layering,
   concurrency, configuration, persistence).
3. `design/allocation.md`: a table assigning EVERY spec ID (CAP, BR, INV, SM, ERR, ALG, IF, DM, FL, NFR) to exactly one
   owning component C-* (enumerate the IDs with the Grep tool, pattern `^### [A-Z]+-`), plus a
   short "cross-component interactions" list for the flows FL-*.
Do not modify any other file. Do not invent behavior: if the spec is ambiguous, note it in the ADR consequences.
Reply with a 5-line summary (number of components, key decisions).
