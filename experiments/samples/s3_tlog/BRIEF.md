# Brief: build experiment subject S3 "tlog-batch" (synthetic LEGACY Java/Spring batch data-processing system)

You are building a realistic *legacy* system that will be used as an experiment subject for "AI-driven redevelopment".
Later, other AI agents will (a) analyze the legacy code + materials to produce redevelopment data, and (b) re-implement
the system in a modern stack WITHOUT seeing the hidden directory. A black-box harness will then measure behavioral fidelity.
So: legacy behavior must be deterministic and fully exercised by hidden fixtures; tribal knowledge must NOT leak into
legacy code or materials.

Work ONLY under: $SP/samples/s3_tlog/   (SP=/tmp/claude-0/-home-user-Restructuring/9155ba45-e573-59a1-b70d-b72c0c21626d/scratchpad)
  legacy/     the legacy project (what a company would hand over)
  materials/  documents a company would hand over (Korean)
  hidden/     NEVER shown to analyzers/redevelopers: tribal knowledge, fixtures, harness
Do NOT touch /home/user/Restructuring.

## Domain
"SSD 양산 테스트 로그 수집·판정·집계 배치" — an internal system (written ~2015-2017 by several developers) that ingests
SSD manufacturing tester logs from two tester vendors, judges a final BIN per device, aggregates lot yield, and
produces report files consumed by a downstream MES.

## Legacy tech stack (keep it legacy-looking)
- Java source level 8 (maven.compiler.release=8), must build & run on the installed JDK 21 (`mvn` at /opt/maven/bin/mvn).
- Spring Framework 5.3.x, Spring Batch 4.3.x with XML job configuration (<batch:job>, <batch:step>, chunk, listeners),
  MyBatis 3.5.x + mybatis-spring 2.0.x with XML mapper files, plus ONE older DAO written with JdbcTemplate (two eras mixed),
  commons-lang 2.6, commons-io, slf4j+logback. H2 2.2.224 JDBC driver; the DB is reached via JDBC URL from env (TCP server).
