# TRAPS — S3 "tlog-batch"

Every trap built into the subject, what production really does, what a naive re-implementation does,
and which hidden fixtures / harness checks catch it. The two **tribal** traps (time zone, duplicate policy)
are proven with real runs of the legacy application; the code/doc traps are quantified with the
independent reference model (`tools/refmodel.py`), whose TZ/DUP variants reproduce the real legacy runs
check-for-check (see §4).

## 1. Legacy application in the hidden harness (145 checks, 12 fixtures)

| Run | JAVA_OPTS | Result |
|---|---|---|
| production #1 (clean build) | `-Duser.timezone=Asia/Seoul -Dtlog.dup.policy=LAST` | **145/145**, 12/12 fixtures |
| production #2 (clean build, determinism) | same | **145/145**, 12/12 fixtures |
| **empty (harness default)** | *(empty)* | **104/145**, 1/12 fixtures (41 checks fail) |
| diagnostic: time zone missing | `-Dtlog.dup.policy=LAST` | 104/145 (same 41 failures as empty) |
| diagnostic: dup policy missing | `-Duser.timezone=Asia/Seoul` | 134/145 (11 failures, fixtures 05 and 12) |
| baseline: app that builds, exits 0 and does nothing | — | 20/145 |

The harness forces `TZ=UTC` (and strips `-Duser.timezone` / `-Dtlog.*` from `JAVA_TOOL_OPTIONS` etc.) for
the application processes, so a re-implementation only passes if it applies production behaviour itself.

### 1.1 Checks failing with EMPTY JAVA_OPTS (legacy)

| Fixture | Passed | Failing checks |
|---|---|---|
| 01_basic_flow | 6/11 | table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250312.csv, outbox:YIELD_20250312.txt |
| 02_ms949_korean | 11/12 | table:TB_TEST_RESULT |
| 03_ter_csv_format | 7/11 | table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250314.txt |
| 04_reject_codes | 11/15 | table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250316.txt |
| 05_dup_policy | 5/11 | table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250317.csv, outbox:YIELD_20250317.txt |
| 06_shift_boundary_tz | 6/12 | table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250317.txt, outbox:YIELD_20250318.txt, outbox:YIELD_20250319.txt |
| 07_retest_attempts | 6/11 | table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250319.csv, outbox:YIELD_20250319.txt |
| 08_rules_override | 11/11 | — (ADV only, no duplicates: isolates rule logic from both settings) |
| 09_scrap_es | 10/11 | table:TB_TEST_RESULT |
| 10_yield_trunc_alert | 10/11 | table:TB_TEST_RESULT |
| 11_rerun_noalert | 12/13 | table:TB_TEST_RESULT |
| 12_full_day_mixed | 9/16 | table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250325.csv, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt |

Attribution: with only the time zone missing the failing set is identical (the TZ trap alone breaks every
fixture that contains TER data; in 05/12 it already fails the checks the DUP trap would fail). With only
the dup policy missing, 11 checks fail: 05_dup_policy (TB_TEST_RESULT, TB_DEVICE_BIN, TB_LOT_YIELD,
ALERT_20250317.csv, YIELD_20250317.txt) and 12_full_day_mixed (TB_TEST_RESULT, TB_DEVICE_BIN, TB_LOT_YIELD,
ALERT_20250325.csv, YIELD_20250324.txt, YIELD_20250325.txt). In 09/10/11 the TER records are in the KST
afternoon (UTC >= 06:00) so only START/END_DTM shift while WORK_DT and bins stay the same.

## 2. Trap catalogue

