# Phase: CHARACTERIZATION — capture real (golden) behavior of the legacy system

Read `.rekit/prompts/kitspec.md`, `kit/README.md` (if present), `kit/00_overview.md`, `kit/03_interfaces/`,
`kit/04_data/`, `kit/05_behavior/`, `kit/07_tests/`, `.rekit/units.json` ("runnable"), `.rekit/intake.md`.
Legacy code roots (read-only, NEVER modify): {{CODE_ROOTS}}. Work only in a copy: `.rekit/sandbox/`.

Goal: executable characterization tests that let an implementer verify a NEW implementation against the ACTUAL legacy
behavior, through external contracts only.
1. Decide feasibility: can the legacy code (or its hardware-independent parts) be built and run here? (Use stubs/
   simulators for hardware or external systems when the logic is host-runnable; use an embedded/in-memory DB if
   the SQL is compatible; synthesize realistic input data from the documented formats.) Time-box yourself sensibly.
2. If feasible: build it in `.rekit/sandbox/`, write a harness driving it through scenarios that cover the kit's rules,
   boundaries, error paths and interface formats (use the kit's TV vectors + your own). Capture the actual outputs.
   Store under `kit/07_tests/golden/<scenario>/` (inputs + expected outputs, exact bytes; note what must be ignored,
   e.g. timestamps). Write `kit/07_tests/README.md` explaining how to run the scenarios against a NEW implementation
   (runner scripts parameterized by the implementation location; contract-level only) and the comparison rules.
   Scenario names and runner scripts use domain terms (capabilities/contracts), not legacy module names; the runners
   must work for ANY implementation that honors the contracts (no dependency on legacy internals).
3. Wherever actual legacy behavior contradicts the kit, FIX the kit (running legacy is the truth for current behavior)
   and tag verified items `[실행확인]`. Spec fixes follow the neutrality rule of kitspec.md (observable terms, no
   legacy internal names or source paths in the spec; those go to `kit/legacy_ref/` or `kit/trace.json`).
4. If not feasible: write in `kit/07_tests/README.md` why and what would be needed (hardware, DB, sample data,
   credentials) and add a `material_request` question to `.rekit/questions/characterize.json` (JSON array).
Reply with a 5-line summary (feasible?, #scenarios, #kit fixes).
