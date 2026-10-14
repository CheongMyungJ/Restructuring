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
