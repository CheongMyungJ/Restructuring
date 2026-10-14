#!/usr/bin/env python3
"""
Independent reference model of the TLOG business rules (production settings: KST, dup policy LAST,
MAX_RETEST 3, yield truncation). Re-computes every fixture from its inputs and compares the result with
fixtures/<fx>/expected (which was recorded from the legacy application).

    python3 tools/refmodel.py [fixture ...]            verify expected/ (exit 0 = byte-for-byte agreement)
    python3 tools/refmodel.py --matrix                 per-trap impact matrix (naive re-implementation variants)
    python3 tools/refmodel.py --variants A,B --vs report.json
                                                       compare a variant with a real harness report

Variants model what a re-implementation gets wrong when it follows the code literally, the outdated
documents, or common library defaults (see VARIANTS).
"""
import datetime as dt
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TABLES = {
    "TB_TEST_RESULT": ["SERIAL", "STEP_CD", "START_DTM", "END_DTM", "WORK_DT", "LOT_ID", "PROD_CD", "TESTER_ID",
                       "OPER_NM", "RESULT_CD", "READ_MBPS", "WRITE_MBPS", "LAT_US", "BAD_BLK", "ECC_CNT",
                       "MAX_TEMP_C", "FW_VER", "VENDOR_CD", "SRC_FILE_NM"],
    "TB_FILE_LOG": ["FILE_NM", "VENDOR_CD", "BIZ_DT", "TOTAL_CNT", "LOAD_CNT", "REJ_CNT", "DUP_CNT", "STATUS_CD"],
    "TB_DEVICE_BIN": ["SERIAL", "WORK_DT", "PROD_CD", "LOT_ID", "BIN_NO", "RULE_ID", "EXCL_YN"],
    "TB_LOT_YIELD": ["WORK_DT", "PROD_CD", "LOT_ID", "IN_QTY", "PASS_QTY", "YIELD_PCT"] +
                    ["BIN%d_QTY" % i for i in range(1, 10)] + ["ALERT_YN"],
}
STEPS = ("FT1", "BI", "FT2")
MAX_RETEST = 3

VARIANTS = {
    "TZ_UTC": "JVM default time zone is not Asia/Seoul (container UTC): TER UTC->'KST' conversion and WORK_DT use UTC",
    "DUP_FIRST": "duplicate policy left at code default FIRST (keep existing row)",
    "YIELD_ROUND": "YIELD_PCT rounded HALF_UP (design doc / code comment) instead of truncated",
    "RETEST_5": "retest limit 5 (design doc, unused Constants.MAX_RETEST) instead of 3",
    "ADV_CHARS": "ADV record length / field offsets taken in characters instead of MS949 bytes",
    "TER_CHARCUT": "TER operator name cut to 10 characters instead of 10 MS949 bytes",
    "TRIM_AFTER_CUT": "TER operator name trimmed again after the byte cut",
    "RPT_CHARCUT": "report PROD_NM cut/padded to 20 characters instead of 20 MS949 bytes",
    "TEMP_DOUBLE": "Fahrenheit->Celsius with double arithmetic and Math.round instead of BigDecimal HALF_UP",
    "NO_STEP_CHECK": "undocumented E08 (invalid STEP) not implemented",
    "E07_FIRST": "product check (E07) done before the other field validations",
    "E09_REJ_ZERO": "file-level reject (E09) logged with REJ_CNT=0 instead of the detail count",
    "TER_FIRST": "inbox files processed TER before ADV (changes which duplicate wins under LAST)",
    "WORKDT_CALENDAR": "WORK_DT = calendar date of START (06:00 shift boundary ignored)",
    "NO_OVR_E": "hard-coded enterprise override (OVR_E) not implemented",
    "SCRAP_ANY_DATE": "scrap stickiness also applied for BIN 9 on later/same work days",
    "NO_ES_EXCL": "engineering samples (ES*) not excluded from yield",
    "ALERT_EMPTY_FILE": "ALERT file written (header only) even when there are no alerts",
    "FOOTER_NO_CRLF": "no CRLF after the report trailer record (FlatFileItemWriter default)",
    "BOM_HEADERMAP": "TER columns mapped by header name without stripping the UTF-8 BOM (SERIAL column lost)",
    "NO_SN_STRIP": "serial normalisation without removing the TER 'SN' prefix",
    "REJECT_UTF8": "ADV reject files written in UTF-8 instead of the source encoding (MS949)",
}


