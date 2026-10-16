# Phase: UNIT ANALYSIS — legacy unit {{UNIT_ID}}: {{UNIT_TITLE}}

You are a meticulous reverse-engineer. Read the kit specification `.rekit/prompts/kitspec.md` first (three layers,
neutrality rule), then the context: `kit/00_overview.md` (capabilities), `kit/02_constraints.md`, `kit/01_glossary.md`,
`.rekit/units.json`, `.rekit/intake.md`, `.rekit/questions/answered.json` (human answers so far, if present).

Legacy code roots (read-only, NEVER modify): {{CODE_ROOTS}}
Files of this unit — read EVERY file completely, line by line (do not skim, do not sample):
{{FILES}}
Focus hint: {{FOCUS}}
Capabilities this unit contributes to (from the survey): {{CAPS}}
You may read any other code to resolve calls, types, constants and macros, and the materials in `.rekit/materials_text/`.

{{CHECKLIST}}

You produce TWO views of the same code. Keep them strictly apart.

A. HOW the legacy does it (legacy_ref layer) — `kit/legacy_ref/modules/{{UNIT_ID}}.md`:
   responsibilities and entry points (who calls, when); internal data structures; internal algorithms
   `LR-{{UNIT_ID}}-NNN` as faithful pseudo-code (constants, loop bounds, ordering, quirks); configuration/variants
   (flags, properties, #ifdef) and which variant is active by default; concurrency/locking; dead code;
   legacy identifiers. Inline `(src: …)` + confidence tags.
   End with `## 커버리지`: every function/method/procedure/SQL statement/config entry of this unit's files, mapped to the
   LR-/note IDs that cover it, or marked `dead`, `unused`, or `trivial` (with reason).
   Also write `.rekit/notes/{{UNIT_ID}}/issues.md`: structural problems of this legacy code that a redesign should NOT
   carry over (hidden global state, god functions/files, mixed layers, duplicated logic, hard-wired configuration,
   untestable coupling, ordering hidden in side effects …) — each with concrete impact; no fixes, just the problem.

B. WHAT the system does, observable from outside (spec layer, legacy-neutral) — `.rekit/notes/{{UNIT_ID}}/behavior.md`:
   every observable rule this unit implements, grouped under `## CAP-<AREA>` headings (use the capability ids from
   the survey; add `## CAP-NEW: <proposal>` only if nothing fits). Items `BR-{{UNIT_ID}}-NNN` (rule: condition →
   observable outcome), `INV-…` (invariant), `SM-…` (observable state machine as a table), `ERR-…` (error behavior),
   `ALG-…` only for outcome-determining algorithms written declaratively with `결과 결정: <which observable result>`.
   Follow the neutrality rule: no legacy internal names, file names, or code-shaped pseudo-code here (contract
   identifiers allowed). Confidence tag on each item; source refs go to trace.json (step 6), not into the text.
   Production configuration matters: when behavior depends on a build flag/property, state the behavior per value and
   which value is the production one (or that it is unknown → question).

Also write:
2. `.rekit/notes/{{UNIT_ID}}/contracts.md` — every EXTERNAL contract (API/ABI, file/message format, DB table & SQL
   semantics, protocol/command, register/HW interface, on-media/persistent layout, CLI/env/config) this unit implements
   or uses, field/byte exact, with IDs `IF-…`/`DM-…` (reuse ids from `.rekit/units.json` contracts when they match).
3. `.rekit/notes/{{UNIT_ID}}/tests.md` — test vectors `TV-{{UNIT_ID}}-NNN`, each tagged with its CAP and the note
   item it checks: concrete input → exact expected output for every rule with edge cases/boundaries/errors, stated
   through contracts (derived by careful reading → tag `[추정]`).
4. `.rekit/notes/{{UNIT_ID}}/questions.json` — JSON array of questions for humans (kitspec format, ids
   `Q-{{UNIT_ID}}-NN`). Empty array if none.
5. `.rekit/notes/{{UNIT_ID}}/digest.md` — at most 40 lines: what the unit does, key identifiers, cross-unit
   dependencies (calls/data shared), hazards, open points.
6. `.rekit/notes/{{UNIT_ID}}/trace.json` — {"<ID>": {"src": ["<root>:<path>:L1-L2"], "confidence": "..."}} for all IDs
   you defined (LR-, BR-, INV-, SM-, ERR-, ALG-, TV-, IF-, DM-).
Reply with a 3-line summary (counts of rules/algorithms/questions).
