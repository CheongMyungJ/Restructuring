"""
Shared builders for hidden fixtures / provided samples.

ADV : fixed length 140 bytes (MS949), CRLF, H/D/T records
TER : CSV UTF-8 (optional BOM), header row, optional '#EOF,<n>' trailer, times in UTC ('Z')
All attempt times are given in KST (plant local time) as naive datetimes.
"""
import datetime as dt
from pathlib import Path

ENC = "cp949"          # == Java MS949 for the characters used here
TER_HEADER = ("SERIAL,LOT,PRODUCT,STEP,START_UTC,END_UTC,TESTER,OPERATOR,RESULT,"
              "READ_MBPS,WRITE_MBPS,LAT_US,BAD_BLK,ECC_CNT,TEMP_F,FW")
KST_OFFSET = dt.timedelta(hours=9)

# default measurements per product family (read/write MB/s, latency us, bad blocks, ecc, temp C)
FAMILY = {
    "C512": dict(read=540.0, write=500.0, lat=90, bad=2, ecc=500, temp=62, fw="SA21C05"),
    "C1T0": dict(read=1700.0, write=1400.0, lat=80, bad=3, ecc=900, temp=66, fw="NV31C12"),
    "C128": dict(read=520.0, write=450.0, lat=95, bad=1, ecc=300, temp=60, fw="SA20B03"),
    "C256": dict(read=500.0, write=420.0, lat=99, bad=2, ecc=400, temp=61, fw="SA19A01"),
    "E384": dict(read=3200.0, write=2800.0, lat=70, bad=5, ecc=2000, temp=68, fw="EN40E07"),
    "E768": dict(read=3100.0, write=2900.0, lat=75, bad=6, ecc=2500, temp=69, fw="EN41E02"),
}


def family(prod):
    return FAMILY.get(prod[:4], FAMILY["C512"])


def kst(s):
    """'yyyyMMddHHmmss' -> datetime"""
    return dt.datetime.strptime(s, "%Y%m%d%H%M%S")


def fb(s, n, enc=ENC):
    b = s.encode(enc)
    if len(b) > n:
        raise ValueError("field too long: %r > %d bytes" % (s, n))
    return b + b" " * (n - len(b))