def jtrim(s):
    """java.lang.String.trim(): strip chars <= U+0020"""
    i, j = 0, len(s)
    while i < j and s[i] <= " ":
        i += 1
    while j > i and s[j - 1] <= " ":
        j -= 1
    return s[i:j]


def ora(v):
    """Oracle mode: empty string is NULL"""
    return None if v == "" else v


def java_lines(text):
    if text == "":
        return []
    parts = re.split(r"\r\n|\r|\n", text)
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def cut_bytes(s, n):
    out, size = [], 0
    for ch in s:
        b = len(ch.encode("cp949", errors="replace"))
        if size + b > n:
            break
        out.append(ch)
        size += b
    return "".join(out)


def rpad_bytes(s, n):
    s = cut_bytes(s or "", n)
    return s + " " * (n - len(s.encode("cp949")))


def norm_serial(s, strip_sn=True):
    s = jtrim(s).upper()
    if strip_sn and s.startswith("SN"):
        s = s[2:]
    return s.replace("-", "")


def split_csv(line):
    out, cur, inq, i = [], [], False, 0
    while i < len(line):
        c = line[i]
        if inq:
            if c == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    cur.append('"')
                    i += 1
                else:
                    inq = False
            else:
                cur.append(c)
        else:
            if c == '"':
                inq = True
            elif c == ",":
                out.append("".join(cur))
                cur = []
            else:
                cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


JAVA_DEC = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
JAVA_INT = re.compile(r"^[+-]?\d+$")


def jdec(s):
    s = jtrim(s)
    if not JAVA_DEC.match(s):
        raise ValueError(s)
    return Decimal(s)


def jint(s):
    s = jtrim(s)
    if not JAVA_INT.match(s) or not (-2 ** 31 <= int(s) < 2 ** 31):
        raise ValueError(s)
    return int(s)


def half_up(fr):
    """round a Fraction to integer, HALF_UP (away from zero)"""
    sign = -1 if fr < 0 else 1
    a = abs(fr)
    n = int(a)
    if a - n >= Fraction(1, 2):
        n += 1
    return sign * n


def parse14(s):
    if not re.fullmatch(r"\d{14}", s):
        return None
    try:
        return dt.datetime.strptime(s, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def parse_utc(s, utc_jvm=False):
    s = jtrim(s)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s):
        return None
    try:
        t = dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return t if utc_jvm else t + dt.timedelta(hours=9)   # -> wall time of the JVM default zone


def work_dt(kst_dt, calendar=False):
    if calendar:
        return kst_dt.strftime("%Y%m%d")
    d = kst_dt.date() - dt.timedelta(days=1) if kst_dt.hour < 6 else kst_dt.date()
    return d.strftime("%Y%m%d")


