# Task: redevelop a legacy Java/Spring batch data-processing system

{{AVAILABLE}}

Re-implement the system in `./new/` as **Spring Boot 3.x + Spring Batch 5.x, Java 21, Maven**, with clean,
maintainable code.

Hard requirements:
1. Keep the **operations contract** exactly: the run script interface (`new/bin/run_job.sh <JOB_ID> <BIZ_DATE>`), the
   environment variables, directory layout, input/output/reject file names, formats, encodings and exit codes.
2. Keep the **database contract**: business tables are pre-created by the DBA with the existing schema (do NOT create
   or alter business tables); connect using the same environment variables as today. Any framework metadata tables
   your implementation needs must be created by the application itself.
3. The current **production behavior must be the default**: in production the new system will be started with ONLY
   `TLOG_HOME`, `TLOG_DB_URL`, `TLOG_DB_USER`, `TLOG_DB_PASSWORD` set and `JAVA_OPTS` empty, on servers whose OS
   timezone is not guaranteed.
4. Provide `new/build.sh` that builds everything needed by `new/bin/run_job.sh` (Maven is available offline-capable via
   ~/.m2 and Maven Central).
5. Write your own tests and make them pass.

Work fully autonomously until done; do not ask questions. Record important decisions/assumptions in `new/NOTES.md`.
Only use files inside the current directory as information sources.
