# Phase: SPECIFY — capability {{CAP_ID}}: {{CAP_TITLE}}

Read `.rekit/prompts/kitspec.md` (three layers, neutrality rule), then `kit/00_overview.md`, `kit/02_constraints.md`,
`kit/01_glossary.md`, `kit/03_interfaces/`, `kit/04_data/`, `.rekit/questions/answered.json` (if present).
Capability: {{CAP_ID}} — {{CAP_DESC}}
Sources for this capability (sections `## {{CAP_ID}}`{{ALIASES}} in):
{{NOTES}}
plus the matching test vectors in the same units' `tests.md`. Consult `kit/legacy_ref/modules/<unit>.md` and the
legacy code roots (read-only: {{CODE_ROOTS}}) whenever a note is unclear, incomplete or contradicts another note —
the code is the truth for current behavior.

Write the legacy-NEUTRAL specification of this capability:
1. `kit/05_behavior/{{CAP_ID}}.md`:
   - purpose and external view (which contracts IF-/DM- and flows FL- it serves), entry conditions (which external
     events/commands/jobs trigger it), observable effects;
   - rules `BR-{{AREA}}-NNN` (condition → observable outcome), invariants `INV-{{AREA}}-NNN`, observable state machines
     `SM-{{AREA}}-NNN` (tables), errors `ERR-{{AREA}}-NNN`, outcome-determining algorithms `ALG-{{AREA}}-NNN`
     (declarative: inputs, criteria, tie-breaks, formulas/constants, ordering constraints, `결과 결정: …`);
   - configuration-dependent behavior with the PRODUCTION value marked; quirks to preserve flagged `quirk`;
   - `## 근거 노트` list: which note IDs each spec ID merges (e.g. `BR-SMART-003 ← BR-HLTH-002, BR-NVME-014`).
   Merge duplicates across units, resolve contradictions (read the code), renumber into this capability's ids.
   Neutrality: no legacy internal function/variable/type/file/module names, no legacy call structure, no code-shaped
   pseudo-code, no source paths (contract identifiers are fine). Describe WHAT, so that an engineer could implement it
   with a completely different decomposition and get identical observable results.
2. `kit/07_tests/vectors/{{CAP_ID}}.md` — test vectors `TV-{{AREA}}-NNN` (renumbered), each referencing the spec ID it
   checks, stated through contracts: concrete input → exact expected output, including edge cases and errors. Add
   vectors for rules that have none.
3. `.rekit/notes/spec/{{CAP_ID}}.trace.json` — {"<new ID>": {"file": "kit/...", "src": ["<root>:<path>:L1-L2", ...],
   "confidence": "...", "from": ["<note ids>"]}} for every ID you wrote (src = union of the merged notes' src).
Reply with a 3-line summary (counts of rules/invariants/algorithms/test vectors).