class Reject(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


# ------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, fx, variants=frozenset()):
        self.fx = fx
        self.v = frozenset(variants)
        self.bom_file = False
        self.products, self.bin_codes, self.rules, self.config = {}, {}, [], {}
        self.test_result, self.file_log, self.device_bin, self.lot_yield = {}, [], {}, {}
        self.inbox = {p.name: p.read_bytes() for p in sorted((fx / "inbox").iterdir())} if (fx / "inbox").is_dir() else {}
        self.outbox, self.reject, self.archive = {}, {}, []
        self.load_seed((fx / "seed.sql").read_text(encoding="utf-8"))

    # ---------------- seed ----------------
    def load_seed(self, text):
        for m in re.finditer(r"INSERT INTO (\w+) \(([^)]*)\) VALUES \((.*)\);", text):
            table, cols = m.group(1), [c.strip() for c in m.group(2).split(",")]
            vals = self.sql_values(m.group(3))
            row = dict(zip(cols, vals))
            if table == "TB_PRODUCT":
                self.products[row["PROD_CD"]] = row
            elif table == "TB_BIN_CODE":
                self.bin_codes[int(row["BIN_NO"])] = row
            elif table == "TB_BIN_RULE":
                self.rules.append(row)
            elif table == "TB_SYS_CONFIG":
                self.config[row["CFG_KEY"]] = row["CFG_VAL"]
            elif table == "TB_TEST_RESULT":
                for k in ("READ_MBPS", "WRITE_MBPS"):
                    row[k] = Decimal(row[k]).quantize(Decimal("0.1"))
                for k in ("LAT_US", "BAD_BLK", "ECC_CNT", "MAX_TEMP_C"):
                    row[k] = int(row[k])
                self.test_result[(row["SERIAL"], row["STEP_CD"], row["START_DTM"])] = row
            elif table == "TB_DEVICE_BIN":
                row["BIN_NO"] = int(row["BIN_NO"])
                self.device_bin[(row["SERIAL"], row["WORK_DT"])] = row
            elif table == "TB_FILE_LOG":
                self.file_log.append(row)
            else:
                raise ValueError(table)

    @staticmethod
    def sql_values(s):
        out, i = [], 0
        while i < len(s):
            c = s[i]
            if c in " ,":
                i += 1
            elif c == "'":
                j, buf = i + 1, []
                while True:
                    if s[j] == "'" and j + 1 < len(s) and s[j + 1] == "'":
                        buf.append("'")
                        j += 2
                    elif s[j] == "'":
                        break
                    else:
                        buf.append(s[j])
                        j += 1
                out.append(ora("".join(buf)))
                i = j + 1
            else:
                m = re.match(r"[^,]+", s[i:])
                tok = m.group(0).strip()
                i += m.end()
                out.append(None if tok in ("NULL", "SYSDATE", "SEQ_FILE_LOG.NEXTVAL") else tok)
        return out

    # ---------------- jobs ----------------
    def run(self, job):
        if len(job) < 2 or job[0] not in ("LOAD", "JUDGE", "YIELD", "PURGE") or not re.fullmatch(r"\d{8}", job[1]):
            return 1
        try:
            dt.datetime.strptime(job[1], "%Y%m%d")
        except ValueError:
            return 1
        getattr(self, {"YIELD": "yield_"}.get(job[0], job[0].lower()))(job[1])
        return 0

    # ---------------- LOAD ----------------
    def load(self, d):
        names = sorted((n for n in self.inbox
                        if re.fullmatch(r"ADV_%s_\d{2}\.dat" % d, n) or re.fullmatch(r"TER_%s_\d{2}\.csv" % d, n)),
                       key=lambda n: (0 if "TER_FIRST" in self.v and n.startswith("TER") else 1, n))
        infos = []
        for n in names:
            adv = n.startswith("ADV_")
            info = dict(FILE_NM=n, VENDOR_CD="ADV" if adv else "TER", BIZ_DT=d, TOTAL_CNT=0, LOAD_CNT=0,
                        REJ_CNT=0, DUP_CNT=0, enc="cp949" if adv else "utf-8", err=False)
            text = self.inbox[n].decode(info["enc"])
            lines = java_lines(text)
            if adv:
                detail = [l for l in lines if l and l[0] not in "HT"]
                trailers = [l for l in lines if l and l[0] == "T"]
                info["TOTAL_CNT"] = len(detail)
                d_cnt = sum(1 for l in detail if l[0] == "D")
                if not trailers:
                    info["err"] = True
                else:
                    c = trailers[-1][1:8]
                    if not re.fullmatch(r"\d{7}", c) or int(c) != d_cnt:
                        info["err"] = True
            else:
                data = [l for l in lines[1:] if jtrim(l) != "" and not l.startswith("#EOF")]
                eofs = [l for l in lines[1:] if jtrim(l) != "" and l.startswith("#EOF")]
                info["TOTAL_CNT"] = len(data)
                if eofs:
                    parts = [p for p in eofs[-1].split(",") if p != ""]
                    if len(parts) < 2 or not re.fullmatch(r"\d+", jtrim(parts[1])) or int(jtrim(parts[1])) != len(data):
                        info["err"] = True
            if info["err"]:
                info["REJ_CNT"] = 0 if "E09_REJ_ZERO" in self.v else info["TOTAL_CNT"]
                self.write_reject(info, 0, "E09", n)
            infos.append(info)

        loaded = set()
        for info in infos:
            if info["err"]:
                continue
            adv = info["VENDOR_CD"] == "ADV"
            raw = self.inbox[info["FILE_NM"]]
            self.bom_file = "BOM_HEADERMAP" in self.v and raw.startswith(b"\xef\xbb\xbf")
            lines = java_lines(raw.decode(info["enc"]))
            for no, line in enumerate(lines, 1):
                if adv:
                    if line == "" or line[0] in "HT":
                        continue
                else:
                    if no == 1 or jtrim(line) == "" or line.startswith("#EOF"):
                        continue
                try:
                    row = self.parse_adv(line) if adv else self.parse_ter(line)
                    self.check_product(row["PROD_CD"])
                except Reject as e:
                    self.write_reject(info, no, e.code, line)
                    info["REJ_CNT"] += 1
                    continue
                row["VENDOR_CD"] = info["VENDOR_CD"]
                row["SRC_FILE_NM"] = info["FILE_NM"]
                key = (row["SERIAL"], row["STEP_CD"], row["START_DTM"])
                if key in loaded or key in self.test_result:
                    info["DUP_CNT"] += 1
                    if "DUP_FIRST" not in self.v:
                        self.test_result[key] = row      # LAST: overwrite
                    continue
                loaded.add(key)
                info["LOAD_CNT"] += 1
                self.test_result[key] = row

        for info in infos:
            st = "E" if info["err"] else ("W" if info["REJ_CNT"] > 0 else "S")
            self.file_log.append({k: info[k] for k in TABLES["TB_FILE_LOG"][:-1]} | {"STATUS_CD": st})
            del self.inbox[info["FILE_NM"]]
            self.archive.append(d + "/" + info["FILE_NM"])

    def check_product(self, prod):
        p = self.products.get(prod)
        if p is None or p["USE_YN"] != "Y":
            raise Reject("E07")

    def write_reject(self, info, no, code, raw):
        enc = "utf-8" if "REJECT_UTF8" in self.v else info["enc"]
        self.reject.setdefault(info["FILE_NM"] + ".rej", bytearray()).extend(
            ("%d|%s|%s\n" % (no, code, raw)).encode(enc))

    def parse_adv(self, line):
        chars = "ADV_CHARS" in self.v
        b = line.encode("cp949")
        if (len(line) if chars else len(b)) != 140 or line[0] != "D":
            raise Reject("E01")

        def f(o, n):
            return line[o:o + n] if chars else b[o:o + n].decode("cp949", errors="replace")

        if "E07_FIRST" in self.v:
            self.check_product(jtrim(f(27, 8)))
        serial = norm_serial(f(1, 16))
        if serial == "":
            raise Reject("E02")
        step = jtrim(f(35, 4))
        if step not in STEPS and "NO_STEP_CHECK" not in self.v:
            raise Reject("E08")
        st, en = parse14(f(39, 14)), parse14(f(53, 14))
        if st is None or en is None:
            raise Reject("E03")
        if en < st:
            raise Reject("E04")
        res = jtrim(f(85, 2))
        if res not in ("P", "F", "A"):
            raise Reject("E05")
        nums = [f(87, 6), f(93, 6), f(99, 6), f(105, 5), f(110, 8)]
        temp = f(118, 4)
        if not all(re.fullmatch(r"\d+", x) for x in nums) or temp[0] not in "+-" or not re.fullmatch(r"\d+", temp[1:]):
            raise Reject("E06")
        t = int(temp[1:]) * (-1 if temp[0] == "-" else 1)
        return dict(SERIAL=serial, STEP_CD=step, START_DTM=st.strftime("%Y%m%d%H%M%S"),
                    END_DTM=en.strftime("%Y%m%d%H%M%S"), WORK_DT=work_dt(st, "WORKDT_CALENDAR" in self.v),
                    LOT_ID=ora(jtrim(f(17, 10))),
                    PROD_CD=ora(jtrim(f(27, 8))), TESTER_ID=ora(jtrim(f(67, 8))), OPER_NM=ora(jtrim(f(75, 10))),
                    RESULT_CD=res, READ_MBPS=Decimal(int(nums[0])) / 10, WRITE_MBPS=Decimal(int(nums[1])) / 10,
                    LAT_US=int(nums[2]), BAD_BLK=int(nums[3]), ECC_CNT=int(nums[4]), MAX_TEMP_C=t,
                    FW_VER=ora(jtrim(f(122, 8))))

    def parse_ter(self, line):
        c = split_csv(line)
        if len(c) != 16:
            raise Reject("E01")
        if "E07_FIRST" in self.v:
            self.check_product(jtrim(c[2]))
        serial = "" if self.bom_file else norm_serial(c[0], "NO_SN_STRIP" not in self.v)
        if serial == "":
            raise Reject("E02")
        step = jtrim(c[3])
        if step not in STEPS and "NO_STEP_CHECK" not in self.v:
            raise Reject("E08")
        utc_jvm = "TZ_UTC" in self.v
        st, en = parse_utc(c[4], utc_jvm), parse_utc(c[5], utc_jvm)
        if st is None or en is None:
            raise Reject("E03")
        if en < st:
            raise Reject("E04")
        res = {"PASS": "P", "FAIL": "F", "ABORT": "A"}.get(jtrim(c[8]))
        if res is None:
            raise Reject("E05")
        try:
            rd = jdec(c[9]).quantize(Decimal("0.1"), ROUND_HALF_UP)
            wr = jdec(c[10]).quantize(Decimal("0.1"), ROUND_HALF_UP)
            lat, bad, ecc = jint(c[11]), jint(c[12]), jint(c[13])
            if "TEMP_DOUBLE" in self.v:
                import math
                temp = int(math.floor((float(jdec(c[14])) - 32) * 5 / 9 + 0.5))
            else:
                temp = half_up((Fraction(jdec(c[14])) - 32) * 5 / 9)
        except (ValueError, ArithmeticError):
            raise Reject("E06")
        oper = jtrim(c[7])
        oper = oper[:10] if "TER_CHARCUT" in self.v else cut_bytes(oper, 10)
        if "TRIM_AFTER_CUT" in self.v:
            oper = jtrim(oper)
        return dict(SERIAL=serial, STEP_CD=step, START_DTM=st.strftime("%Y%m%d%H%M%S"),
                    END_DTM=en.strftime("%Y%m%d%H%M%S"), WORK_DT=work_dt(st, "WORKDT_CALENDAR" in self.v),
                    LOT_ID=ora(jtrim(c[1])), PROD_CD=ora(jtrim(c[2])), TESTER_ID=ora(jtrim(c[6])), OPER_NM=ora(oper),
                    RESULT_CD=res, READ_MBPS=rd, WRITE_MBPS=wr, LAT_US=lat, BAD_BLK=bad, ECC_CNT=ecc,
                    MAX_TEMP_C=temp, FW_VER=ora(jtrim(c[15])))

    # ---------------- JUDGE ----------------
    def judge(self, d):
        rules = sorted((r for r in self.rules if r["USE_YN"] == "Y"),
                       key=lambda r: (int(r["PRIORITY"]), 1 if r["PROD_CD"] == "*" else 0, -int(r["BIN_NO"]),
                                      r["RULE_ID"]))
        rows = [r for r in self.test_result.values() if r["WORK_DT"] == d]
        for serial in sorted({r["SERIAL"] for r in rows}):
            att = sorted((r for r in rows if r["SERIAL"] == serial), key=lambda r: (r["STEP_CD"], r["START_DTM"]))
            eff, by_step = [], {}
            for r in att:
                by_step.setdefault(r["STEP_CD"], []).append(r)
            for step in sorted(by_step):
                tries = by_step[step]
                eff.append(tries[min(len(tries), 5 if "RETEST_5" in self.v else MAX_RETEST) - 1])
            prod, lot = att[0]["PROD_CD"], att[0]["LOT_ID"]
            excl = "Y" if serial.startswith("ES") and "NO_ES_EXCL" not in self.v else "N"
            agg = {"READ_MBPS": min(Decimal(r["READ_MBPS"]) for r in eff),
                   "WRITE_MBPS": min(Decimal(r["WRITE_MBPS"]) for r in eff),
                   "LAT_US": max(r["LAT_US"] for r in eff), "BAD_BLK": max(r["BAD_BLK"] for r in eff),
                   "ECC_CNT": max(r["ECC_CNT"] for r in eff), "TEMP_MAX": max(r["MAX_TEMP_C"] for r in eff)}
            any_day = "SCRAP_ANY_DATE" in self.v
            if any(k[0] == serial and (k[1] != d if any_day else k[1] < d) and v["BIN_NO"] == 9
                   for k, v in self.device_bin.items()):
                b = (9, "SCRAP_KEEP")
            elif any(r["RESULT_CD"] == "A" for r in eff):
                b = (8, "ABORT")
            elif prod and prod.startswith("E") and agg["BAD_BLK"] > 20 and "NO_OVR_E" not in self.v:
                b = (5, "OVR_E")
            else:
                b = None
                for r in rules:
                    if r["PROD_CD"] != "*" and r["PROD_CD"] != prod:
                        continue
                    if r["ITEM_CD"] not in agg:
                        continue
                    v, th, op = Decimal(agg[r["ITEM_CD"]]), Decimal(r["THRESHOLD"]), r["OPER_CD"].strip()
                    hit = {"<": v < th, "<=": v <= th, ">": v > th, ">=": v >= th}.get(op, False)
                    if hit:
                        b = (int(r["BIN_NO"]), r["RULE_ID"])
                        break
                if b is None:
                    b = (1, "DEFAULT") if all(r["RESULT_CD"] == "P" for r in eff) else (7, "DEFAULT_F")
            self.device_bin[(serial, d)] = dict(SERIAL=serial, WORK_DT=d, PROD_CD=prod, LOT_ID=lot, BIN_NO=b[0],
                                                RULE_ID=b[1], EXCL_YN=excl)

    # ---------------- YIELD ----------------
    def yield_(self, d):
        for k in [k for k in self.lot_yield if k[0] == d]:
            del self.lot_yield[k]
        groups = {}
        for r in self.device_bin.values():
            if r["WORK_DT"] == d and r["EXCL_YN"] == "N":
                groups.setdefault((r["PROD_CD"], r["LOT_ID"]), []).append(r)
        for (prod, lot), rs in sorted(groups.items()):
            n_in = len(rs)
            n_pass = sum(1 for r in rs if self.bin_codes.get(r["BIN_NO"], {}).get("PASS_YN") == "Y")
            if "YIELD_ROUND" in self.v:
                y = (Decimal(n_pass * 100) / Decimal(n_in)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            else:
                y = Decimal(n_pass * 10000 // n_in) / 100
            p = self.products.get(prod)
            ay = Decimal(p["ALERT_YIELD"]) if p and p["ALERT_YIELD"] is not None else None
            alert = "Y" if ay is not None and n_in >= 10 and y < ay else "N"
            row = dict(WORK_DT=d, PROD_CD=prod, LOT_ID=lot, IN_QTY=n_in, PASS_QTY=n_pass, YIELD_PCT=y,
                       ALERT_YN=alert)
            for i in range(1, 10):
                row["BIN%d_QTY" % i] = sum(1 for r in rs if r["BIN_NO"] == i)
            self.lot_yield[(d, prod, lot)] = row
        rows = [self.lot_yield[k] for k in sorted(k for k in self.lot_yield if k[0] == d)]
        recs = ["H" + d + "TLOGBATCH ".ljust(10) + "%07d" % len(rows)]
        recs[0] = recs[0].ljust(60)
        for r in rows:
            nm = (self.products.get(r["PROD_CD"]) or {}).get("PROD_NM")
            pnm = (nm or "")[:20].ljust(20) if "RPT_CHARCUT" in self.v else rpad_bytes(nm, 20)
            recs.append("D" + rpad_bytes(r["PROD_CD"], 8) + rpad_bytes(r["LOT_ID"], 10) + pnm
                        + "%07d" % r["IN_QTY"] + "%07d" % r["PASS_QTY"]
                        + ("%.2f" % r["YIELD_PCT"]).rjust(6, "0") + r["ALERT_YN"])
        recs.append(("T%07d%07d" % (len(rows), sum(r["PASS_QTY"] for r in rows) % 10 ** 7)).ljust(60))
        body = "".join(x + "\r\n" for x in recs)
        if "FOOTER_NO_CRLF" in self.v:
            body = body[:-2]
        self.outbox["YIELD_%s.txt" % d] = body.encode("cp949")
        alerts = [r for r in rows if r["ALERT_YN"] == "Y"]
        if "ALERT_EMPTY_FILE" in self.v and not alerts:
            self.outbox["ALERT_%s.csv" % d] = b"BIZ_DATE,PROD_CD,PROD_NM,LOT_ID,IN_QTY,PASS_QTY,YIELD_PCT,ALERT_YIELD\n"
        if alerts:
            out = ["BIZ_DATE,PROD_CD,PROD_NM,LOT_ID,IN_QTY,PASS_QTY,YIELD_PCT,ALERT_YIELD"]
            for r in alerts:
                p = self.products[r["PROD_CD"]]
                out.append('%s,%s,"%s",%s,%d,%d,%.2f,%.2f' % (d, r["PROD_CD"], p["PROD_NM"] or "", r["LOT_ID"],
                                                             r["IN_QTY"], r["PASS_QTY"], r["YIELD_PCT"],
                                                             Decimal(p["ALERT_YIELD"])))
            self.outbox["ALERT_%s.csv" % d] = "".join(x + "\n" for x in out).encode("utf-8")

    def purge(self, d):
        days = int(self.config.get("RETENTION_DAYS") or 90)
        cut = (dt.datetime.strptime(d, "%Y%m%d") - dt.timedelta(days=days)).strftime("%Y%m%d")
        for k in [k for k, v in self.test_result.items() if v["WORK_DT"] < cut]:
            del self.test_result[k]

    # ---------------- output ----------------
    def table_csv(self, name):
        cols = TABLES[name]
        src = {"TB_TEST_RESULT": self.test_result.values(), "TB_FILE_LOG": self.file_log,
               "TB_DEVICE_BIN": self.device_bin.values(), "TB_LOT_YIELD": self.lot_yield.values()}[name]

        def fmt(v):
            if v is None or v == "":
                return None
            if isinstance(v, (Decimal, float)):
                v = Decimal(str(v))
                return "0" if v == 0 else format(v.normalize(), "f")
            if isinstance(v, int):
                return str(v)
            s = str(v)
            if re.fullmatch(r"-?\d+\.\d+", s) and name != "TB_TEST_RESULT":
                return format(Decimal(s).normalize(), "f")
            return s

        rows = []
        for r in src:
            vals = []
            for c in cols:
                v = r.get(c)
                if c in ("TOTAL_CNT", "LOAD_CNT", "REJ_CNT", "DUP_CNT") and v is not None:
                    v = int(v)
                vals.append(fmt(v))
            rows.append(vals)
        rows.sort(key=lambda row: [x or "" for x in row])

        def csv(v):
            if v is None:
                return ""
            if v == "" or any(ch in v for ch in ',"\r\n') or v.startswith(" ") or v.endswith(" "):
                return '"' + v.replace('"', '""') + '"'
            return v

        return ",".join(cols) + "\n" + "".join(",".join(csv(v) for v in r) + "\n" for r in rows)


def harness_checks(fx, variants=frozenset()):
    """Run the model for one fixture and evaluate it with the same check ids as harness.py.
    Returns (list of (check_id, passed, detail))."""
    import difflib
    m = Model(fx, variants)
    jobs = [l.split() for l in (fx / "jobs.txt").read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]
    codes = [m.run(j) for j in jobs]
    exp = fx / "expected"
    out = []
    wrong = []
    for line in (exp / "exit_codes.txt").read_text(encoding="utf-8").splitlines():
        idx, job, rc = line.split("\t")
        act = codes[int(idx) - 1]
        if (int(rc) == 0) != (act == 0):
            wrong.append("[%s] %s rc=%s" % (idx, job, act))
    out.append(("exit:codes", not wrong, "; ".join(wrong)))
    for t in TABLES:
        mine = m.table_csv(t)
        theirs = (exp / "tables" / (t + ".csv")).read_text(encoding="utf-8")
        d = list(difflib.unified_diff(theirs.splitlines(), mine.splitlines(), "expected", "model", n=0, lineterm=""))
        out.append(("table:" + t, mine == theirs, "\n  ".join(d[:12])))
    for sub, files in (("outbox", m.outbox), ("reject", m.reject)):
        exp_files = sorted(p.name for p in (exp / sub).iterdir()) if (exp / sub).is_dir() else []
        out.append(("%s:files" % sub, sorted(files) == exp_files, "%s vs %s" % (sorted(files), exp_files)))
        for n in exp_files:
            ok = n in files and bytes(files[n]) == (exp / sub / n).read_bytes()
            out.append(("%s:%s" % (sub, n), ok, "content differs" if n in files else "missing"))
    arch = (exp / "archive_listing.txt").read_text().splitlines()
    out.append(("archive:listing", sorted(m.archive) == arch, "%s" % sorted(m.archive)))
    inbox = (exp / "inbox_listing.txt").read_text().splitlines()
    out.append(("inbox:listing", sorted(m.inbox) == inbox, "%s" % sorted(m.inbox)))
    return out


def fixtures(sel=()):
    return [p for p in sorted(FIXTURES.iterdir())
            if p.is_dir() and (not sel or any(p.name.startswith(s) for s in sel))]


def cmd_verify(sel):
    bad = 0
    for fx in fixtures(sel):
        res = harness_checks(fx)
        fails = [(i, d) for i, ok, d in res if not ok]
        print("%-4s %3d/%-3d %s" % ("OK" if not fails else "DIFF", len(res) - len(fails), len(res), fx.name))
        for i, d in fails:
            print("     x %s\n       %s" % (i, d))
        bad += 1 if fails else 0
    return 1 if bad else 0


def cmd_matrix(sel):
    fxs = fixtures(sel)
    total = sum(len(harness_checks(fx)) for fx in fxs)
    print("| trap variant | failing checks | fixtures affected (failing checks) |")
    print("|---|---|---|")
    detail = {}
    for name, desc in VARIANTS.items():
        per = []
        n = 0
        for fx in fxs:
            fails = [i for i, ok, _ in harness_checks(fx, {name}) if not ok]
            if fails:
                per.append("%s (%d)" % (fx.name[:2], len(fails)))
                detail.setdefault(name, []).append((fx.name, fails))
                n += len(fails)
        print("| `%s` %s | %d/%d | %s |" % (name, desc, n, total, ", ".join(per) or "-"))
    print()
    for name, rows in detail.items():
        print("* `%s`" % name)
        for fxn, fails in rows:
            print("  * %s: %s" % (fxn, ", ".join(fails)))


def cmd_vs(variants, report, sel):
    import json
    r = json.load(open(report, encoding="utf-8"))
    actual = {f["name"]: sorted(c["id"] for c in f["checks"] if not c["pass"]) for f in r["fixtures"]}
    same = True
    for fx in fixtures(sel):
        mine = sorted(i for i, ok, _ in harness_checks(fx, set(variants)) if not ok)
        theirs = actual.get(fx.name, [])
        flag = "same" if mine == theirs else "DIFFERENT"
        same &= mine == theirs
        print("%-9s %s model=%s legacy=%s" % (flag, fx.name, mine, theirs))
    return 0 if same else 1


def main():
    args = sys.argv[1:]
    if args[:1] == ["--matrix"]:
        cmd_matrix(args[1:])
        return 0
    if args[:1] == ["--variants"]:
        variants = [v for v in args[1].split(",") if v]
        unknown = [v for v in variants if v not in VARIANTS]
        if unknown:
            sys.exit("unknown variants %s" % unknown)
        return cmd_vs(variants, args[3], args[4:])
    return cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main())