| ID | Trap | Kind | Production truth (legacy = golden) | Naive re-implementation | Checks failing (model / legacy) |
|---|---|---|---|---|---|
| T01 | Time zone | **tribal** | `/etc/profile.d/tlog.sh`: `JAVA_OPTS=-Duser.timezone=Asia/Seoul ...`; OS is UTC. Code formats TER UTC instants and derives WORK_DT with the *JVM default* zone | Port the code literally (default zone) and run in a UTC container | 41 in 11 fixtures (`TZ_UTC`, = legacy empty run) |
| T02 | Duplicate policy | **tribal** | `-Dtlog.dup.policy=LAST` (overwrite with the newest record); code default and design doc say FIRST / keep existing | Keep FIRST | 11 in 05, 12 (`DUP_FIRST`, = legacy run) |
| T03 | Yield truncation | doc-vs-code (+tribal reason) | `ROUND_DOWN` to 2 decimals (MES compares with a truncating calc). Code comment and design doc say 반올림 | HALF_UP rounding; or let H2 `NUMBER(5,2)` round 66.666 -> 66.67 | 22 in 8 fixtures (`YIELD_ROUND`); 10: 8/12 66.66 vs 66.67 threshold, 7/11 63.63 vs 63.64, 1/7 14.28 |
| T04 | Retest limit | doc-vs-code, duplicate constant | First **3** attempts per (serial, step) count (private constant in `BinJudgeProcessor`); `Constants.MAX_RETEST = 5` unused; design doc says 5 | Use 5 | 7 in 07, 12 (`RETEST_5`) |
| T05 | MS949 byte semantics | encoding | ADV record = 140 **bytes**, offsets in bytes; TER operator cut to 10 MS949 bytes without splitting Hangul and not re-trimmed; report PROD_NM 20 bytes (cut + space pad); reject files in source encoding | Character based length/offsets/cuts, UTF-8 rejects | `ADV_CHARS` 85, `RPT_CHARCUT` 16, `TER_CHARCUT` 1, `TRIM_AFTER_CUT` 1, `REJECT_UTF8` 4 |
| T06 | TER CSV format | format | Optional UTF-8 BOM, header skipped positionally, quoted fields with commas and `""`, optional `#EOF,n`, blank lines ignored, values trimmed, `SN` prefix + `-` removed from serials, CRLF or LF | Header-name mapping with BOM kept, no SN strip | `BOM_HEADERMAP` 79, `NO_SN_STRIP` 22 |
| T07 | Numeric conversions | precision | TEMP_F -> C with BigDecimal `(F-32)*5/9` HALF_UP (32.9->1, 22.1->-6); TER READ/WRITE rounded HALF_UP to 1 decimal (1700.25->1700.3) | double + `Math.round` | `TEMP_DOUBLE` 1 (03) |
| T08 | Validation details | hidden rule / doc gap | Undocumented **E08** (STEP not FT1/BI/FT2, case-sensitive); order E01,E02,E08,E03,E04,E05,E06,E07 (first error only); E09 file: `0|E09|<file>`, TOTAL=REJ=detail count, STATUS E; ADV `' P'` trims to P; TER `Pass`/`ft1`/lower-case product rejected | Skip STEP check, check product first, REJ_CNT 0 | `NO_STEP_CHECK` 7, `E07_FIRST` 1, `E09_REJ_ZERO` 1 (all 04) |
| T09 | 06:00 shift boundary | rule | WORK_DT = KST start date, minus 1 day when hour < 06 (night shift arrives in the next day's file) | Calendar date | `WORKDT_CALENDAR` 19 in 06, 11, 12 |
| T10 | Hard-coded enterprise override | doc-vs-code | `PROD_CD` starts with 'E' and max BAD_BLK > 20 -> BIN5 `OVR_E`, after ABORT, before rules (design doc forbids hard-coding) | Rule table only | `NO_OVR_E` 6 in 08, 12 |
| T11 | Scrap stickiness / ES samples | rule | BIN 9 on an **earlier** WORK_DT only -> `SCRAP_KEEP` (beats ABORT); same-day or later BIN 9 not sticky. ES* (after normalisation) judged, EXCL_YN='Y', excluded from yield | Any-date scrap; no exclusion | `SCRAP_ANY_DATE` 4 (09), `NO_ES_EXCL` 12 (03, 09, 12) |
| T12 | ALERT file | doc outdated + quirk | ALERT merged into YIELD (no ALERT job, no TB_YIELD_ALERT); file only when alerts exist; strict `<` threshold, IN_QTY >= 10, NULL threshold never alerts | Header-only file every day | `ALERT_EMPTY_FILE` 4 (04, 06, 11, 12); threshold cases in 10 |
| T13 | MES report bytes | format | MS949, CRLF incl. after the T record, 60 bytes, `TLOGBATCH`, YIELD `099.50`, sort PROD_CD/LOT_ID, H/T-only file on empty days | Spring Batch default writer (no CRLF after footer) | `FOOTER_NO_CRLF` 17 (every YIELD file) |
| T14 | File processing order | rule | Inbox files processed in name order (ADV_* before TER_*), so the TER record wins a cross-vendor duplicate under LAST | Other order | `TER_FIRST` 6 (05) |
| T15 | Re-run safety | doc outdated | `run.ts` job parameter allows same-date re-runs; JUDGE = MERGE, YIELD = delete + insert, report overwritten. Design doc still says to clean BATCH_JOB_* tables first | JobInstanceAlreadyComplete / insert-only | 11 (`exit:codes` + outputs after re-runs) |
| T16 | PURGE unused | **tribal** | Not scheduled in production (DBA drops monthly partitions); design doc says weekly. `run_job.sh PURGE` remains in the contract | — | not in fixtures |
| T17 | Ops contract edge cases | contract | Impossible date (20250230), unknown JOB_ID, 7-digit date -> non-zero exit; LOAD with no files -> exit 0; YIELD on a day without data -> H/T-only report | — | 11 (`exit:codes`), 11 (`YIELD_20250325.txt`) |
| T18 | Inbox selection / archive | rule | Only `ADV_<date>_NN.dat` / `TER_<date>_NN.csv`; other names/dates stay in inbox; every processed file (also fully rejected) moves to `archive/<BIZ_DATE>/` | Glob too wide / skip archiving rejected files | `inbox:listing`, `archive:listing` (03, 04) |
| T19 | Outdated environment info | doc outdated | README/design doc: JDK 1.7, Spring 4, Oracle 11g, CentOS; real: Java 21, Spring 5.3 / Batch 4.3, H2 (Oracle mode) via `TLOG_DB_URL` | — | informational |

## 3. Fixture map

| Fixture | Focus | Main traps |
|---|---|---|
| 01_basic_flow | LOAD/JUDGE/YIELD happy path, rules, alerts | T01, T03, T13 |
| 02_ms949_korean | Korean operator names (ADV bytes, TER 10-byte cut incl. trailing space), 143-byte record, report name cuts | T05, T01 |
| 03_ter_csv_format | BOM, quoting, `#EOF`, SN/ES serials, padded values, HALF_UP temps/speeds, inbox leftovers | T06, T07, T11, T18 |
| 04_reject_codes | E01..E09 incl. undocumented E08, validation order, E09 files, inbox leftovers | T08, T05, T18 |
| 05_dup_policy | duplicates vs DB / same file / other file / other vendor, processing order | T02, T14, T01 |
| 06_shift_boundary_tz | 06:00 boundary for ADV and TER, UTC dates crossing KST midnight, 3 work days | T09, T01 |
| 07_retest_attempts | 1..5 attempts, ignored 4th/5th, ABORT positions, cross-vendor ordering | T04, T01 |
| 08_rules_override | priority / specific-first / BIN desc, boundaries, unknown item, disabled rule, OVR_E, ABORT | T10 (TZ/DUP independent) |
| 09_scrap_es | scrap stickiness earlier/later/same day, ES exclusion, ES-only lot | T11 |
| 10_yield_trunc_alert | truncation vs rounding, alert strict `<`, min sample 10, NULL threshold, BIN2 pass | T03, T12 |
| 11_rerun_noalert | re-runs, late night-shift data, no-alert-no-file, empty day, invalid calls | T15, T12, T17, T09 |
| 12_full_day_mixed | seeded production-like day (507 records, 4 files) | all |

## 4. Evidence and method

* `expected/` was recorded from the legacy application with production JAVA_OPTS (`tools/record_expected.sh`).
* `tools/refmodel.py` is an independent Python implementation of the stated rules; it reproduces all 145
  checks byte-for-byte from the fixture inputs (so the golden outputs follow the specification, not just
  the legacy). Mutating the model to the documented behaviours (retest 5, rounding) makes it fail.
* Variants `TZ_UTC`, `DUP_FIRST` and `TZ_UTC+DUP_FIRST` produce exactly the failing checks of the real
  legacy runs without time zone, without dup policy and with empty JAVA_OPTS (12/12 fixtures identical),
  which validates the model-based numbers for the other traps below.
* Determinism: two production runs from clean builds both 145/145; no volatile values are compared.
* Raw harness reports: `reports/legacy_*.json`, `reports/baseline_noop_app.json`; matrix: `reports/trap_matrix.md`.

## 5. Impact matrix (reference-model variants, one trap at a time, production settings otherwise)

| trap variant | failing checks | fixtures affected (failing checks) |
|---|---|---|
| `TZ_UTC` JVM default time zone is not Asia/Seoul (container UTC): TER UTC->'KST' conversion and WORK_DT use UTC | 41/145 | 01 (5), 02 (1), 03 (4), 04 (4), 05 (6), 06 (6), 07 (5), 09 (1), 10 (1), 11 (1), 12 (7) |
| `DUP_FIRST` duplicate policy left at code default FIRST (keep existing row) | 11/145 | 05 (5), 12 (6) |
| `YIELD_ROUND` YIELD_PCT rounded HALF_UP (design doc / code comment) instead of truncated | 22/145 | 02 (2), 03 (2), 07 (3), 08 (3), 09 (3), 10 (3), 11 (3), 12 (3) |
| `RETEST_5` retest limit 5 (design doc, unused Constants.MAX_RETEST) instead of 3 | 7/145 | 07 (4), 12 (3) |
| `ADV_CHARS` ADV record length / field offsets taken in characters instead of MS949 bytes | 85/145 | 01 (8), 02 (6), 04 (6), 05 (8), 06 (7), 07 (8), 08 (8), 09 (8), 10 (8), 11 (9), 12 (9) |
| `TER_CHARCUT` TER operator name cut to 10 characters instead of 10 MS949 bytes | 1/145 | 02 (1) |
| `TRIM_AFTER_CUT` TER operator name trimmed again after the byte cut | 1/145 | 02 (1) |
| `RPT_CHARCUT` report PROD_NM cut/padded to 20 characters instead of 20 MS949 bytes | 16/145 | 01 (1), 02 (1), 03 (1), 04 (1), 05 (1), 06 (3), 07 (1), 08 (1), 09 (1), 10 (1), 11 (2), 12 (2) |
| `TEMP_DOUBLE` Fahrenheit->Celsius with double arithmetic and Math.round instead of BigDecimal HALF_UP | 1/145 | 03 (1) |
| `NO_STEP_CHECK` undocumented E08 (invalid STEP) not implemented | 7/145 | 04 (7) |
| `E07_FIRST` product check (E07) done before the other field validations | 1/145 | 04 (1) |
| `E09_REJ_ZERO` file-level reject (E09) logged with REJ_CNT=0 instead of the detail count | 1/145 | 04 (1) |
| `TER_FIRST` inbox files processed TER before ADV (changes which duplicate wins under LAST) | 6/145 | 05 (6) |
| `WORKDT_CALENDAR` WORK_DT = calendar date of START (06:00 shift boundary ignored) | 19/145 | 06 (6), 11 (7), 12 (6) |
| `NO_OVR_E` hard-coded enterprise override (OVR_E) not implemented | 6/145 | 08 (4), 12 (2) |
| `SCRAP_ANY_DATE` scrap stickiness also applied for BIN 9 on later/same work days | 4/145 | 09 (4) |
| `NO_ES_EXCL` engineering samples (ES*) not excluded from yield | 12/145 | 03 (4), 09 (4), 12 (4) |
| `ALERT_EMPTY_FILE` ALERT file written (header only) even when there are no alerts | 4/145 | 04 (1), 06 (1), 11 (1), 12 (1) |
| `FOOTER_NO_CRLF` no CRLF after the report trailer record (FlatFileItemWriter default) | 17/145 | 01 (1), 02 (1), 03 (1), 04 (1), 05 (1), 06 (3), 07 (1), 08 (1), 09 (1), 10 (1), 11 (3), 12 (2) |
| `BOM_HEADERMAP` TER columns mapped by header name without stripping the UTF-8 BOM (SERIAL column lost) | 79/145 | 01 (8), 02 (8), 03 (6), 04 (6), 05 (8), 06 (8), 07 (7), 09 (8), 10 (6), 11 (6), 12 (8) |
| `NO_SN_STRIP` serial normalisation without removing the TER 'SN' prefix | 22/145 | 03 (5), 04 (6), 09 (5), 12 (6) |
| `REJECT_UTF8` ADV reject files written in UTF-8 instead of the source encoding (MS949) | 4/145 | 02 (1), 04 (1), 12 (2) |

* `TZ_UTC`
  * 01_basic_flow: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250312.csv, outbox:YIELD_20250312.txt
  * 02_ms949_korean: table:TB_TEST_RESULT
  * 03_ter_csv_format: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250314.txt
  * 04_reject_codes: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250316.txt
  * 05_dup_policy: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250317.csv, outbox:YIELD_20250317.txt
  * 06_shift_boundary_tz: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250317.txt, outbox:YIELD_20250318.txt, outbox:YIELD_20250319.txt
  * 07_retest_attempts: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250319.csv, outbox:YIELD_20250319.txt
  * 09_scrap_es: table:TB_TEST_RESULT
  * 10_yield_trunc_alert: table:TB_TEST_RESULT
  * 11_rerun_noalert: table:TB_TEST_RESULT
  * 12_full_day_mixed: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250325.csv, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt
* `DUP_FIRST`
  * 05_dup_policy: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250317.csv, outbox:YIELD_20250317.txt
  * 12_full_day_mixed: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250325.csv, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt
* `YIELD_ROUND`
  * 02_ms949_korean: table:TB_LOT_YIELD, outbox:YIELD_20250313.txt
  * 03_ter_csv_format: table:TB_LOT_YIELD, outbox:YIELD_20250314.txt
  * 07_retest_attempts: table:TB_LOT_YIELD, outbox:ALERT_20250319.csv, outbox:YIELD_20250319.txt
  * 08_rules_override: table:TB_LOT_YIELD, outbox:ALERT_20250320.csv, outbox:YIELD_20250320.txt
  * 09_scrap_es: table:TB_LOT_YIELD, outbox:ALERT_20250321.csv, outbox:YIELD_20250321.txt
  * 10_yield_trunc_alert: table:TB_LOT_YIELD, outbox:ALERT_20250322.csv, outbox:YIELD_20250322.txt
  * 11_rerun_noalert: table:TB_LOT_YIELD, outbox:ALERT_20250323.csv, outbox:YIELD_20250323.txt
  * 12_full_day_mixed: table:TB_LOT_YIELD, outbox:ALERT_20250325.csv, outbox:YIELD_20250325.txt
* `RETEST_5`
  * 07_retest_attempts: table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250319.csv, outbox:YIELD_20250319.txt
  * 12_full_day_mixed: table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250325.txt
* `ADV_CHARS`
  * 01_basic_flow: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250312.csv, outbox:YIELD_20250312.txt, reject:files
  * 02_ms949_korean: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250313.txt, reject:ADV_20250313_01.dat.rej
  * 04_reject_codes: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250316.txt, reject:ADV_20250316_01.dat.rej
  * 05_dup_policy: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250317.csv, outbox:YIELD_20250317.txt, reject:files
  * 06_shift_boundary_tz: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250317.txt, outbox:YIELD_20250318.txt, reject:files
  * 07_retest_attempts: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250319.csv, outbox:YIELD_20250319.txt, reject:files
  * 08_rules_override: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250320.csv, outbox:YIELD_20250320.txt, reject:files
  * 09_scrap_es: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250321.csv, outbox:YIELD_20250321.txt, reject:files
  * 10_yield_trunc_alert: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250322.csv, outbox:YIELD_20250322.txt, reject:files
  * 11_rerun_noalert: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250323.csv, outbox:YIELD_20250323.txt, outbox:YIELD_20250324.txt, reject:files
  * 12_full_day_mixed: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250325.csv, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt, reject:ADV_20250325_01.dat.rej, reject:ADV_20250325_02.dat.rej
* `TER_CHARCUT`
  * 02_ms949_korean: table:TB_TEST_RESULT
* `TRIM_AFTER_CUT`
  * 02_ms949_korean: table:TB_TEST_RESULT
* `RPT_CHARCUT`
  * 01_basic_flow: outbox:YIELD_20250312.txt
  * 02_ms949_korean: outbox:YIELD_20250313.txt
  * 03_ter_csv_format: outbox:YIELD_20250314.txt
  * 04_reject_codes: outbox:YIELD_20250316.txt
  * 05_dup_policy: outbox:YIELD_20250317.txt
  * 06_shift_boundary_tz: outbox:YIELD_20250317.txt, outbox:YIELD_20250318.txt, outbox:YIELD_20250319.txt
  * 07_retest_attempts: outbox:YIELD_20250319.txt
  * 08_rules_override: outbox:YIELD_20250320.txt
  * 09_scrap_es: outbox:YIELD_20250321.txt
  * 10_yield_trunc_alert: outbox:YIELD_20250322.txt
  * 11_rerun_noalert: outbox:YIELD_20250323.txt, outbox:YIELD_20250324.txt
  * 12_full_day_mixed: outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt
* `TEMP_DOUBLE`
  * 03_ter_csv_format: table:TB_TEST_RESULT
* `NO_STEP_CHECK`
  * 04_reject_codes: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250316.txt, reject:ADV_20250316_01.dat.rej, reject:TER_20250316_01.csv.rej
* `E07_FIRST`
  * 04_reject_codes: reject:ADV_20250316_01.dat.rej
* `E09_REJ_ZERO`
  * 04_reject_codes: table:TB_FILE_LOG
* `TER_FIRST`
  * 05_dup_policy: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250317.csv, outbox:YIELD_20250317.txt
* `WORKDT_CALENDAR`
  * 06_shift_boundary_tz: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250317.txt, outbox:YIELD_20250318.txt, outbox:YIELD_20250319.txt
  * 11_rerun_noalert: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250323.csv, outbox:YIELD_20250323.txt, outbox:YIELD_20250324.txt
  * 12_full_day_mixed: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250325.csv, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt
* `NO_OVR_E`
  * 08_rules_override: table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250320.csv, outbox:YIELD_20250320.txt
  * 12_full_day_mixed: table:TB_DEVICE_BIN, table:TB_LOT_YIELD
* `SCRAP_ANY_DATE`
  * 09_scrap_es: table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250321.csv, outbox:YIELD_20250321.txt
* `NO_ES_EXCL`
  * 03_ter_csv_format: table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250314.csv, outbox:YIELD_20250314.txt
  * 09_scrap_es: table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250321.csv, outbox:YIELD_20250321.txt
  * 12_full_day_mixed: table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250325.csv, outbox:YIELD_20250325.txt
* `ALERT_EMPTY_FILE`
  * 04_reject_codes: outbox:files
  * 06_shift_boundary_tz: outbox:files
  * 11_rerun_noalert: outbox:files
  * 12_full_day_mixed: outbox:files
* `FOOTER_NO_CRLF`
  * 01_basic_flow: outbox:YIELD_20250312.txt
  * 02_ms949_korean: outbox:YIELD_20250313.txt
  * 03_ter_csv_format: outbox:YIELD_20250314.txt
  * 04_reject_codes: outbox:YIELD_20250316.txt
  * 05_dup_policy: outbox:YIELD_20250317.txt
  * 06_shift_boundary_tz: outbox:YIELD_20250317.txt, outbox:YIELD_20250318.txt, outbox:YIELD_20250319.txt
  * 07_retest_attempts: outbox:YIELD_20250319.txt
  * 08_rules_override: outbox:YIELD_20250320.txt
  * 09_scrap_es: outbox:YIELD_20250321.txt
  * 10_yield_trunc_alert: outbox:YIELD_20250322.txt
  * 11_rerun_noalert: outbox:YIELD_20250323.txt, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt
  * 12_full_day_mixed: outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt
* `BOM_HEADERMAP`
  * 01_basic_flow: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250312.csv, outbox:YIELD_20250312.txt, reject:files
  * 02_ms949_korean: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250313.csv, outbox:YIELD_20250313.txt, reject:files
  * 03_ter_csv_format: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250314.txt, reject:files
  * 04_reject_codes: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250316.txt, reject:TER_20250316_01.csv.rej
  * 05_dup_policy: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250317.csv, outbox:YIELD_20250317.txt, reject:files
  * 06_shift_boundary_tz: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250317.txt, outbox:YIELD_20250318.txt, outbox:YIELD_20250319.txt, reject:files
  * 07_retest_attempts: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250319.csv, outbox:YIELD_20250319.txt, reject:files
  * 09_scrap_es: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:files, outbox:ALERT_20250321.csv, outbox:YIELD_20250321.txt, reject:files
  * 10_yield_trunc_alert: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250322.txt, reject:files
  * 11_rerun_noalert: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250323.txt, reject:files
  * 12_full_day_mixed: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250325.csv, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt, reject:TER_20250325_01.csv.rej
* `NO_SN_STRIP`
  * 03_ter_csv_format: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250314.csv, outbox:YIELD_20250314.txt
  * 04_reject_codes: table:TB_TEST_RESULT, table:TB_FILE_LOG, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:YIELD_20250316.txt, reject:TER_20250316_01.csv.rej
  * 09_scrap_es: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250321.csv, outbox:YIELD_20250321.txt
  * 12_full_day_mixed: table:TB_TEST_RESULT, table:TB_DEVICE_BIN, table:TB_LOT_YIELD, outbox:ALERT_20250325.csv, outbox:YIELD_20250324.txt, outbox:YIELD_20250325.txt
* `REJECT_UTF8`
  * 02_ms949_korean: reject:ADV_20250313_01.dat.rej
  * 04_reject_codes: reject:ADV_20250316_01.dat.rej
  * 12_full_day_mixed: reject:ADV_20250325_01.dat.rej, reject:ADV_20250325_02.dat.rej
