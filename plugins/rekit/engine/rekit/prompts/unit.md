# Phase: UNIT ANALYSIS — unit {{UNIT_ID}}: {{UNIT_TITLE}}

You are a meticulous reverse-engineer. Read the kit specification `.rekit/prompts/kitspec.md` first, then the context:
`kit/00_overview.md`, `kit/02_architecture.md`, `kit/01_glossary.md`, `.rekit/units.json`, `.rekit/intake.md`,
`.rekit/questions/answered.json` (human answers so far, if present).

Legacy code roots (read-only, NEVER modify): {{CODE_ROOTS}}
Files of this unit — read EVERY file completely, line by line (do not skim, do not sample):
{{FILES}}
Focus hint: {{FOCUS}}
You may read any other code to resolve calls, types, constants and macros, and the materials in `.rekit/materials_text/`.

Write (create directories as needed):
1. `kit/05_behavior/{{UNIT_ID}}.md` — complete behavioral specification of this unit: responsibilities; entry points
   (who calls, when); rules `BR-{{UNIT_ID}}-NNN`; algorithms `ALG-{{UNIT_ID}}-NNN` as faithful pseudo-code (constants,
   loop bounds, ordering, quirks); state machines `SM-…` as tables; error behavior `ERR-…`; configuration/variants
   (flags, properties, #ifdef) and which variant is active by default; concurrency/timing; hazards (doc-vs-code,
   environment-dependent behavior, dead code, suspected bugs). Every item: `(src: …)`, confidence tag,
   `계약(유지 필수)` or `구현상세(변경 가능)`.
   End with `## 커버리지`: every function/method/procedure/SQL statement/config entry of this unit's files, mapped to the
   item IDs that cover it, or marked `dead`, `unused`, or `trivial` (with reason).
2. `.rekit/notes/{{UNIT_ID}}/contracts.md` — every EXTERNAL contract (API/ABI, file/message format, DB table & SQL
   semantics, protocol/command, register/HW interface, on-media/persistent layout, CLI/env/config) this unit implements
   or uses, field/byte exact, with IDs `IF-…`/`DM-…` (reuse ids from `.rekit/units.json` contracts when they match).
3. `.rekit/notes/{{UNIT_ID}}/tests.md` — test vectors `TV-{{UNIT_ID}}-NNN`: concrete input → exact expected output
   for every rule with edge cases/boundaries/errors (derived by careful reading → tag `[추정]`).
4. `.rekit/notes/{{UNIT_ID}}/questions.json` — JSON array of questions for humans (kitspec format, ids
   `Q-{{UNIT_ID}}-NN`). Empty array if none.
5. `.rekit/notes/{{UNIT_ID}}/digest.md` — at most 40 lines: what the unit does, key identifiers, cross-unit
   dependencies (calls/data shared), hazards, open points.
6. `.rekit/notes/{{UNIT_ID}}/trace.json` — {"<ID>": {"src": ["<root>:<path>:L1-L2"], "confidence": "..."}} for all IDs
   you defined.
Reply with a 3-line summary (counts of rules/algorithms/questions).
