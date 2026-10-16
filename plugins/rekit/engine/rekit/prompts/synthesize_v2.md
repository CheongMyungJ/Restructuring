# Phase: SYNTHESIS — system-level contracts, data, context and legacy reference

Read `.rekit/prompts/kitspec.md` (three layers, neutrality rule), then {{SOURCES}}, `.rekit/units.json`,
`.rekit/questions/survey.json`, `.rekit/questions/answered.json` (if present), all `.rekit/notes/*/issues.md`,
and skim `.rekit/notes/*/behavior.md` and `kit/legacy_ref/modules/*.md`.
Legacy code roots (read-only) for resolving conflicts: {{CODE_ROOTS}}. Materials: `.rekit/materials_text/`.

The per-capability behavior files (`kit/05_behavior/CAP-*.md`) and test vectors are written by the NEXT phase; do not
write them here. Write / complete:
1. `kit/03_interfaces/IF-*.md` — one file per external contract; merge duplicates; resolve conflicts between units by
   reading the code; byte/field exact.
2. `kit/04_data/DM-*.md` — persisted/shared data contracts (on-media formats, files, tables, persisted counters),
   invariants, lifecycle. Purely internal data structures stay in legacy_ref.
3. Spec context (legacy-neutral, no legacy internal names or file names): `kit/00_overview.md` (final, incl. the
   capability list and end-to-end flows `FL-NNN` as step lists referencing CAP/IF/DM IDs and observable effects),
   `kit/01_glossary.md` (domain terms; contract identifiers only), `kit/02_constraints.md` (final: externally imposed
   runtime/call model, production configuration and variant facts, compatibility requirements), `kit/06_nfr.md`
   (NFR-NNN with evidence).
4. Capabilities: review the capability list against all `behavior.md` notes (incl. `CAP-NEW` proposals). Update
   `.rekit/units.json` → "capabilities" so that every note section maps to exactly one existing capability (merge or
   add capabilities as needed; keep ids stable when possible; each entry keeps "id", "area", "title",
   "description", "units"). Every `## CAP-NEW: <proposal>` section in a unit's `behavior.md` must end up under a
   real capability: edit that heading in the note to the capability id it now belongs to (proposals of different units
   may go to different capabilities). If you rename/merge an existing capability id, write the mapping old→new into
   `.rekit/capability_map.json` ({"CAP-OLD": "CAP-X"}; `{}` if none). The engine refuses to continue while a
   `## CAP-…` note heading matches no capability (it would silently drop that behavior).
5. `kit/07_tests/README.md` — how tests are organized (`vectors/CAP-*.md` filled next phase, `golden/` from running
   the legacy) and the comparison rules.
6. Legacy reference: `kit/legacy_ref/README.md` (usage rule: reference only — consult it for a specific spec ID via
   `trace.json` when the spec is ambiguous; never copy its module/file/function structure or internal names),
   `kit/legacy_ref/structure.md` (final: legacy modules, runtime model, dependency graph, module → capability map),
   `kit/legacy_ref/structure_issues.md` — merged, deduplicated structural problems `### LP-NNN <title>`: the problem,
   where it shows (src refs), impact on maintainability/testability/porting, affected capabilities.
7. `.rekit/questions/merged.json` — JSON array: deduplicate/merge all questions (keep the surviving id; list merged ids
   in "merged_from"); DROP questions the code can answer (answer them in the kit instead); keep only questions a
   domain expert/operator can answer; set priority (blocking > important > minor). Kitspec format.
8. `.rekit/notes/synthesis_trace.json` — {"<ID>": {"file": "kit/...", "src": [...], "confidence": "..."}} for the IDs
   you created or finalized here (IF, DM, FL, NFR, LP, CAP).
Reply with a 5-line summary.
