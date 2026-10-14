# Phase: FINALIZE — plan, entry point, consistency

Read `.rekit/prompts/kitspec.md` and the whole kit. Coverage report from the engine: `.rekit/coverage.json`
(source files and symbols never referenced by the kit). Legacy code roots (read-only): {{CODE_ROOTS}}.

1. Coverage: for every unreferenced source file/symbol, either add the missing behavior to the right kit file (with
   src refs) or list it in `kit/02_architecture.md` section `## 제외/미사용 코드` with a reason.
2. Write `kit/10_plan.md`: ordered implementation tasks `T-NNN` (dependency order, small enough for one AI session
   each). For each: goal, kit IDs/files to load (context pack), done criteria (which TV/golden tests must pass), risks.
3. Write `kit/README.md`: what the system is (3 lines), reading order, ID and tag conventions, how to use
   `07_tests` and `10_plan.md`, list of must-preserve contracts, open questions summary with applied assumptions.
4. Make `kit/trace.json` complete and consistent (every ID heading in the kit has an entry and vice versa).
Reply with a 3-line summary.
