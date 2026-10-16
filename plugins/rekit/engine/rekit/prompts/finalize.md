# Phase: FINALIZE — plan, entry point, consistency

Read `.rekit/prompts/kitspec.md` (three layers, neutrality rule) and the whole kit, especially `kit/design/`.
Coverage report from the engine: `.rekit/coverage.json` (source files and symbols never referenced by the kit).
Neutrality report: `.rekit/neutrality.json`. Legacy code roots (read-only): {{CODE_ROOTS}}.

1. Coverage: for every unreferenced source file/symbol, either add the missing behavior (observable part → the right
   `kit/05_behavior/CAP-*.md`, internal part → `kit/legacy_ref/modules/<unit>.md` with src refs) or list it in
   `kit/legacy_ref/structure.md` section `## 제외/미사용 코드` with a reason.
2. Write `kit/10_plan.md`: ordered implementation tasks `T-NNN` following the TARGET design (`kit/design/`), not the
   legacy module order: build components C-* in dependency order (contract boundary and data contracts early, so tests
   can run), each task small enough for one AI session. For each: goal, component(s), spec IDs to load (context pack:
   `05_behavior` / `03_interfaces` / `04_data` / `07_tests` ids + the design sections; never legacy_ref), done criteria
   (which TV/golden tests must pass), risks/open assumptions.
3. Write `kit/README.md` — the implementer's entry point:
   - what the system is (3 lines); the three layers and the reading order: spec (`00`→`02`→`03`→`04`→`05`→`06`→`07`→
     `08`→`09`) → `design/` → `10_plan.md`;
   - **rules for the implementer** (verbatim intent, in {{LANG}}):
     (a) build the structure of `design/` (components, layout, names); the legacy structure is not a requirement;
     (b) preserve every contract (`03`, `04`) and every spec rule/test exactly; production configuration is the default;
     (c) `legacy_ref/` and any legacy source code are references for resolving a specific ambiguity only: look up the
         spec ID in `trace.json`, read just that place, then express the answer in the new design — never port files or
         functions one-to-one, never reuse legacy internal names (contract names excepted), never mirror the legacy
         module layout; if you deviate from `design/`, record an ADR in `IMPLEMENTATION_NOTES.md`;
     (d) verify through contracts: TV vectors and `07_tests/golden`;
     (e) do not keep the legacy source in the new project's workspace; if it is there anyway (or you consulted it),
         run `python3 kit/tools/structure_check.py <legacy code dir> <new code dir> --detail` before finishing. The
         contract files are fixed by the kit (`03_interfaces/files/`); do not exclude anything else. Targets: LSS < 20
         and function mirror M4 < 10%; every function it lists as mirrored must be rewritten following `design/` —
         renaming identifiers or excluding files does not change what was ported. Report the tool's verdict as is;
   - ID and tag conventions, how to use `07_tests` and `10_plan.md`;
   - list of must-preserve contracts; open questions summary with applied assumptions.
4. Make `kit/trace.json` complete and consistent (every ID heading in the kit has an entry and vice versa; spec IDs
   keep their legacy src there).
Do not add legacy internal names, file names or source paths to the spec or design layers while doing this.
Reply with a 3-line summary.
