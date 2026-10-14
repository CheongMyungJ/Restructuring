# Phase: INTEGRATE HUMAN ANSWERS

Read `.rekit/prompts/kitspec.md` and `.rekit/questions/to_integrate.json` (questions with the human's answers).
Legacy code roots (read-only): {{CODE_ROOTS}}. New materials provided by the human (if any) are listed in the answers;
converted text is in `.rekit/materials_text/`.

For each answered question:
1. Update every affected kit file (rules, interfaces, data, tests, plan) so the kit reflects the answer. If the answer
   says the production behavior differs from the code default (configuration, environment), the kit must state the
   PRODUCTION behavior as the requirement and keep the legacy default only as a note.
2. Add a decision entry `### DEC-NNN <title>` to `kit/08_decisions.md` (create if missing; continue numbering):
   question id, answer (verbatim summary), consequence for the new system, affected IDs. Tag affected items `[사람확인]`.
3. If the answer is "unknown"/"모르겠습니다", keep the current assumption, mark it clearly as unconfirmed risk in
   `kit/08_decisions.md`.
4. If an answer makes a NEW question necessary, append it to `.rekit/questions/followup.json` (JSON array, kitspec format).
Reply with a 3-line summary.