- Launched through Spring Batch's CommandLineJobRunner from a shell script. Build: `build.sh` -> `mvn -q -B package`
  producing target/tlog-batch.jar + target/lib/*.jar (maven-dependency-plugin copy-dependencies) — classic legacy layout.
- Spring Batch metadata tables: created by the app at startup if absent (jdbc:initialize-database with
  ignore-failures or equivalent). Legacy run script appends a `run.ts=<epoch millis>` job parameter so the same BIZ_DATE can be re-run.

## Operations contract (this IS the external interface; ops & harness use only this)
- `bin/run_job.sh <JOB_ID> <BIZ_DATE yyyyMMdd>`; JOB_ID in {LOAD, JUDGE, YIELD, PURGE}. Exit 0 = success, non-zero = failure.
- Env: TLOG_HOME (subdirs inbox/ outbox/ reject/ archive/), TLOG_DB_URL, TLOG_DB_USER (default sa), TLOG_DB_PASSWORD (default empty),
  JAVA_OPTS (passed verbatim to the JVM). The script must NOT itself set timezone or tlog.* properties.
- Business tables are pre-created by the DBA (DDL lives in legacy/sql/ddl.sql). Master data (products, bin rules, bin codes,
  sys config) is maintained by another team: the repo has DDL and at most a tiny dev seed, NOT the production master data.

## Jobs and business rules (implement exactly; these define golden behavior)
### LOAD (tlogLoadJob)
Inputs in $TLOG_HOME/inbox whose filename date == BIZ_DATE:
- ADV_<yyyyMMdd>_<NN>.dat : fixed-length records, **MS949** encoding, CRLF. Byte-offset layout (offsets are in BYTES of MS949):
  record type(1: H header / D detail / T trailer), serial(16, right-padded), lot id(10), product code(8), test step(4: "FT1 ","BI  ","FT2 "),
  start(14 yyyyMMddHHmmss, local plant time), end(14), tester id(8), operator name(10 BYTES MS949 — Korean = 2 bytes/char),
  result(2: "P ","F ","A "), read MB/s(6 digits, implied 1 decimal), write MB/s(6, implied 1 decimal), latency us(6), bad blocks(5),
  ecc corrected(8), max temp °C(4 signed like "+072"/"-005"), fw version(8), filler. Header: file creation info. Trailer: detail count;
  if trailer count != number of D records -> whole file rejected (E09) and nothing from it loaded.
- TER_<yyyyMMdd>_<NN>.csv : UTF-8 with OPTIONAL BOM, header row, comma separated, fields may be double-quoted (with commas inside),
  may end with trailer line `#EOF,<count>` (validate if present -> E09 on mismatch). Columns: SERIAL,LOT,PRODUCT,STEP,START_UTC,END_UTC
  (ISO-8601 'Z'),TESTER,OPERATOR,RESULT(PASS/FAIL/ABORT),READ_MBPS,WRITE_MBPS,LAT_US,BAD_BLK,ECC_CNT,TEMP_F(Fahrenheit),FW.
Normalization: serial trimmed, uppercased, leading "SN" prefix stripped (TER sometimes has it), '-' removed; results -> P/F/A;
TEMP_F -> °C = (F-32)*5/9 rounded HALF_UP to integer; all times converted to KST; WORK_DT (production day) derived from START in
plant time: if hour < 06 -> previous calendar day (shift boundary 06:00).
**TRAP TZ (tribal):** implement WORK_DT/ADV parsing with the JVM *default* timezone (SimpleDateFormat/Calendar without explicit TZ)
and TER conversion as "parse UTC, add 9h hack, format with default TZ" or similar, so results are only correct when the JVM default
timezone is Asia/Seoul. Production runs with -Duser.timezone=Asia/Seoul set in a server profile that is NOT in the repo.
Validation -> reject file $TLOG_HOME/reject/<original file name>.rej, one line per rejected record: `<lineNo>|<errCode>|<raw record>`:
E01 bad length/column count, E02 missing serial, E03 bad timestamp, E04 end < start, E05 unknown result, E06 numeric error,
E07 unknown product (not in TB_PRODUCT or USE_YN='N'), E09 trailer mismatch (whole-file; write one line `0|E09|<file name>`).
Duplicates: same (SERIAL, STEP, START_DTM) already in TB_TEST_RESULT (or earlier in same run) -> policy from
`System.getProperty("tlog.dup.policy","FIRST")` read deep in the code: FIRST = keep existing / ignore new, LAST = overwrite with new.
**TRAP DUP (tribal):** production uses LAST (set in the hidden server profile). Code default stays FIRST.
Valid records -> TB_TEST_RESULT. Per file -> TB_FILE_LOG (file name, vendor, total, loaded, rejected, dup, status). Processed files
(including fully rejected) moved to $TLOG_HOME/archive/<BIZ_DATE>/ (move failure logged and swallowed).
### JUDGE (binJudgeJob) for WORK_DT = BIZ_DATE, per device (SERIAL):
a) per (SERIAL, STEP): attempts ordered by START_DTM; only the first 3 attempts count (MAX_RETEST=3; a Constants class ALSO
   defines MAX_RETEST=5 that is unused — inconsistent duplicate constant); effective attempt = last counted attempt.
b) any effective attempt result 'A' -> BIN 8 (rule id 'ABORT').
c) else evaluate TB_BIN_RULE rows (USE_YN='Y') applicable to the product (PROD_CD exact or '*'), ordered by PRIORITY asc, then
   specific product before '*', then BIN_NO desc; item in {READ_MBPS, WRITE_MBPS, LAT_US, BAD_BLK, ECC_CNT, TEMP_MAX} evaluated over
   effective attempts (READ/WRITE use MIN across steps, LAT/BAD/ECC/TEMP use MAX), operator in {<,<=,>,>=}; first match wins.
d) hard-coded override BEFORE rules: product code starting with 'E' (enterprise) and max BAD_BLK > 20 -> BIN 5 (rule id 'OVR_E'),
   with a Korean comment like "임시 조치 2016.03 고객 클레임 대응 - 추후 룰테이블로 이관 예정".
e) no rule matched: all effective attempts 'P' -> BIN 1 ('DEFAULT'); otherwise BIN 7 ('DEFAULT_F').
f) scrap stickiness: if TB_DEVICE_BIN already has BIN 9 for the serial (any earlier WORK_DT), keep BIN 9 ('SCRAP_KEEP').
g) serials starting with 'ES' (engineering samples) are judged normally but EXCL_YN='Y'.
Output: MERGE into TB_DEVICE_BIN keyed by (SERIAL, WORK_DT): PROD_CD, LOT_ID, BIN_NO, RULE_ID, EXCL_YN (no volatile timestamps in
compared columns — if you add audit timestamps, list them in the harness as ignored).
### YIELD (yieldSummaryJob) for WORK_DT = BIZ_DATE:
group TB_DEVICE_BIN (EXCL_YN='N') by (PROD_CD, LOT_ID): IN_QTY, PASS_QTY (bins with TB_BIN_CODE.PASS_YN='Y'), YIELD_PCT =
**truncated** to 2 decimals (floor) — while the code comment and the design doc both say 반올림 (rounding) (TRAP DOC-vs-CODE: code
is truth, MES depends on truncation), per-BIN counts BIN1..BIN9. Delete rows for WORK_DT then insert into TB_LOT_YIELD (re-run safe).
Report $TLOG_HOME/outbox/YIELD_<BIZ_DATE>.txt in **MS949**, CRLF, fixed width: H record (BIZ_DATE + system name + detail count),
D records sorted by PROD_CD, LOT_ID (PROD_CD 8, LOT_ID 10, PROD_NM 20 BYTES MS949 truncated without splitting a 2-byte char and
space-padded, IN_QTY 7 zero-padded, PASS_QTY 7, YIELD like 099.50, ALERT Y/N), T record (detail count 7 + sum(PASS_QTY) mod 10^7).
Alert: lots with YIELD_PCT < TB_PRODUCT.ALERT_YIELD and IN_QTY >= 10 (hard-coded minimum) -> $TLOG_HOME/outbox/ALERT_<BIZ_DATE>.csv
(UTF-8, header row); legacy quirk: file is NOT created when there are no alerts.
### PURGE (purgeJob): delete TB_TEST_RESULT rows older than TB_SYS_CONFIG 'RETENTION_DAYS' (default 90) relative to BIZ_DATE.
(Tribal: PURGE is not scheduled in production; DBA drops partitions. Not part of hidden fixtures.)

## Legacy smells (make it realistic, but behavior must stay correct & deterministic per the rules above)
Korean comments (some outdated or wrong), magic numbers, a static `CommonUtil` god class, StringBuffer, static SimpleDateFormat,
copy-pasted parsing between vendors, a dead `AdvParserV1` class not wired anywhere, commented-out blocks, inconsistent naming,
swallowed exceptions, MyBatis + JdbcTemplate mixed, the duplicated inconsistent constant, a short OUTDATED README.
Target size: roughly 3,000–5,000 lines total (Java + XML + SQL + scripts). Do not exceed ~6,000.

## Materials (Korean, realistic, partially outdated) in materials/
- TLOG_배치_설계서_v1.3.docx (python-docx): overview, architecture, job descriptions, data flow, ops; deliberately outdated in places:
  says yield is 반올림, says retest limit is 5, mentions an old separate ALERT job later merged into YIELD.
- 인터페이스_정의서.xlsx (openpyxl): sheets for ADV layout (offset/len/type/desc), TER columns, YIELD report layout, ALERT csv,
  reject file format, error codes (leave one error code undocumented).
- 운영_가이드.txt: cron schedule, directories, how to re-run, contacts; must NOT reveal JAVA_OPTS / timezone / dup policy.

## Hidden (hidden/)
- oracle_knowledge.md (Korean): everything a long-time operator/developer knows, for a simulated human who answers questions:
  production JAVA_OPTS (`-Duser.timezone=Asia/Seoul -Dtlog.dup.policy=LAST -Xmx2g`, set in /etc/profile.d/tlog.sh), truncation is
  intended (MES compatibility), design doc is outdated where it conflicts with code (code is truth), PURGE unused, meaning of BINs,
  report must stay byte-identical (MS949, CRLF), any other facts you think an operator would know; and guidance to answer
  "모르겠습니다" when something is not covered.
- provided_on_request/: what the human hands over if asked: samples/ (2 ADV + 2 TER realistic sample files for some date) and
  master_data/ (CSV exports of TB_PRODUCT, TB_BIN_RULE, TB_BIN_CODE, TB_SYS_CONFIG). Must be DIFFERENT data from fixtures.
- fixtures/<NN_name>/: seed.sql (master data + pre-existing rows e.g. earlier scrap), inbox/ files, jobs.txt (lines `JOB BIZ_DATE`
  executed in order), expected/ (business table dumps as CSV sorted by key, and outbox/ reject/ files + archive listing).
  10–12 fixtures covering: basic flow; MS949 Korean names/product names byte truncation; BOM+quoted CSV+#EOF+SN prefix; every reject
  code incl. trailer mismatch; duplicates across files (policy LAST); 06:00 shift boundary incl. TER UTC crossing midnight (TZ trap);
  retests with 4+ attempts; rule priority/wildcard/tie-break + enterprise override; scrap stickiness; truncation vs rounding cases
  (e.g. 2/3 -> 66.66) + alert threshold + min sample 10 + no-alert-no-file; ES exclusion; re-run idempotency (YIELD twice).
- run_hidden_tests.sh <app_dir> [--java-opts "<opts>"] [--out report.json]: builds via <app_dir>/build.sh, starts an H2 TCP server
  using the harness's own h2 jar (from ~/.m2), per fixture: fresh in-memory DB (`jdbc:h2:tcp://localhost:<port>/mem:<fixture>;MODE=Oracle;DB_CLOSE_DELAY=-1`)
  initialized with hidden copy of DDL + seed.sql, fresh TLOG_HOME, copy inbox, run each job line via <app_dir>/bin/run_job.sh with
  JAVA_OPTS = the --java-opts value (DEFAULT EMPTY — a redeveloped app must show production behavior out of the box), dump
  business tables (ignore volatile columns), collect outbox/reject files (byte compare) and archive listing, compare with expected.
  Output JSON: per fixture, per check pass/fail with short diff, and totals (checks passed / total). Must work for ANY implementation
  that honors the ops contract (it may be Spring Boot 3 etc.), so use only the contract.
- Generate expected/ by running the LEGACY app with production JAVA_OPTS (`-Duser.timezone=Asia/Seoul -Dtlog.dup.policy=LAST`).
  Then verify: harness on legacy with prod opts = 100% pass, twice (determinism). Also run legacy with EMPTY opts and record which
  checks fail (proves the traps bite) in TRAPS.md.
- TRAPS.md: every trap (TZ, DUP, doc-vs-code truncation, doc-vs-code retest limit, MS949 byte truncation, BOM, ...) and which fixtures/checks it affects.

## Final report (your reply)
Paths, LOC counts, how to build/run, fixture list, harness results (legacy+prod opts, legacy+empty opts), any caveats.
