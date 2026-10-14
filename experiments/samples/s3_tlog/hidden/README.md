# hidden/ — S3 tlog-batch (never shown to analyzers / re-developers)

| Path | Purpose |
|---|---|
| `run_hidden_tests.sh` | Black-box harness entry point (wraps `harness/harness.py`) |
| `harness/harness.py` | Harness: build, H2 TCP server, per-fixture DB + TLOG_HOME, run jobs, dump, compare, JSON report |
| `harness/DbDump.java` | Business-table dumper (compiled on the fly with `javac`; implementation-neutral number/NULL formatting) |
| `harness/ddl.sql` | Hidden copy of the DBA DDL (identical to `legacy/sql/ddl.sql`) used to create every fixture DB |
| `fixtures/NN_name/` | `desc.txt`, `seed.sql`, `inbox/`, `jobs.txt`, `expected/` |
| `oracle_knowledge.md` | Tribal knowledge for the simulated operator (Korean) |
| `provided_on_request/` | What the operator hands over when asked: `samples/` (2024-11-07) and `master_data/` CSV exports |
| `TRAPS.md` | Trap catalogue, which fixtures/checks each trap affects, legacy results with prod / empty JAVA_OPTS |
| `reports/` | Harness JSON reports of the legacy app (prod opts x2, empty, TZ-only, DUP-only), no-op baseline, trap matrix |
| `tools/` | Generators and verification tools (see below) |

## Running the harness

```sh
hidden/run_hidden_tests.sh <app_dir> [--java-opts "<opts>"] [--out report.json]
                                     [--fixtures 01,05] [--work DIR | --keep-work] [--no-build] [--job-timeout SEC]
```

* Uses only the ops contract: `<app_dir>/build.sh`, `<app_dir>/bin/run_job.sh <JOB_ID> <BIZ_DATE>`,
  env `TLOG_HOME`, `TLOG_DB_URL`, `TLOG_DB_USER=sa`, `TLOG_DB_PASSWORD=` (empty), `JAVA_OPTS`.
* `JAVA_OPTS` defaults to **empty**: a re-developed app must show production behaviour out of the box.
* Hermetic job environment: `TZ=UTC`, `LANG=LC_ALL=C.UTF-8`; `-Duser.timezone`, `-Dtlog.*`, locale and
  `file.encoding` flags are stripped from `JAVA_TOOL_OPTIONS` / `_JAVA_OPTIONS` / `JDK_JAVA_OPTIONS`.
* Per fixture: fresh in-memory DB `jdbc:h2:tcp://localhost:<port>/mem:<fixture>;MODE=Oracle;DB_CLOSE_DELAY=-1`
  on the harness' own H2 2.2.224 server (jar from `~/.m2`, or `H2_JAR=`), initialised with `harness/ddl.sql` + `seed.sql`;
  fresh `TLOG_HOME` with `inbox/ outbox/ reject/ archive/`; each line of `jobs.txt` executed in order.
* Checks per fixture (145 in total):
  `exit:codes` (zero / non-zero of every job line), `table:TB_TEST_RESULT|TB_FILE_LOG|TB_DEVICE_BIN|TB_LOT_YIELD`,
  `outbox:files` + byte-compare of every expected outbox file, `reject:files` + byte-compare of every expected reject file,
  `archive:listing`, `inbox:listing` (files left in inbox).
* Ignored (volatile) columns: `TB_TEST_RESULT.REG_DTM, UPD_DTM`, `TB_FILE_LOG.FILE_SEQ, LOAD_DTM`,
  `TB_DEVICE_BIN.REG_DTM, UPD_DTM`, `TB_LOT_YIELD.REG_DTM`. Rows are compared as sorted CSV
  (NULL = empty, numbers with trailing zeros stripped). Spring Batch / other meta tables are not compared.
* Requirements: bash, python3 (stdlib only), JDK 17+ (`java`, `javac`), Maven (only for the app build).
* Exit code 0 when all checks pass, 1 otherwise. JSON: per fixture, per check pass/fail + short diff, and totals.
* Baseline: an app that builds, exits 0 for every job and does nothing scores 20/145.

## Tools

| Tool | What it does |
|---|---|
| `tools/gen_fixtures.py` | Regenerates fixture inputs (`seed.sql`, `inbox/`, `jobs.txt`, `desc.txt`); removes `expected/` |
| `tools/record_expected.sh [legacy_dir]` | Runs the LEGACY app with production JAVA_OPTS through the harness and stores the outputs as `expected/` |
| `tools/refmodel.py` | Independent Python re-implementation of the rules: `refmodel.py` verifies every `expected/` (must be 145/145); `--matrix` prints the per-trap impact matrix; `--variants A,B --vs report.json` compares a naive variant with a real harness report |
| `tools/gen_materials.py` | Regenerates `materials/` (docx, xlsx, txt) |
| `tools/gen_provided.py` | Regenerates `provided_on_request/` |
| `tools/fxlib.py` | Shared ADV/TER/seed builders |

Regeneration order: `gen_fixtures.py` → `record_expected.sh` → `refmodel.py` (must print OK for all fixtures).
