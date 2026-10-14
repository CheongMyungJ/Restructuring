# Phase: SYNTHESIS — merge unit results into system-level kit sections

Read `.rekit/prompts/kitspec.md`, then all `.rekit/notes/*/digest.md`, `.rekit/notes/*/contracts.md`,
`.rekit/notes/*/tests.md`, `.rekit/notes/*/questions.json`, `.rekit/questions/survey.json`,
`.rekit/questions/answered.json` (if present), and skim `kit/05_behavior/*.md`.
Legacy code roots (read-only) for resolving conflicts: {{CODE_ROOTS}}. Materials: `.rekit/materials_text/`.

Write / complete:
1. `kit/03_interfaces/IF-*.md` — one file per external contract; merge duplicates; resolve conflicts between units by
   reading the code; byte/field exact.
2. `kit/04_data/DM-*.md` — persistent and core data structures/formats, invariants, lifecycle.
3. `kit/00_overview.md` (final) including end-to-end flows `FL-NNN` (step lists that reference BR/IF/DM IDs),
   `kit/01_glossary.md` (complete), `kit/02_architecture.md` (final: components, runtime model, config/variants,
   legacy→suggested new structure mapping), `kit/06_nfr.md` (NFR-NNN with evidence).
4. `kit/07_tests/README.md` and `kit/07_tests/vectors/<area>.md` — all test vectors grouped by feature/area.
5. `.rekit/questions/merged.json` — JSON array: deduplicate/merge all questions (keep the surviving id; list merged ids
   in "merged_from"); DROP questions the code can answer (answer them in the kit instead); keep only questions a
   domain expert/operator can answer; set priority (blocking > important > minor). Kitspec format.
6. `kit/trace.json` — merge all `.rekit/notes/*/trace.json` plus entries for IDs you created (file + src + confidence).
Reply with a 5-line summary.