class Att:
    """One test attempt (one D record / one CSV line)."""

    def __init__(self, serial, lot, prod, step, start, res="P", dur=15, end=None, tester=None,
                 oper="김민준", fw=None, **m):
        f = family(prod)
        self.serial, self.lot, self.prod, self.step = serial, lot, prod, step
        self.start = kst(start) if isinstance(start, str) else start
        if end is not None:
            self.end = kst(end) if isinstance(end, str) else end
        else:
            self.end = self.start + dt.timedelta(minutes=dur)
        self.res = res
        self.tester = tester
        self.oper = oper
        self.fw = fw or f["fw"]
        self.read = m.pop("read", f["read"])
        self.write = m.pop("write", f["write"])
        self.lat = m.pop("lat", f["lat"])
        self.bad = m.pop("bad", f["bad"])
        self.ecc = m.pop("ecc", f["ecc"])
        self.temp = m.pop("temp", f["temp"])
        self.temp_f = m.pop("temp_f", None)
        if m:
            raise TypeError("unknown measures %s" % m)

    # ---------------- ADV ----------------
    def adv(self, rectype="D", serial=None, step=None, start=None, end=None, oper=None, res=None,
            read=None, write=None, lat=None, bad=None, ecc=None, temp=None, prod=None, lot=None,
            tester=None, fw=None, oper_chars=None):
        """Build a 140-byte ADV detail record. Keyword args override the raw field text.
        oper_chars: pad OPERATOR to 10 *characters* instead of bytes (produces a bad-length record)."""
        tval = self.temp if temp is None else temp
        temp_s = tval if isinstance(tval, str) else ("%+04d" % tval)
        parts = [
            fb(rectype, 1),
            fb(self.serial if serial is None else serial, 16),
            fb(self.lot if lot is None else lot, 10),
            fb(self.prod if prod is None else prod, 8),
            fb(self.step if step is None else step, 4),
            fb(self.start.strftime("%Y%m%d%H%M%S") if start is None else start, 14),
            fb(self.end.strftime("%Y%m%d%H%M%S") if end is None else end, 14),
            fb((self.tester or "ADVT01") if tester is None else tester, 8),
        ]
        if oper_chars is not None:
            parts.append(oper_chars.ljust(10).encode(ENC))
        else:
            parts.append(fb(self.oper if oper is None else oper, 10))
        parts += [
            fb(self.res if res is None else res, 2),
            fb("%06d" % round(self.read * 10) if read is None else read, 6),
            fb("%06d" % round(self.write * 10) if write is None else write, 6),
            fb("%06d" % self.lat if lat is None else lat, 6),
            fb("%05d" % self.bad if bad is None else bad, 5),
            fb("%08d" % self.ecc if ecc is None else ecc, 8),
            fb(temp_s, 4),
            fb(self.fw if fw is None else fw, 8),
            b" " * 10,
        ]
        return b"".join(parts)

    # ---------------- TER ----------------
    def ter(self, serial=None, step=None, start=None, end=None, oper=None, res=None, read=None,
            write=None, lat=None, bad=None, ecc=None, temp_f=None, prod=None, lot=None, tester=None,
            fw=None, quote=()):
        """Build one TER CSV line (no line terminator). Values are raw text; 'quote' lists
        column names that must be double-quoted (auto-quoted when containing ',' or '"')."""
        res_map = {"P": "PASS", "F": "FAIL", "A": "ABORT"}
        tf = self.temp_f if self.temp_f is not None else ("%.1f" % (self.temp * 1.8 + 32))
        cols = [
            ("SERIAL", self.serial if serial is None else serial),
            ("LOT", self.lot if lot is None else lot),
            ("PRODUCT", self.prod if prod is None else prod),
            ("STEP", self.step if step is None else step),
            ("START_UTC", utc(self.start) if start is None else start),
            ("END_UTC", utc(self.end) if end is None else end),
            ("TESTER", (self.tester or "TER-07") if tester is None else tester),
            ("OPERATOR", self.oper if oper is None else oper),
            ("RESULT", res_map.get(self.res, self.res) if res is None else res),
            ("READ_MBPS", ("%.1f" % self.read) if read is None else read),
            ("WRITE_MBPS", ("%.1f" % self.write) if write is None else write),
            ("LAT_US", str(self.lat) if lat is None else lat),
            ("BAD_BLK", str(self.bad) if bad is None else bad),
            ("ECC_CNT", str(self.ecc) if ecc is None else ecc),
            ("TEMP_F", tf if temp_f is None else temp_f),
            ("FW", self.fw if fw is None else fw),
        ]
        out = []
        for name, v in cols:
            if name in quote or "," in v or '"' in v:
                v = '"' + v.replace('"', '""') + '"'
            out.append(v)
        return ",".join(out)


def utc(kst_dt):
    return (kst_dt - KST_OFFSET).strftime("%Y-%m-%dT%H:%M:%SZ")


def adv_header(file_date, create_time="063000", site="P1"):
    h = b"H" + file_date.encode() + create_time.encode() + fb("ADV", 10) + fb(site, 4) + fb("LAYOUT-V2", 10)
    return h + b" " * (140 - len(h))


def adv_trailer(count):
    t = b"T" + (b"%07d" % count)
    return t + b" " * (140 - len(t))


def adv_file(file_date, records, trailer="auto", eol=b"\r\n", create_time="063000"):
    """records: list of bytes (D records or raw malformed lines).
    trailer: 'auto' (count of lines starting with D), None (no trailer), int, or raw bytes."""
    lines = [adv_header(file_date, create_time)] + list(records)
    if trailer == "auto":
        lines.append(adv_trailer(sum(1 for r in records if r[:1] == b"D")))
    elif isinstance(trailer, int):
        lines.append(adv_trailer(trailer))
    elif isinstance(trailer, bytes):
        lines.append(trailer)
    return eol.join(lines) + eol


def ter_file(lines, bom=True, eof="auto", eol="\r\n", header=TER_HEADER):
    """eof: 'auto' (#EOF,<data line count>), None (no trailer), int or raw str."""
    out = [header] + list(lines)
    if eof == "auto":
        out.append("#EOF,%d" % len(lines))
    elif isinstance(eof, int):
        out.append("#EOF,%d" % eof)
    elif isinstance(eof, str):
        out.append(eof)
    data = eol.join(out) + eol
    return (b"\xef\xbb\xbf" if bom else b"") + data.encode("utf-8")


# ---------------------------------------------------------------------------------------------
# master data / seed
# ---------------------------------------------------------------------------------------------

