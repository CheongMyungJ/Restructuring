# Phase: NEUTRALIZE — remove legacy structure from the spec

Read `.rekit/prompts/kitspec.md` (three layers, neutrality rule). A deterministic scan found legacy-structure leaks in
the spec layer (kit root files `00`–`08`, `05_behavior/`, `07_tests/vectors/`): legacy internal identifiers
(functions, types, variables, macros, classes), legacy file/directory names, and source references.
Leak list (file → leaked tokens with counts): `.rekit/neutrality_leaks.json`.
Legacy code roots (read-only): {{CODE_ROOTS}}.

For every leak decide and fix:
- It names an internal mechanism → rewrite the statement in domain/observable terms (what is observable, not which
  function does it). If the sentence only described HOW the legacy works, move it to the matching
  `kit/legacy_ref/modules/<unit>.md` (with src refs) and keep only the observable consequence in the spec.
- It is genuinely part of an external contract (a name the outside world sees: API symbol, field of a persisted format,
  property/env name, file/table/column name, opcode, log text consumed by others) → keep it, and make sure it is
  defined in the right `kit/03_interfaces/IF-*.md` or `kit/04_data/DM-*.md` (that is what makes it allowed).
- It is a source reference/file path → delete it from the spec text (the source is in `kit/trace.json`).
Do not drop behavior: every rule must keep its exact conditions, values, boundaries and test vectors. Do not touch
`kit/legacy_ref/`, `kit/07_tests/golden/`, `kit/09_open_questions.md`, `kit/trace.json` except to move content into
legacy_ref as described.
Write `.rekit/neutralize_report.json`: [{"file": "...", "token": "...", "action": "rewritten|moved|contract|src-removed"}].
Reply with a 3-line summary.
