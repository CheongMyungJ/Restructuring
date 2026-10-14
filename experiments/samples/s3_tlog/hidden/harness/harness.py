#!/usr/bin/env python3
"""
TLOG hidden black-box harness.

Runs every fixture in hidden/fixtures against an application directory that honors the
operations contract:

  <app_dir>/build.sh                         build the application
  <app_dir>/bin/run_job.sh <JOB_ID> <DATE>   run one job (exit 0 = success)
  env: TLOG_HOME, TLOG_DB_URL, TLOG_DB_USER, TLOG_DB_PASSWORD, JAVA_OPTS

Nothing else about the implementation is assumed (works for the legacy Spring Batch app and
for any re-implementation, e.g. Spring Boot 3).

Per fixture:
  1. fresh in-memory H2 database on the harness' own H2 TCP server
       jdbc:h2:tcp://localhost:<port>/mem:<fixture>;MODE=Oracle;DB_CLOSE_DELAY=-1
     initialised with the hidden copy of the DDL (harness/ddl.sql) + fixture seed.sql
  2. fresh TLOG_HOME (inbox/ outbox/ reject/ archive/), fixture inbox copied in
  3. each line of jobs.txt executed via run_job.sh with JAVA_OPTS = --java-opts (default EMPTY)
  4. business tables dumped (volatile columns ignored), outbox/ and reject/ files collected,
     archive/ and inbox/ listings taken
  5. compared with fixture expected/ -> checks

Hermetic job environment: TZ=UTC, LANG=LC_ALL=C.UTF-8, and -Duser.timezone / -Dtlog.* /
locale / file.encoding flags are stripped from JAVA_TOOL_OPTIONS, _JAVA_OPTIONS and
JDK_JAVA_OPTIONS, so production behaviour must come from the application itself.
"""

import argparse
import datetime as _dt
import difflib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIDDEN = HERE.parent
FIXTURES_DIR = HIDDEN / "fixtures"
DDL_FILE = HERE / "ddl.sql"
DUMPER_SRC = HERE / "DbDump.java"
H2_VERSION = "2.2.224"
HARNESS_VERSION = "1.0"

# Compared columns per business table (key columns first). Ignored (volatile) columns:
#   TB_TEST_RESULT.REG_DTM, TB_TEST_RESULT.UPD_DTM
#   TB_FILE_LOG.FILE_SEQ (sequence value), TB_FILE_LOG.LOAD_DTM
#   TB_DEVICE_BIN.REG_DTM, TB_DEVICE_BIN.UPD_DTM
#   TB_LOT_YIELD.REG_DTM
TABLES = [
    ("TB_TEST_RESULT", ["SERIAL", "STEP_CD", "START_DTM", "END_DTM", "WORK_DT", "LOT_ID", "PROD_CD",
                        "TESTER_ID", "OPER_NM", "RESULT_CD", "READ_MBPS", "WRITE_MBPS", "LAT_US",
                        "BAD_BLK", "ECC_CNT", "MAX_TEMP_C", "FW_VER", "VENDOR_CD", "SRC_FILE_NM"]),
    ("TB_FILE_LOG", ["FILE_NM", "VENDOR_CD", "BIZ_DT", "TOTAL_CNT", "LOAD_CNT", "REJ_CNT", "DUP_CNT",
                     "STATUS_CD"]),
    ("TB_DEVICE_BIN", ["SERIAL", "WORK_DT", "PROD_CD", "LOT_ID", "BIN_NO", "RULE_ID", "EXCL_YN"]),
    ("TB_LOT_YIELD", ["WORK_DT", "PROD_CD", "LOT_ID", "IN_QTY", "PASS_QTY", "YIELD_PCT",
                      "BIN1_QTY", "BIN2_QTY", "BIN3_QTY", "BIN4_QTY", "BIN5_QTY", "BIN6_QTY",
                      "BIN7_QTY", "BIN8_QTY", "BIN9_QTY", "ALERT_YN"]),
]

STRIP_JVM_FLAGS = re.compile(
    r"^-D(user\.timezone|tlog\.[^=]*|user\.language|user\.country|user\.region|file\.encoding)(=.*)?$")
JVM_ENV_VARS = ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS")

MAX_DIFF_LINES = 30
MAX_DIFF_CHARS = 4000


# --------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------

def log(msg):
    print(msg, flush=True)


