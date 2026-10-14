#!/bin/bash
#======================================================================
# TLOG hidden black-box test harness
#
#   run_hidden_tests.sh <app_dir> [--java-opts "<opts>"] [--out report.json]
#                       [--fixtures 01_x,02_y] [--work DIR | --keep-work] [--no-build]
#                       [--job-timeout SEC]
#
#   <app_dir> must honour the ops contract only:
#     <app_dir>/build.sh, <app_dir>/bin/run_job.sh <JOB_ID> <BIZ_DATE>
#     env TLOG_HOME / TLOG_DB_URL / TLOG_DB_USER / TLOG_DB_PASSWORD / JAVA_OPTS
#
#   JAVA_OPTS defaults to EMPTY: an application must show production behaviour out of the box.
#   Requires: bash, python3 (stdlib only), a JDK 17+ (java + javac), H2 2.2.224 jar in ~/.m2
#   (or H2_JAR=/path/to/h2-2.2.224.jar).
#   Exit code: 0 = all checks passed, 1 = some check failed.
#======================================================================
HERE=$(cd "$(dirname "$0")" && pwd)
exec python3 "$HERE/harness/harness.py" "$@"
