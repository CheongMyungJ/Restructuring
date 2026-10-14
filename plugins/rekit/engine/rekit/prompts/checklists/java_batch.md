## Domain checklist: Java / Spring data-processing & batch
Capture explicitly when present:
- **Job topology**: jobs, steps, flows/deciders, tasklets vs chunk steps (reader/processor/writer), commit interval,
  partitioning/multi-threading, listeners, job parameters (names, formats, defaults, incrementers), restart/re-run
  semantics, idempotency, how a re-run of the same date behaves.
- **Error handling**: skip/retry/no-rollback policies and limits, exception classes, what is logged/rejected/counted,
  exit codes/exit statuses, partial-failure behavior, transaction boundaries & rollback scope.
- **Data contracts**: every input/output file: naming pattern, encoding (UTF-8/MS949/EUC-KR, BOM), line endings, record
  layouts (byte offsets for fixed length, delimiter/quoting for CSV), header/trailer rules, sorting; every DB table
  touched: columns, keys, every SQL/MyBatis statement's exact semantics (WHERE, JOIN, ORDER BY, GROUP BY, NVL/DECODE,
  MERGE/upsert, sequences, locking, batch size), dynamic SQL conditions; messages/queues/APIs.
- **Numbers, time, text**: BigDecimal scale & RoundingMode (HALF_UP vs truncation), integer division, overflow;
  date/time parsing/formatting patterns, time zone used (explicit vs JVM default!), business-day/shift boundaries,
  calendar tables; string trimming/padding/case, byte-length vs char-length for multibyte text.
- **Configuration**: Spring profiles, property files, system properties (`System.getProperty`) and env vars with
  defaults — and which values production uses; scheduler (cron/Quartz/external), JNDI/datasource settings.
- **Framework semantics that leak into behavior**: bean scopes (step scope), MyBatis result mapping/null handling,
  JdbcTemplate batch updates, Spring Batch metadata tables & job instance uniqueness, ordering of listeners.
- **Operations**: run scripts, directory layout, file archiving/moving, retention/purge, monitoring/alerts, logs that
  other systems parse.