def java_tool(name):
    jh = os.environ.get("JAVA_HOME")
    if jh and (Path(jh) / "bin" / name).exists():
        return str(Path(jh) / "bin" / name)
    found = shutil.which(name)
    if not found:
        raise SystemExit("harness: '%s' not found (need a JDK 17+ on PATH or JAVA_HOME)" % name)
    return found


def find_h2_jar():
    env = os.environ.get("H2_JAR")
    if env and Path(env).is_file():
        return Path(env)
    jar = Path.home() / ".m2" / "repository" / "com" / "h2database" / "h2" / H2_VERSION / ("h2-%s.jar" % H2_VERSION)
    if jar.is_file():
        return jar
    mvn = os.environ.get("MVN") or ("/opt/maven/bin/mvn" if Path("/opt/maven/bin/mvn").exists() else shutil.which("mvn"))
    if mvn:
        subprocess.run([mvn, "-q", "-B", "dependency:get", "-Dartifact=com.h2database:h2:%s" % H2_VERSION],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if jar.is_file():
        return jar
    raise SystemExit("harness: H2 %s jar not found (set H2_JAR)" % H2_VERSION)


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_port(port, timeout=30.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def sanitize_jvm_env(value):
    kept, dropped = [], []
    for tok in value.split():
        (dropped if STRIP_JVM_FLAGS.match(tok) else kept).append(tok)
    return " ".join(kept), dropped


def job_env(java_opts, tlog_home, db_url):
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("TLOG_"):
            del env[k]
    stripped = []
    for var in JVM_ENV_VARS:
        if var in env:
            kept, dropped = sanitize_jvm_env(env[var])
            stripped.extend(dropped)
            if kept:
                env[var] = kept
            else:
                del env[var]
    env["TZ"] = "UTC"
    env["LANG"] = "C.UTF-8"
    env["LC_ALL"] = "C.UTF-8"
    env["TLOG_HOME"] = str(tlog_home)
    env["TLOG_DB_URL"] = db_url
    env["TLOG_DB_USER"] = "sa"
    env["TLOG_DB_PASSWORD"] = ""
    env["JAVA_OPTS"] = java_opts
    return env, stripped


def run_cmd(cmd, cwd=None, env=None, log_file=None, timeout=None):
    """Run a command in its own process group; returns (rc, seconds). rc=-999 on timeout."""
    t0 = time.time()
    with open(log_file, "ab") if log_file else open(os.devnull, "wb") as out:
        try:
            p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            out.write(("harness: cannot start %s: %s\n" % (cmd, e)).encode())
            return -998, 0.0
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, 9)
            except OSError:
                pass
            p.wait()
            out.write(b"\nharness: TIMEOUT - process group killed\n")
            rc = -999
    return rc, time.time() - t0


def list_files(root):
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*") if p.is_file())


def read_jobs(fx):
    jobs = []
    for line in (fx / "jobs.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            jobs.append(line.split())
    return jobs


def truncate(text):
    lines = text.splitlines()
    if len(lines) > MAX_DIFF_LINES:
        lines = lines[:MAX_DIFF_LINES] + ["... (%d more diff lines)" % (len(lines) - MAX_DIFF_LINES)]
    text = "\n".join(lines)
    if len(text) > MAX_DIFF_CHARS:
        text = text[:MAX_DIFF_CHARS] + "\n... (truncated)"
    return text


def decode_guess(data):
    for enc in ("utf-8", "cp949"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1"), "latin-1"


def text_diff(exp_lines, act_lines):
    diff = difflib.unified_diff(exp_lines, act_lines, "expected", "actual", n=0, lineterm="")
    return truncate("\n".join(diff))


def bytes_diff(exp, act):
    if exp == act:
        return ""
    off = next((i for i in range(min(len(exp), len(act))) if exp[i] != act[i]), min(len(exp), len(act)))
    head = "size expected=%d actual=%d, first difference at byte %d" % (len(exp), len(act), off)
    exp_txt, exp_enc = decode_guess(exp)
    act_txt, act_enc = decode_guess(act)
    if exp_enc != act_enc:
        head += " (encoding looks like expected=%s actual=%s)" % (exp_enc, act_enc)
    exp_lines = [repr(l) for l in exp_txt.splitlines(keepends=True)]
    act_lines = [repr(l) for l in act_txt.splitlines(keepends=True)]
    return truncate(head + "\n" + text_diff(exp_lines, act_lines))


# --------------------------------------------------------------------------------------------
# fixture execution
# --------------------------------------------------------------------------------------------

class Env:
    def __init__(self, args, work):
        self.args = args
        self.work = work
        self.java = java_tool("java")
        self.h2_jar = find_h2_jar()
        self.classes = work / "_classes"
        self.port = None
        self.server = None

    def compile_dumper(self):
        self.classes.mkdir(parents=True, exist_ok=True)
        rc = subprocess.run([java_tool("javac"), "-nowarn", "-d", str(self.classes), str(DUMPER_SRC)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if rc.returncode != 0:
            raise SystemExit("harness: cannot compile DbDump.java\n" + rc.stdout.decode(errors="replace"))

    def start_h2(self):
        self.port = free_port()
        logf = open(self.work / "_h2_server.log", "wb")
        env = dict(os.environ)
        env["TZ"] = "UTC"
        self.server = subprocess.Popen(
            [self.java, "-cp", str(self.h2_jar), "org.h2.tools.Server", "-tcp", "-tcpPort", str(self.port),
             "-ifNotExists"], stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=env, start_new_session=True)
        if not wait_port(self.port):
            self.stop_h2()
            raise SystemExit("harness: H2 TCP server did not start (see %s)" % (self.work / "_h2_server.log"))

    def stop_h2(self):
        if self.server is not None:
            try:
                os.killpg(self.server.pid, 15)
            except OSError:
                pass
            try:
                self.server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.server.pid, 9)
                except OSError:
                    pass
            self.server = None

    def db_url(self, name):
        return "jdbc:h2:tcp://localhost:%d/mem:%s;MODE=Oracle;DB_CLOSE_DELAY=-1" % (self.port, name)

    def run_sql(self, url, script, log_file):
        rc, _ = run_cmd([self.java, "-cp", str(self.h2_jar), "org.h2.tools.RunScript", "-url", url,
                         "-user", "sa", "-password", "", "-script", str(script)], log_file=log_file,
                        timeout=300)
        return rc

    def dump(self, url, out_dir, log_file):
        specs = ["%s=%s" % (t, ",".join(cols)) for t, cols in TABLES]
        cp = os.pathsep.join([str(self.h2_jar), str(self.classes)])
        rc, _ = run_cmd([self.java, "-cp", cp, "DbDump", url, "sa", "", str(out_dir)] + specs,
                        log_file=log_file, timeout=300)
        return rc


def run_fixture(env, fx, app_dir):
    name = fx.name
    fdir = env.work / name
    if fdir.exists():
        shutil.rmtree(fdir)
    logs = fdir / "logs"
    home = fdir / "home"
    actual = fdir / "actual"
    for d in (logs, actual, home / "inbox", home / "outbox", home / "reject", home / "archive"):
        d.mkdir(parents=True, exist_ok=True)
    src_inbox = fx / "inbox"
    if src_inbox.is_dir():
        for p in sorted(src_inbox.iterdir()):
            if p.is_file():
                shutil.copyfile(p, home / "inbox" / p.name)

    db_name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    url = env.db_url(db_name)
    errors = []
    if env.run_sql(url, DDL_FILE, logs / "00_ddl.log") != 0:
        errors.append("DDL initialisation failed")
    seed = fx / "seed.sql"
    if seed.is_file() and env.run_sql(url, seed, logs / "00_seed.log") != 0:
        errors.append("seed.sql failed")

    jenv, stripped = job_env(env.args.java_opts, home, url)
    script = app_dir / "bin" / "run_job.sh"
    results = []
    for i, job in enumerate(read_jobs(fx), 1):
        lf = logs / ("%02d_%s.log" % (i, "_".join(job)))
        rc, secs = run_cmd(["bash", str(script)] + job, cwd=str(app_dir), env=jenv, log_file=lf,
                           timeout=env.args.job_timeout)
        results.append({"line": " ".join(job), "rc": rc, "seconds": round(secs, 1)})

    if env.dump(url, actual / "tables", logs / "99_dump.log") != 0:
        errors.append("table dump failed")
    for sub in ("outbox", "reject"):
        for rel in list_files(home / sub):
            dst = actual / sub / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(home / sub / rel, dst)
    (actual / "archive_listing.txt").write_text("".join(x + "\n" for x in list_files(home / "archive")),
                                                encoding="utf-8")
    (actual / "inbox_listing.txt").write_text("".join(x + "\n" for x in list_files(home / "inbox")),
                                              encoding="utf-8")
    (actual / "exit_codes.txt").write_text(
        "".join("%d\t%s\t%d\n" % (i, r["line"], r["rc"]) for i, r in enumerate(results, 1)), encoding="utf-8")
    return actual, results, errors, stripped


# --------------------------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------------------------

def check(cid, ok, diff="", **extra):
    c = {"id": cid, "pass": bool(ok)}
    if not ok and diff:
        c["diff"] = diff
    c.update(extra)
    return c


def compare_fixture(fx, actual, results):
    exp = fx / "expected"
    checks = []

    # 1. exit codes (contract: 0 = success, non-zero = failure) - one check per fixture covering
    #    every job line, so that an application that does nothing gets little credit
    exp_codes = []
    ec_file = exp / "exit_codes.txt"
    if ec_file.is_file():
        for line in ec_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                idx, job, rc = line.split("\t")
                exp_codes.append((int(idx), job, int(rc)))
    wrong = []
    for idx, job, rc in exp_codes:
        act = results[idx - 1]["rc"] if idx - 1 < len(results) else None
        if act is None or (rc == 0) != (act == 0):
            wrong.append("[%d] %s: expected %s, actual rc=%s"
                         % (idx, job, "success(0)" if rc == 0 else "failure(non-zero)", act))
    checks.append(check("exit:codes", not wrong, "\n".join(wrong), jobs=len(exp_codes)))

    # 2. business tables
    for table, _ in TABLES:
        ef = exp / "tables" / (table + ".csv")
        af = actual / "tables" / (table + ".csv")
        e_lines = ef.read_text(encoding="utf-8").splitlines() if ef.is_file() else []
        if not af.is_file():
            checks.append(check("table:" + table, False, "table dump missing"))
            continue
        a_lines = af.read_text(encoding="utf-8").splitlines()
        ok = e_lines == a_lines
        e_rows, a_rows = e_lines[1:], a_lines[1:]
        matched = len(set(e_rows) & set(a_rows))
        checks.append(check("table:" + table, ok, "" if ok else text_diff(e_lines, a_lines),
                            rows_expected=len(e_rows), rows_actual=len(a_rows), rows_matched=matched))

    # 3. outbox / reject files (byte compare) + listings
    for sub in ("outbox", "reject"):
        e_list = list_files(exp / sub)
        a_list = list_files(actual / sub)
        ok = e_list == a_list
        diff = ""
        if not ok:
            miss = sorted(set(e_list) - set(a_list))
            extra = sorted(set(a_list) - set(e_list))
            diff = "missing=%s extra=%s" % (miss, extra)
        checks.append(check("%s:files" % sub, ok, diff))
        for rel in e_list:
            ef = exp / sub / rel
            af = actual / sub / rel
            if not af.is_file():
                checks.append(check("%s:%s" % (sub, rel), False, "file not produced"))
                continue
            eb, ab = ef.read_bytes(), af.read_bytes()
            checks.append(check("%s:%s" % (sub, rel), eb == ab, bytes_diff(eb, ab)))

    # 4. archive / inbox listings
    for lst in ("archive_listing.txt", "inbox_listing.txt"):
        ef, af = exp / lst, actual / lst
        e_lines = ef.read_text(encoding="utf-8").splitlines() if ef.is_file() else []
        a_lines = af.read_text(encoding="utf-8").splitlines() if af.is_file() else []
        checks.append(check(lst.replace("_listing.txt", ":listing"), e_lines == a_lines,
                            text_diff(e_lines, a_lines)))
    return checks


# --------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="run_hidden_tests.sh",
                                 description="TLOG hidden black-box harness")
    ap.add_argument("app_dir", help="application directory (contains build.sh and bin/run_job.sh)")
    ap.add_argument("--java-opts", default="", help="JAVA_OPTS passed to every job (default: empty)")
    ap.add_argument("--out", default="hidden_test_report.json", help="JSON report path")
    ap.add_argument("--fixtures", default="", help="comma separated fixture names (default: all)")
    ap.add_argument("--work", default="", help="work directory (kept); default: temp dir, removed")
    ap.add_argument("--keep-work", action="store_true", help="keep the temporary work directory")
    ap.add_argument("--no-build", action="store_true", help="skip <app_dir>/build.sh")
    ap.add_argument("--job-timeout", type=int, default=600, help="seconds per job (default 600)")
    # argparse would treat a single value such as "-Dfoo=bar" as an option: glue it to the flag
    argv = list(sys.argv[1:] if argv is None else argv)
    fixed = []
    i = 0
    while i < len(argv):
        if argv[i] == "--java-opts" and i + 1 < len(argv):
            fixed.append("--java-opts=" + argv[i + 1])
            i += 2
        else:
            fixed.append(argv[i])
            i += 1
    args = ap.parse_args(fixed)

    app_dir = Path(args.app_dir).resolve()
    if not (app_dir / "bin" / "run_job.sh").is_file():
        raise SystemExit("harness: %s/bin/run_job.sh not found" % app_dir)

    fixtures = sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir() and (p / "jobs.txt").is_file())
    if args.fixtures:
        wanted = [w.strip() for w in args.fixtures.split(",") if w.strip()]
        fixtures = [f for f in fixtures if any(f.name == w or f.name.startswith(w) for w in wanted)]
    if not fixtures:
        raise SystemExit("harness: no fixtures selected")

    keep = bool(args.work) or args.keep_work
    work = Path(args.work).resolve() if args.work else Path(tempfile.mkdtemp(prefix="tlog_hidden_"))
    work.mkdir(parents=True, exist_ok=True)

    started = _dt.datetime.now().isoformat(timespec="seconds")
    report = {"harness_version": HARNESS_VERSION, "app_dir": str(app_dir), "java_opts": args.java_opts,
              "started_at": started, "work_dir": str(work) if keep else None, "fixtures": []}

    env = Env(args, work)
    env.compile_dumper()

    # build
    build = {"skipped": args.no_build}
    if not args.no_build:
        log("[harness] building %s ..." % app_dir)
        rc, secs = run_cmd(["bash", str(app_dir / "build.sh")], cwd=str(app_dir), log_file=work / "_build.log",
                           timeout=3600)
        build.update({"rc": rc, "seconds": round(secs, 1)})
        log("[harness] build rc=%d (%.0fs)" % (rc, secs))
    report["build"] = build
    build_ok = args.no_build or build.get("rc") == 0

    total_pass = total = fx_pass = 0
    try:
        if build_ok:
            env.start_h2()
            log("[harness] H2 %s TCP server on port %d" % (H2_VERSION, env.port))
        for fx in fixtures:
            desc = (fx / "desc.txt").read_text(encoding="utf-8").strip() if (fx / "desc.txt").is_file() else ""
            if build_ok:
                actual, results, errors, stripped = run_fixture(env, fx, app_dir)
                checks = compare_fixture(fx, actual, results)
            else:
                results, errors, stripped = [], ["build failed"], []
                checks = [dict(c, **{"pass": False, "diff": "build failed"})
                          for c in compare_fixture(fx, work / "_nonexistent", [])]
            passed = sum(1 for c in checks if c["pass"])
            total_pass += passed
            total += len(checks)
            fx_pass += 1 if passed == len(checks) else 0
            entry = {"name": fx.name, "description": desc, "passed": passed, "total": len(checks),
                     "jobs": results, "checks": checks}
            if errors:
                entry["errors"] = errors
            if stripped:
                entry["stripped_jvm_env_flags"] = sorted(set(stripped))
            report["fixtures"].append(entry)
            status = "PASS" if passed == len(checks) else "FAIL"
            log("[harness] %-4s %3d/%-3d %s" % (status, passed, len(checks), fx.name))
            for c in checks:
                if not c["pass"]:
                    log("           x %s" % c["id"])
    finally:
        env.stop_h2()

    report["finished_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    report["totals"] = {"checks_passed": total_pass, "checks_total": total,
                        "fixtures_passed": fx_pass, "fixtures_total": len(fixtures),
                        "pass_rate": round(total_pass / total, 4) if total else 0.0}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log("[harness] TOTAL %d/%d checks passed, %d/%d fixtures fully passed -> %s"
        % (total_pass, total, fx_pass, len(fixtures), out))
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return 0 if total and total_pass == total else 1


if __name__ == "__main__":
    sys.exit(main())