def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def seed_sql(products, bin_codes, rules, config, extra=()):
    out = ["-- fixture seed (master data + pre-existing rows)"]
    for p in products:
        out.append("INSERT INTO TB_PRODUCT (PROD_CD, PROD_NM, PROD_GRP, ALERT_YIELD, USE_YN) VALUES (%s);"
                   % ", ".join(q(x) for x in p))
    for b in bin_codes:
        out.append("INSERT INTO TB_BIN_CODE (BIN_NO, BIN_NM, PASS_YN) VALUES (%s);" % ", ".join(q(x) for x in b))
    for r in rules:
        out.append("INSERT INTO TB_BIN_RULE (RULE_ID, PROD_CD, ITEM_CD, OPER_CD, THRESHOLD, BIN_NO, PRIORITY, USE_YN, RULE_DESC) "
                   "VALUES (%s);" % ", ".join(q(x) for x in r))
    for k, v, d in config:
        out.append("INSERT INTO TB_SYS_CONFIG (CFG_KEY, CFG_VAL, CFG_DESC) VALUES (%s, %s, %s);" % (q(k), q(v), q(d)))
    out.extend(extra)
    out.append("COMMIT;")
    return "\n".join(out) + "\n"


def test_result_insert(a, vendor, src_file, work_dt):
    """Pre-existing TB_TEST_RESULT row (KST strings as the legacy stores them)."""
    vals = [a.serial, a.step, a.start.strftime("%Y%m%d%H%M%S"), a.end.strftime("%Y%m%d%H%M%S"), work_dt,
            a.lot, a.prod, a.tester or ("ADVT01" if vendor == "ADV" else "TER-07"), a.oper, a.res,
            a.read, a.write, a.lat, a.bad, a.ecc, a.temp, a.fw, vendor, src_file]
    return ("INSERT INTO TB_TEST_RESULT (SERIAL, STEP_CD, START_DTM, END_DTM, WORK_DT, LOT_ID, PROD_CD, TESTER_ID, "
            "OPER_NM, RESULT_CD, READ_MBPS, WRITE_MBPS, LAT_US, BAD_BLK, ECC_CNT, MAX_TEMP_C, FW_VER, VENDOR_CD, "
            "SRC_FILE_NM, REG_DTM) VALUES (%s, SYSDATE);" % ", ".join(q(v) for v in vals))


def device_bin_insert(serial, work_dt, prod, lot, bin_no, rule_id, excl="N"):
    return ("INSERT INTO TB_DEVICE_BIN (SERIAL, WORK_DT, PROD_CD, LOT_ID, BIN_NO, RULE_ID, EXCL_YN, REG_DTM) "
            "VALUES (%s, %s, %s, %s, %d, %s, %s, SYSDATE);" % (q(serial), q(work_dt), q(prod), q(lot), bin_no,
                                                              q(rule_id), q(excl)))


def file_log_insert(seq, name, vendor, biz_dt, total, load, rej, dup, status):
    return ("INSERT INTO TB_FILE_LOG (FILE_SEQ, FILE_NM, VENDOR_CD, BIZ_DT, TOTAL_CNT, LOAD_CNT, REJ_CNT, DUP_CNT, "
            "STATUS_CD, LOAD_DTM) VALUES (SEQ_FILE_LOG.NEXTVAL, %s, %s, %s, %d, %d, %d, %d, %s, SYSDATE);"
            % (q(name), q(vendor), q(biz_dt), total, load, rej, dup, q(status)))


class FixtureWriter:
    def __init__(self, root, name, desc):
        self.dir = Path(root) / name
        self.desc = desc
        self.files = {}
        self.jobs = []
        self.seed = ""

    def add(self, fname, data):
        self.files[fname] = data

    def write(self):
        import shutil
        if self.dir.exists():
            # keep nothing from a previous generation (expected/ is regenerated by record_expected)
            shutil.rmtree(self.dir)
        (self.dir / "inbox").mkdir(parents=True)
        for n, d in sorted(self.files.items()):
            (self.dir / "inbox" / n).write_bytes(d)
        (self.dir / "seed.sql").write_text(self.seed, encoding="utf-8")
        (self.dir / "jobs.txt").write_text("".join(" ".join(j) + "\n" for j in self.jobs), encoding="utf-8")
        (self.dir / "desc.txt").write_text(self.desc.strip() + "\n", encoding="utf-8")
