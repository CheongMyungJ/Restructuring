# Phase: GROUP SYNTHESIS — subsystem {{GROUP_ID}}: {{GROUP_TITLE}}

Read `.rekit/prompts/kitspec.md`. Units of this subsystem: {{UNITS}}.
Read their `.rekit/notes/<unit>/digest.md`, `contracts.md`, `tests.md`, `questions.json`, `issues.md` and skim
`.rekit/notes/<unit>/behavior.md` and `kit/legacy_ref/modules/<unit>.md`.
Legacy code roots (read-only) for resolving conflicts: {{CODE_ROOTS}}.

Write `.rekit/groups/{{GROUP_ID}}/summary.md` (≤ 120 lines): purpose, internal structure, flows inside the subsystem,
interfaces offered to / used from other subsystems (exact), shared data, hazards, capabilities served.
Write `.rekit/groups/{{GROUP_ID}}/contracts.md`: merged, de-duplicated, conflict-resolved external contracts and data
formats of this subsystem (byte/field exact, IF-/DM- IDs).
Write `.rekit/groups/{{GROUP_ID}}/questions.json`: merged/deduplicated questions of these units (drop ones the code
answers — answer them in the kit instead). Write `.rekit/groups/{{GROUP_ID}}/tests.md`: merged test vectors (keep
their CAP tags). Write `.rekit/groups/{{GROUP_ID}}/issues.md`: merged structural problems.
Reply with a 3-line summary.
