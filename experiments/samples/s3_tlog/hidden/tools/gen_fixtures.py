#!/usr/bin/env python3
"""
Generate hidden fixture INPUTS: fixtures/<NN_name>/{seed.sql, inbox/, jobs.txt, desc.txt}.
expected/ is produced afterwards by running the LEGACY app with production JAVA_OPTS
(tools/record_expected.sh) and cross-checked with tools/refmodel.py.

Inline comments state the intended outcome under production settings
(JVM TZ Asia/Seoul, tlog.dup.policy=LAST).
"""
import datetime as dt
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fxlib import (Att, FixtureWriter, adv_file, adv_trailer, device_bin_insert, file_log_insert, kst,  # noqa: E402
                   seed_sql, ter_file, test_result_insert, utc)

ROOT = Path(__file__).resolve().parents[1] / "fixtures"

PRODUCTS = [
    ("C512A100", "클라이언트 SSD 512GB 보급형", "CLIENT", 95.00, "Y"),
    ("C1T0A200", "클라이언트 NVMe 1TB 고성능", "CLIENT", 93.50, "Y"),
    ("C128T010", "보급형 128G", "CLIENT", 90.00, "Y"),
    ("E3840A01", "엔터프라이즈 NVMe SSD 3.84TB", "ENT", 97.00, "Y"),
    ("E7680B02", "X 데이터센터용 고성능 드라이브", "ENT", 96.50, "Y"),
    ("C256Z900", "단종 모델 256GB", "CLIENT", 90.00, "N"),
]
BIN_CODES = [
    (1, "양품 A", "Y"), (2, "양품 B(성능 하위)", "Y"), (3, "READ 성능 미달", "N"), (4, "WRITE 성능 미달", "N"),
    (5, "불량블록 과다", "N"), (6, "온도 이상", "N"), (7, "기능 불량", "N"), (8, "테스트 중단", "N"), (9, "폐기", "N"),
]
RULES = [
    ("R10_BAD_SCRAP", "*", "BAD_BLK", ">", 50, 9, 10, "Y", "불량블록 50 초과 폐기"),
    ("R20_TEMP_HI", "*", "TEMP_MAX", ">=", 85, 6, 20, "Y", "최고온도 85도 이상"),
    ("R30_READ_C512", "C512A100", "READ_MBPS", "<", 450, 3, 30, "Y", "512G READ 450 미만"),
    ("R30_READ_ALL", "*", "READ_MBPS", "<", 400, 3, 30, "Y", "READ 400 미만"),
    ("R30_WRITE_ALL", "*", "WRITE_MBPS", "<", 380, 4, 30, "Y", "WRITE 380 미만"),
    ("R40_LAT_E384", "E3840A01", "LAT_US", ">", 120, 2, 40, "Y", "3.84T 지연 120us 초과 B급"),
    ("R40_ECC_ALL", "*", "ECC_CNT", ">=", 5000, 2, 40, "Y", "ECC 5000 이상 B급"),
    ("R50_BAD_WARN", "*", "BAD_BLK", ">", 10, 5, 50, "Y", "불량블록 10 초과"),
    ("R05_OLD_TEMP", "*", "TEMP_MAX", ">", 70, 6, 5, "N", "구 온도기준 (미사용)"),
]
CONFIG = [("RETENTION_DAYS", "90", "테스트결과 보관일수")]
OPERS = ["김민준", "이서연", "박지호", "최수아", "정우진", "강하은", "조예준", "윤지유"]

H = dt.timedelta(hours=1)
M = dt.timedelta(minutes=1)


def seed(extra=(), products=None, rules=None):
    return seed_sql(products or PRODUCTS, BIN_CODES, rules or RULES, CONFIG, extra)


def std_jobs(d):
    return [["LOAD", d], ["JUDGE", d], ["YIELD", d]]


# ---------------------------------------------------------------------------------------------
def f01():
    fx = FixtureWriter(ROOT, "01_basic_flow", """
Basic end-to-end day: 1 ADV + 1 TER file, LOAD -> JUDGE -> YIELD.
Lot L25031201 (C512A100, 12 dev: 6 ADV + 6 TER whose KST times are before 15:00, i.e. UTC 23:xx-04:xx),
lot L25031202 (E3840A01, 10 dev). Rules R30_READ_C512 (BIN3), R40_LAT_E384 (BIN2 = pass bin),
R20_TEMP_HI (BIN6), FT2 FAIL -> DEFAULT_F. Both lots alert (83.33 < 95, 90.00 < 97).
""")
    D = "20250312"
    adv, ter = [], []
    for i in range(1, 13):
        sn = "D250312A%04d" % i
        base = kst("20250312080000") + 7 * i * M
        for step, off in (("FT1", 0), ("BI", 2), ("FT2", 5)):
            kw, res = {}, "P"
            if i == 4 and step == "FT2":
                res = "F"                       # -> BIN7 DEFAULT_F
            if i == 9 and step == "BI":
                kw["read"] = 440.0              # -> BIN3 R30_READ_C512
            a = Att(sn, "L25031201", "C512A100", step, base + off * H, res=res, dur=12,
                    oper=OPERS[i % 8], **kw)
            (adv if i <= 6 else ter).append(a)
    for i in range(1, 11):
        sn = "D250312B%04d" % i
        base = kst("20250312150000") + 6 * i * M
        for step, off in (("FT1", 0), ("BI", 1), ("FT2", 3)):
            kw = {}
            if i == 3 and step == "FT2":
                kw["lat"] = 130                 # -> BIN2 R40_LAT_E384 (pass bin)
            if i == 7 and step == "BI":
                kw["temp"] = 86                 # -> BIN6 R20_TEMP_HI
            a = Att(sn, "L25031202", "E3840A01", step, base + off * H, dur=20, oper=OPERS[(i + 3) % 8], **kw)
            (adv if i <= 5 else ter).append(a)
    fx.add("ADV_%s_01.dat" % D, adv_file(D, [a.adv() for a in adv]))
    fx.add("TER_%s_01.csv" % D, ter_file([a.ter() for a in ter]))
    fx.seed = seed()
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
def f02():
    fx = FixtureWriter(ROOT, "02_ms949_korean", """
MS949 byte semantics. ADV operator names of 2..10 bytes (record = 140 BYTES, not chars); one ADV record
padded by CHARACTERS (143 bytes) -> E01. TER operator names (UTF-8) cut to 10 MS949 bytes without
splitting a Hangul char (incl. a cut that keeps a trailing space). YIELD report PROD_NM cut to 20 bytes:
exact fit, cut ending in space, ASCII cut, cut that would split a Hangul char (-> 19 bytes + 1 pad),
short name padded. ALERT csv with Korean product name in UTF-8.
""")
    D = "20250313"
    adv = []
    names = ["김철수", "남궁민수", "제갈공명이", "이A", "박", "홍길동", "선우진", "독고"]
    for i, nm in enumerate(names, 1):
        sn = "D250313K%04d" % i
        base = kst("20250313083000") + 10 * i * M
        for step, off in (("FT1", 0), ("FT2", 3)):
            a = Att(sn, "L25031301", "C512A100", step, base + off * H, oper=nm)
            if i == 6 and step == "FT1":
                adv.append(a.adv(oper_chars=nm))     # 143 bytes -> E01 (device judged on FT2 only)
            else:
                adv.append(a.adv())
            if i == 8 and step == "FT2":
                pass
    # small lots for report truncation patterns
    for i in range(1, 4):
        adv.append(Att("D250313E%04d" % i, "L25031303", "E3840A01", "FT1", kst("20250313130000") + 9 * i * M,
                       oper="엔지니어%d" % i).adv())
        adv.append(Att("D250313F%04d" % i, "L25031304", "E7680B02", "FT1", kst("20250313140000") + 9 * i * M,
                       oper="황보", res="F" if i == 2 else "P").adv())
    for i in range(1, 3):
        adv.append(Att("D250313G%04d" % i, "L25031305", "C128T010", "FT1", kst("20250313150000") + 9 * i * M,
                       oper="정").adv())
    fx.add("ADV_%s_01.dat" % D, adv_file(D, adv))

    ter_names = ["황보영수정", "독고길동이야", "A홍길동전설", 'Lee "Jay"', "Kimberly Anne", "  박서준  ",
                 "남궁 민수 대리", "김", "Park,Jisoo", "최고의작업자입니다"]
    lines = []
    for i, nm in enumerate(ter_names, 1):
        sn = "D250313T%04d" % i
        base = kst("20250313170000") + 8 * i * M
        for step, off in (("FT1", 0), ("FT2", 2)):
            res = "F" if (i == 5 and step == "FT2") else "P"
            lines.append(Att(sn, "L25031302", "C1T0A200", step, base + off * H, oper=nm, res=res).ter())
    fx.add("TER_%s_01.csv" % D, ter_file(lines))
    fx.seed = seed()
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
def f03():
    fx = FixtureWriter(ROOT, "03_ter_csv_format", """
TER CSV parsing. File 01: UTF-8 BOM, CRLF, '#EOF,n' trailer, serial normalisation (SN prefix, lower case,
spaces, '-'), SN+ES sample, quoted fields with comma and doubled quotes, all-quoted line, padded values,
READ/WRITE 2-decimal values rounded HALF_UP to 1 decimal. File 02: no BOM, LF, no trailer, blank line,
TEMP_F -> C rounded HALF_UP (32.9 -> 1, 22.1 -> -6, 184.1 -> 85 = BIN6 where double maths gives 84).
Non-matching inbox names (other date, 1-digit seq, lower case, .bak) must stay in inbox.
""")
    D = "20250314"
    raw_serials = {1: "SN-D250314C0001", 2: "sn-d250314c0002", 3: "  D250314C0003  ", 4: "D250314-C0004",
                   5: "SNES2503140005"}
    lines = []
    for i in range(1, 11):
        sn = "D250314C%04d" % i
        base = kst("20250314100000") + 6 * i * M
        for step, off in (("FT1", 0), ("FT2", 2)):
            res = "F" if (i == 7 and step == "FT2") else "P"
            a = Att(sn, "L25031401", "C1T0A200", step, base + off * H, res=res, oper=OPERS[i % 8])
            kw = {}
            if i in raw_serials:
                kw["serial"] = raw_serials[i]
            if i == 6:
                kw["oper"] = "Kim, Minsu"
            if i == 7:
                kw["oper"] = 'Lee "Jay"'
            if i == 8:
                kw["quote"] = ("SERIAL", "LOT", "PRODUCT", "STEP", "START_UTC", "END_UTC", "TESTER", "OPERATOR",
                               "RESULT", "READ_MBPS", "WRITE_MBPS", "LAT_US", "BAD_BLK", "ECC_CNT", "TEMP_F", "FW")
            if i == 9:
                kw.update(res=" PASS ", read=" 1700.0 ", lat=" 80 ", tester=" TER-08 ")
            if i == 10:
                kw.update(read="1700.25" if step == "FT1" else "1699.95",
                          write="1400.24" if step == "FT1" else "1399.95")
            lines.append(a.ter(**kw))
    fx.add("TER_%s_01.csv" % D, ter_file(lines, bom=True, eof="auto", eol="\r\n"))

    temps = ["161.6", "32.9", "22.1", "99.5", "184.9", "184.1", "-4.0", "185", "212.0", "33.8"]
    lines2 = []
    for i, tf in enumerate(temps, 1):
        a = Att("D250314E%04d" % i, "L25031402", "C512A100", "FT1", kst("20250314180000") + 7 * i * M,
                temp_f=tf, oper="이서연")
        lines2.append(a.ter())
        if i == 5:
            lines2.append("")                    # blank line: skipped, not counted
    fx.add("TER_%s_02.csv" % D, ter_file(lines2, bom=False, eof=None, eol="\n"))

    other = [Att("D250315Z0001", "L25031501", "C512A100", "FT1", "20250315100000").ter()]
    fx.add("TER_20250315_01.csv", ter_file(other))
    fx.add("TER_%s_1.csv" % D, ter_file(other))
    fx.add("ter_%s_03.csv" % D, ter_file(other))
    fx.add("ADV_%s_01.dat.bak" % D, adv_file(D, [Att("D250314Z0002", "L25031401", "C1T0A200", "FT1",
                                                   "20250314110000").adv()]))
    fx.seed = seed()
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
def f04():
    fx = FixtureWriter(ROOT, "04_reject_codes", """
Every reject code incl. the undocumented E08 (invalid STEP) and the validation order for records with
several errors (E01, E02, E08, E03, E04, E05, E06, then E07). ADV: short record, 140-char/143-byte record,
unknown record type, blank/'SN--' serial, Feb 30, end < start, bad result, non-numeric/unsigned/space-padded
numbers, unknown and USE_YN='N' products, ' P' result (valid after trim), negative temperature.
E09: ADV trailer count mismatch, ADV without trailer, TER '#EOF' mismatch (whole file rejected,
TOTAL_CNT=REJ_CNT=detail count, one line '0|E09|<file>'). Files of other dates / .tmp stay in inbox.
""")
    D = "20250316"
    C = "C512A100"

    def A(n, step="FT1", start="20250316090000", **kw):
        return Att("D250316V%04d" % n, "L25031601", C, step, start, oper="김민준", **kw)

    recs = [
        A(1).adv(),                                                  # L2 valid
        A(2).adv()[:139],                                            # L3 E01 139 bytes
        A(3).adv(oper_chars="홍길동"),                                 # L4 E01 143 bytes / 140 chars
        A(4).adv(rectype="X"),                                       # L5 E01 unknown record type
        A(5).adv(serial=""),                                         # L6 E02 blank serial
        A(6).adv(serial="SN--"),                                     # L7 E02 serial empty after normalisation
        A(7).adv(step="FT3"),                                        # L8 E08 (undocumented)
        A(8).adv(start="20250230120000", end="20250316100000"),      # L9 E03 Feb 30
        A(9).adv(end="2025031612000A"),                              # L10 E03
        A(10).adv(start="20250316120000", end="20250316115959"),     # L11 E04
        A(11).adv(res="X"),                                          # L12 E05
        A(12).adv(res="p"),                                          # L13 E05 lower case
        A(13).adv(read="00A123"),                                    # L14 E06
        A(14).adv(temp="072 "),                                      # L15 E06 unsigned temp
        A(15).adv(bad=" 0012"),                                      # L16 E06 space padded
        A(16).adv(prod="X9999999"),                                  # L17 E07 unknown product
        A(17).adv(prod="C256Z900"),                                  # L18 E07 USE_YN = N
        A(18).adv(serial="", start="2025031612AA00"),                # L19 E02 (before E03)
        A(19).adv(start="20251316120000", prod="X9999999"),          # L20 E03 (before E07)
        A(20).adv(step="FT3", start="20250316999999"),               # L21 E08 (before E03)
        A(21).adv(res="Q", read="ABCDEF"),                           # L22 E05 (before E06)
        A(22).adv(start="20250316120000", end="20250316110000", temp="+7A1"),  # L23 E04 (before E06)
        A(23, step="FT2", start="20250316130000").adv(),             # L24 valid
        A(24).adv(res=" P"),                                         # L25 valid: ' P' trims to P
        A(25, temp=-5).adv(),                                        # L26 valid, MAX_TEMP_C = -5
    ]
    fx.add("ADV_%s_01.dat" % D, adv_file(D, recs))

    bad_trl = [Att("D250316W%04d" % i, "L25031601", C, "FT1", kst("20250316100000") + i * M).adv() for i in range(1, 5)]
    fx.add("ADV_%s_02.dat" % D, adv_file(D, bad_trl, trailer=5))           # E09 count mismatch
    no_trl = [Att("D250316X%04d" % i, "L25031601", C, "FT1", kst("20250316110000") + i * M).adv() for i in range(1, 4)]
    fx.add("ADV_%s_03.dat" % D, adv_file(D, no_trl, trailer=None))         # E09 missing trailer

    def T(n, step="FT1", start="20250316140000", **kw):
        return Att("D250316Y%04d" % n, "L25031602", "C1T0A200", step, start, oper="Lee", **kw)

    tl = [
        T(1).ter(),                                                  # L2 valid
        T(2).ter().rsplit(",", 1)[0],                                # L3 E01 15 columns
        T(3).ter(oper="Kim, Minsu").replace('"Kim, Minsu"', "Kim, Minsu"),   # L4 E01 17 columns
        T(4).ter(serial="SN"),                                       # L5 E02
        T(5).ter(serial=""),                                         # L6 E02
        T(6).ter(step="ft1"),                                        # L7 E08 (case sensitive)
        T(7).ter(start="2025-03-16 05:00:00Z"),                      # L8 E03
        T(8).ter(start="2025-03-16T05:00:00.000Z"),                  # L9 E03
        T(9).ter(end="2025-02-30T05:00:00Z"),                        # L10 E03
        T(10).ter(start="2025-03-16T05:30:00Z", end="2025-03-16T05:29:59Z"),  # L11 E04
        T(11).ter(res="Pass"),                                       # L12 E05
        T(12).ter(res="OK"),                                         # L13 E05
        T(13).ter(read="abc"),                                       # L14 E06
        T(14).ter(temp_f=""),                                        # L15 E06
        T(15).ter(lat="12.5"),                                       # L16 E06
        T(16).ter(ecc="1e3"),                                        # L17 E06
        T(17).ter(prod="C256Z900"),                                  # L18 E07
        T(18).ter(prod="c512a100"),                                  # L19 E07 (product not upper-cased)
        T(19).ter(step="FT4", res="BAD"),                            # L20 E08 (before E05)
        T(20, res="F").ter(res=" FAIL "),                            # L21 valid FAIL
    ]
    fx.add("TER_%s_01.csv" % D, ter_file(tl, bom=True, eof="auto"))
    tl2 = [Att("D250316Z%04d" % i, "L25031602", "C1T0A200", "FT1", kst("20250316150000") + i * M).ter()
           for i in range(1, 4)]
    fx.add("TER_%s_02.csv" % D, ter_file(tl2, bom=True, eof=4))           # E09 '#EOF' mismatch
    fx.add("ADV_20250315_01.dat", adv_file("20250315", [A(90, start="20250315090000").adv()]))
    fx.add("TER_%s_01.csv.tmp" % D, ter_file(tl2))
    fx.seed = seed()
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
def f05():
    fx = FixtureWriter(ROOT, "05_dup_policy", """
Duplicate (SERIAL, STEP, START_DTM) handling with production policy LAST (overwrite):
against rows already in TB_TEST_RESULT (seeded from an earlier load of ADV_20250317_01.dat),
inside one file, across files of the same run (processing order = file name order: ADV_02, ADV_03, TER_01),
and across vendors (TER UTC time == ADV KST time). DUP_CNT counts all duplicates (not in LOAD_CNT).
Corrected values change JUDGE bins (FT2 F->P, READ 430 -> BIN3, ECC 6000 -> BIN2, P->F) and yield.
""")
    D = "20250317"
    L, P = "L25031701", "C512A100"

    def dev(i):
        return "D250317D%04d" % i

    def att(i, step, res="P", **kw):
        base = kst("20250317080000") + 6 * i * M
        off = {"FT1": 0, "BI": 2, "FT2": 5}[step]
        return Att(dev(i), L, P, step, base + off * H, res=res, oper=OPERS[i % 8], **kw)

    pre = []
    for i in range(1, 7):
        for step in ("FT1", "BI", "FT2"):
            pre.append(att(i, step, res="F" if (i == 1 and step == "FT2") else "P"))
    extra = [test_result_insert(a, "ADV", "ADV_20250317_01.dat", D) for a in pre]
    extra.append(file_log_insert(1, "ADV_20250317_01.dat", "ADV", D, 18, 18, 0, 0, "S"))
    fx.seed = seed(extra)

    f2 = [
        att(1, "FT2", res="P").adv(),                                # dup vs DB: F -> P   (BIN7 -> BIN1)
        att(2, "FT2", read=430.0).adv(),                             # dup vs DB: READ 430 (BIN1 -> BIN3)
        att(3, "FT1").adv(),                                         # dup vs DB, identical
        Att(dev(7), L, P, "FT1", "20250317100000", oper="강하은").adv(),
        Att(dev(7), L, P, "FT1", "20250317100000", oper="강하은", res="F").adv(),   # dup in same file -> F
        att(8, "FT1").adv(), att(8, "BI").adv(), att(8, "FT2").adv(),
        Att(dev(9), L, P, "FT1", "20250317100000", res="F", oper="조예준").adv(),   # overwritten by TER
        Att(dev(4), L, P, "FT2", "20250317143000", res="F", oper="박지호").adv(),   # 2nd FT2 attempt (not dup)
    ]
    fx.add("ADV_%s_02.dat" % D, adv_file(D, f2, create_time="150000"))
    f3 = [
        att(8, "FT2", res="F").adv(),                                # dup vs earlier file in same run -> F
        att(5, "BI", fw="SA21C06").adv(),                            # dup vs DB, only FW differs
    ]
    fx.add("ADV_%s_03.dat" % D, adv_file(D, f3, create_time="153000"))
    t1 = [
        Att(dev(9), L, P, "FT1", "20250317100000", oper="조예준").ter(),           # KST 10:00 == ADV -> dup, P wins
        att(6, "BI", ecc=6000).ter(),                                # dup vs DB via UTC time -> ECC 6000 (BIN2)
    ]
    for step, st in (("FT1", "20250317160000"), ("BI", "20250317180000"), ("FT2", "20250317210000")):
        t1.append(Att(dev(10), L, P, step, st, oper="윤지유").ter())
    fx.add("TER_%s_01.csv" % D, ter_file(t1))
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
def f06():
    fx = FixtureWriter(ROOT, "06_shift_boundary_tz", """
WORK_DT = production day with 06:00 shift boundary in plant time (KST). ADV: 00:00:00, 05:59:59 -> previous
day; 06:00:00, 23:59:59 -> same day; device split over two work days. TER (UTC): 20:59:59Z/21:00:00Z,
15:00:00Z (= KST midnight), records whose UTC date differs from KST date, end crossing midnight.
JUDGE and YIELD run for 0317, 0318, 0319. Only correct when UTC->KST conversion and WORK_DT derivation
use Asia/Seoul (JVM default TZ in production).
""")
    D = "20250318"
    adv = []
    L1, L2, P = "L25031801", "L25031802", "C1T0A200"
    adv.append(Att("D250318W0001", L1, P, "FT1", "20250318000000").adv())          # 0317
    adv.append(Att("D250318W0002", L1, P, "FT1", "20250318055959").adv())          # 0317
    adv.append(Att("D250318W0003", L1, P, "FT1", "20250318060000").adv())          # 0318
    adv.append(Att("D250318W0004", L1, P, "FT1", "20250318235959").adv())          # 0318 (ends next day)
    adv.append(Att("D250318W0005", L1, P, "FT1", "20250318053000", res="F").adv())  # 0317 -> BIN7 on 0317
    adv.append(Att("D250318W0005", L1, P, "FT2", "20250318070000").adv())          # 0318 -> BIN1 on 0318
    adv.append(Att("D250318W0006", L1, P, "FT1", "20250317230000").adv())          # 0317
    adv.append(Att("D250318W0007", L1, P, "BI", "20250318120000", temp=85).adv())  # 0318 -> BIN6
    fx.add("ADV_%s_01.dat" % D, adv_file(D, adv))

    def T(sn, start_utc, end_utc=None, res="P", **kw):
        st = dt.datetime.strptime(start_utc, "%Y-%m-%dT%H:%M:%SZ") + 9 * H
        en = (dt.datetime.strptime(end_utc, "%Y-%m-%dT%H:%M:%SZ") + 9 * H) if end_utc else None
        return Att(sn, L2, P, kw.pop("step", "FT1"), st, end=en, res=res, **kw).ter()

    ter = [
        T("D250318W0011", "2025-03-17T20:59:59Z"),     # KST 03-18 05:59:59 -> 0317
        T("D250318W0012", "2025-03-17T21:00:00Z"),     # KST 03-18 06:00:00 -> 0318
        T("D250318W0013", "2025-03-17T15:00:00Z"),     # KST 03-18 00:00:00 -> 0317
        T("D250318W0014", "2025-03-18T14:59:59Z"),     # KST 03-18 23:59:59 -> 0318
        T("D250318W0015", "2025-03-18T15:00:00Z"),     # KST 03-19 00:00:00 -> 0318
        T("D250318W0016", "2025-03-18T20:59:59Z"),     # KST 03-19 05:59:59 -> 0318
        T("D250318W0017", "2025-03-18T21:00:00Z"),     # KST 03-19 06:00:00 -> 0319
        T("D250318W0018", "2025-03-17T23:30:00Z"),     # KST 03-18 08:30 -> 0318 (UTC date 03-17)
        T("D250318W0019", "2025-03-18T14:50:00Z", "2025-03-18T15:20:00Z"),   # end crosses KST midnight
        T("D250318W0020", "2025-03-18T00:10:00Z", res="F"),                  # KST 09:10 FT1 F
        T("D250318W0020", "2025-03-18T05:00:00Z", step="FT2"),               # KST 14:00 FT2 P -> BIN7
        T("D250318W0021", "2025-03-18T03:00:00Z", read=390.0),               # KST 12:00 -> BIN3 R30_READ_ALL
    ]
    fx.add("TER_%s_01.csv" % D, ter_file(ter))
    fx.seed = seed()
    fx.jobs = [["LOAD", D], ["JUDGE", "20250317"], ["JUDGE", D], ["JUDGE", "20250319"],
               ["YIELD", "20250317"], ["YIELD", D], ["YIELD", "20250319"]]
    fx.write()


# ---------------------------------------------------------------------------------------------
def f07():
    fx = FixtureWriter(ROOT, "07_retest_attempts", """
Retest limit: per (SERIAL, STEP) only the first 3 attempts (by START_DTM) count, effective attempt =
last counted (design doc and Constants.MAX_RETEST say 5 - not used). Cases with 1..5 attempts, ignored
4th/5th PASS/ABORT/bad READ, ABORT only when in the effective attempt, rules evaluated on effective
attempts only, attempts interleaved across ADV and TER (ordering needs correct UTC->KST conversion).
""")
    D = "20250319"
    L, P = "L25031901", "C1T0A200"
    adv, ter = [], []

    def seq(n, step, results, start="20250319090000", gap=40, vendor="ADV", measures=None):
        st = kst(start)
        for k, r in enumerate(results):
            m = (measures or {}).get(k, {})
            a = Att("D250319R%04d" % n, L, P, step, st + k * gap * M, res=r, oper=OPERS[n % 8], **m)
            (adv if vendor == "ADV" else ter).append(a)

    seq(1, "FT1", "P")                                   # BIN1
    seq(2, "FT1", "FP")                                  # BIN1
    seq(3, "FT1", "FFP")                                 # BIN1
    seq(4, "FT1", "FFFP")                                # 4th ignored -> BIN7
    seq(5, "FT1", "FFFFP")                               # BIN7
    seq(6, "FT1", "PPPA")                                # 4th ABORT ignored -> BIN1
    seq(7, "FT1", "AP")                                  # BIN1
    seq(8, "FT1", "PA")                                  # BIN8 ABORT
    seq(9, "BI", "PPFP")                                 # BIN7
    seq(10, "FT1", "PP", measures={0: {"read": 380.0}})  # 1st READ 380 not effective -> BIN1
    seq(11, "FT2", "PPPP", measures={3: {"read": 350.0}})  # 4th READ 350 ignored -> BIN1
    # R12: ADV 16:00 P, TER 16:30 F, ADV 17:00 F, TER 17:30 P -> 3rd (ADV 17:00 F) effective -> BIN7
    adv.append(Att("D250319R0012", L, P, "FT1", "20250319160000", res="P", oper="최수아"))
    ter.append(Att("D250319R0012", L, P, "FT1", "20250319163000", res="F", oper="최수아"))
    adv.append(Att("D250319R0012", L, P, "FT1", "20250319170000", res="F", oper="최수아"))
    ter.append(Att("D250319R0012", L, P, "FT1", "20250319173000", res="P", oper="최수아"))
    seq(13, "FT1", "P", start="20250319080000")
    seq(13, "BI", "FP", start="20250319100000")
    seq(13, "FT2", "PPPF", start="20250319130000")       # 3rd P effective -> BIN1
    seq(14, "FT1", "FP", vendor="TER")                   # KST 09:00/09:40 = UTC 00:00/00:40 -> BIN1
    fx.add("ADV_%s_01.dat" % D, adv_file(D, [a.adv() for a in adv]))
    fx.add("TER_%s_01.csv" % D, ter_file([a.ter() for a in ter]))
    fx.seed = seed()
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
F08_RULES = [
    ("P10_TEMP_CRIT", "*", "TEMP_MAX", ">=", 90, 6, 10, "Y", "온도 90 이상"),
    ("P10_BAD_SCRAP", "*", "BAD_BLK", ">", 60, 9, 10, "Y", "불량블록 60 초과 폐기"),
    ("P15_UNKNOWN", "*", "RETRY_CNT", ">", 0, 7, 15, "Y", "미구현 항목"),
    ("P20_READ_C1T", "C1T0A200", "READ_MBPS", "<=", 1500, 4, 20, "Y", "1TB READ 1500 이하"),
    ("P20_READ_ALL", "*", "READ_MBPS", "<", 1600, 3, 20, "Y", "READ 1600 미만"),
    ("P30_WRITE_ALL", "*", "WRITE_MBPS", "<", 1200, 4, 30, "Y", "WRITE 1200 미만"),
    ("P30_ECC_ALL", "*", "ECC_CNT", ">=", 8000, 2, 30, "Y", "ECC 8000 이상 B급"),
    ("P40_LAT_ALL", "*", "LAT_US", ">", 150, 7, 40, "Y", "지연 150 초과"),
    ("P50_E384_LAT", "E3840A01", "LAT_US", ">=", 100, 2, 50, "Y", "3.84T 지연 100 이상 B급"),
    ("P05_DISABLED", "*", "TEMP_MAX", ">", 0, 6, 5, "N", "미사용"),
    ("P01_OTHER", "C512A100", "READ_MBPS", "<", 9999, 3, 1, "Y", "타 제품 전용"),
]


def f08():
    fx = FixtureWriter(ROOT, "08_rules_override", """
BIN rule evaluation with a dedicated rule table: PRIORITY asc, product-specific before '*', BIN_NO desc;
USE_YN='N' ignored, unknown ITEM_CD skipped, rule for another product never applies; operators < <= > >=
at exact thresholds; READ/WRITE use MIN over effective steps, LAT/BAD/ECC/TEMP use MAX. Hard-coded
enterprise override (PROD_CD 'E%' and max BAD_BLK > 20 -> BIN5 OVR_E) runs BEFORE rules, ABORT before it.
ADV only (time-zone independent).
""")
    D = "20250320"
    recs = []
    t0 = kst("20250320083000")

    def dev(sn, lot, prod, steps):
        nonlocal t0
        for step, kw in steps:
            kw = dict(kw)
            res = kw.pop("res", "P")
            recs.append(Att(sn, lot, prod, step, t0, res=res, oper="정우진", **kw).adv())
            t0 += 7 * M

    G, E = "C1T0A200", "E3840A01"
    LG, LE = "L25032001", "L25032002"
    dev("D250320G0001", LG, G, [("FT1", {}), ("FT2", {})])                        # BIN1 DEFAULT
    dev("D250320G0002", LG, G, [("FT1", {}), ("FT2", {"temp": 90})])              # BIN6 P10_TEMP_CRIT (>=)
    dev("D250320G0003", LG, G, [("FT1", {"temp": 89}), ("FT2", {})])              # BIN1
    dev("D250320G0004", LG, G, [("FT1", {"temp": 95}), ("FT2", {"bad": 61})])     # BIN9 (same prio, BIN desc)
    dev("D250320G0005", LG, G, [("FT1", {"bad": 60}), ("FT2", {})])               # BIN1 (> 60 strict)
    dev("D250320G0006", LG, G, [("FT1", {"read": 1500.0}), ("FT2", {})])          # BIN4 specific first
    dev("D250320G0007", LG, G, [("FT1", {}), ("FT2", {"read": 1550.0})])          # BIN3 P20_READ_ALL (MIN)
    dev("D250320G0008", LG, G, [("FT1", {"read": 1600.0}), ("FT2", {})])          # BIN1 (< 1600 strict)
    dev("D250320G0009", LG, G, [("FT1", {"write": 1199.9}), ("FT2", {"ecc": 8000})])  # BIN4 (BIN desc)
    dev("D250320G0010", LG, G, [("FT1", {"ecc": 8000}), ("FT2", {})])             # BIN2 P30_ECC_ALL (>=)
    dev("D250320G0011", LG, G, [("FT1", {"lat": 150}), ("FT2", {})])              # BIN1 (> 150 strict)
    dev("D250320G0012", LG, G, [("FT1", {}), ("FT2", {"lat": 151})])              # BIN7 P40_LAT_ALL
    dev("D250320G0013", LG, G, [("FT1", {}), ("FT2", {"res": "F"})])              # BIN7 DEFAULT_F
    dev("D250320G0014", LG, G, [("FT1", {"res": "F"}), ("FT2", {"read": 1550.0})])  # BIN3 rule before default
    dev("D250320G0015", LG, G, [("FT1", {"bad": 25}), ("FT2", {})])               # BIN1 (override only 'E')
    dev("D250320H0001", LE, E, [("FT1", {}), ("FT2", {})])                        # BIN1
    dev("D250320H0002", LE, E, [("FT1", {"bad": 5}), ("FT2", {"bad": 21})])       # BIN5 OVR_E (MAX)
    dev("D250320H0003", LE, E, [("FT1", {"bad": 20}), ("FT2", {})])               # BIN1 (> 20 strict)
    dev("D250320H0004", LE, E, [("FT1", {"bad": 25, "temp": 92}), ("FT2", {})])   # BIN5 override before rules
    dev("D250320H0005", LE, E, [("FT1", {"bad": 70}), ("FT2", {})])               # BIN5 (not BIN9 rule)
    dev("D250320H0006", LE, E, [("FT1", {"bad": 30}), ("FT2", {"res": "A"})])     # BIN8 ABORT first
    dev("D250320H0007", LE, E, [("FT1", {"lat": 100}), ("FT2", {})])              # BIN2 P50_E384_LAT (>=)
    dev("D250320H0008", LE, E, [("FT1", {"lat": 99}), ("FT2", {})])               # BIN1
    dev("D250320H0009", LE, E, [("FT1", {"read": 1550.0}), ("FT2", {})])          # BIN3 wildcard rule
    dev("D250320H0010", LE, E, [("FT1", {"write": 1200.0}), ("FT2", {})])         # BIN1 (< 1200 strict)
    fx.add("ADV_%s_01.dat" % D, adv_file(D, recs))
    fx.seed = seed(rules=F08_RULES)
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
def f09():
    fx = FixtureWriter(ROOT, "09_scrap_es", """
Scrap stickiness: BIN 9 in TB_DEVICE_BIN for an EARLIER work day -> BIN9 SCRAP_KEEP (beats ABORT);
BIN 9 on a later day or on the same day (re-judge) is not sticky; BIN 9 assigned by a rule today keeps
the rule id. Engineering samples (serial starts with 'ES' after normalisation, incl. TER 'SN-ES..' and
lower case) are judged but EXCL_YN='Y' and excluded from yield; 'ES' inside a serial does not count;
a lot of only ES devices produces no yield row.
""")
    D = "20250321"
    L1, L2, P = "L25032101", "L25032102", "C512A100"
    extra = [
        device_bin_insert("D250321S0001", "20250320", P, "L25032001", 9, "R10_BAD_SCRAP"),
        device_bin_insert("D250321S0002", "20250310", P, "L25031001", 9, "R10_BAD_SCRAP"),
        device_bin_insert("D250321S0003", "20250322", P, "L25032201", 9, "R10_BAD_SCRAP"),
        device_bin_insert("D250321S0004", "20250320", P, "L25032001", 7, "DEFAULT_F"),
        device_bin_insert("D250321S0005", "20250321", P, L1, 9, "R10_BAD_SCRAP"),
        device_bin_insert("D250321S0006", "20250315", P, "L25031501", 9, "SCRAP_KEEP"),
        device_bin_insert("ES2503210003", "20250319", P, "L25031901", 9, "R10_BAD_SCRAP", "Y"),
    ]
    fx.seed = seed(extra)
    adv = []
    t = kst("20250321090000")

    def A(sn, lot=L1, **kw):
        nonlocal t
        a = Att(sn, lot, P, kw.pop("step", "FT1"), t, oper="최수아", **kw)
        t += 9 * M
        return a

    adv.append(A("D250321S0001").adv())                 # SCRAP_KEEP (scrap on 0320)
    adv.append(A("D250321S0002").adv())                 # SCRAP_KEEP (scrap on 0310)
    adv.append(A("D250321S0003").adv())                 # BIN1 (scrap only on later day 0322)
    adv.append(A("D250321S0004").adv())                 # BIN1 (earlier BIN7 not sticky)
    adv.append(A("D250321S0005").adv())                 # BIN1 (same-day BIN9 replaced by MERGE)
    adv.append(A("D250321S0006", res="A").adv())        # SCRAP_KEEP beats ABORT
    adv.append(A("D250321S0007", bad=55).adv())         # BIN9 by rule R10_BAD_SCRAP
    adv.append(A("D250321S0008").adv())                 # BIN1
    adv.append(A("D250321ES01").adv())                  # 'ES' not prefix -> counted, BIN1
    adv.append(A("ES2503210001").adv())                 # ES, BIN1, excluded
    adv.append(A("ES2503210002", res="F").adv())        # ES, BIN7, excluded
    adv.append(A("ES2503210003").adv())                 # ES with earlier scrap -> SCRAP_KEEP, excluded
    for i in range(1, 4):
        adv.append(A("ES25032102%02d" % i, lot=L2).adv())   # lot with only ES -> no yield row
    fx.add("ADV_%s_01.dat" % D, adv_file(D, adv))
    ter = [
        Att("ES2503210004", L1, P, "FT1", "20250321160000", oper="Choi").ter(serial="SN-ES2503210004"),
        Att("ES2503210005", L1, P, "FT1", "20250321161000", oper="Choi").ter(serial="es2503210005"),
        Att("D250321S0009", L1, P, "FT1", "20250321162000", oper="Choi").ter(serial="SN-D250321S0009"),
        Att("D250321S0010", L1, P, "FT1", "20250321163000", oper="Choi", res="F").ter(),
    ]
    fx.add("TER_%s_01.csv" % D, ter_file(ter))
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
F10_PRODUCTS = [
    ("C512A100", "클라이언트 SSD 512GB 보급형", "CLIENT", 66.67, "Y"),
    ("C1T0A200", "클라이언트 NVMe 1TB 고성능", "CLIENT", 63.64, "Y"),
    ("C128T010", "보급형 128G", "CLIENT", 99.99, "Y"),
    ("E3840A01", "엔터프라이즈 NVMe SSD 3.84TB", "ENT", 90.00, "Y"),
    ("E7680B02", "X 데이터센터용 고성능 드라이브", "ENT", None, "Y"),
]


def f10():
    fx = FixtureWriter(ROOT, "10_yield_trunc_alert", """
YIELD_PCT is TRUNCATED to 2 decimals (code comment and design doc say rounding): 8/12 -> 66.66 (alert
vs 66.67 threshold), 7/11 -> 63.63 (alert vs 63.64), 1/7 -> 14.28, 2/3, 1/3, 5/6, 0/12, 199/200 -> 099.50,
15/15 -> 100.00. Alert only when YIELD < ALERT_YIELD (strict) and IN_QTY >= 10 (9 -> no alert, 10 -> alert);
NULL ALERT_YIELD never alerts. BIN2 counts as pass (TB_BIN_CODE.PASS_YN). Report ordering by PROD_CD, LOT_ID.
""")
    D = "20250322"
    adv, ter = [], []
    t = [kst("20250322070000")]

    def lot(lot_id, prod, n_in, n_pass, n_bin2=0, vendor="ADV", start=None):
        if start:
            t[0] = kst(start)
        for i in range(1, n_in + 1):
            kw, res = {}, "P"
            if i > n_pass:
                res = "F"
            elif i <= n_bin2:
                kw["ecc"] = 6000             # R40_ECC_ALL -> BIN2 (pass bin)
            a = Att("D%s%03d" % (lot_id[1:], i), lot_id, prod, "FT1", t[0], res=res, dur=4, oper="강하은", **kw)
            t[0] += 2 * M
            (adv if vendor == "ADV" else ter).append(a)

    lot("L25032201", "C512A100", 12, 8, n_bin2=2)   # 66.66 < 66.67 -> Y
    lot("L25032202", "C512A100", 3, 2)              # 66.66, IN 3 -> N
    lot("L25032203", "C1T0A200", 11, 7)             # 63.63 < 63.64 -> Y
    lot("L25032204", "C1T0A200", 10, 6)             # 60.00, IN 10 -> Y
    lot("L25032205", "C1T0A200", 9, 1)              # 11.11, IN 9 -> N
    lot("L25032206", "E3840A01", 10, 9)             # 90.00 == 90.00 -> N
    lot("L25032207", "E3840A01", 7, 1)              # 14.28, IN 7 -> N
    lot("L25032208", "E7680B02", 12, 0)             # 0.00, NULL alert -> N
    lot("L25032209", "C128T010", 200, 199)          # 99.50 < 99.99 -> Y
    lot("L25032211", "E7680B02", 6, 5)              # 83.33
    lot("L25032212", "C512A100", 3, 1)              # 33.33
    lot("L25032210", "C128T010", 15, 15, vendor="TER", start="20250322170000")   # 100.00 -> N
    fx.add("ADV_%s_01.dat" % D, adv_file(D, [a.adv() for a in adv]))
    fx.add("TER_%s_01.csv" % D, ter_file([a.ter() for a in ter]))
    fx.seed = seed(products=F10_PRODUCTS)
    fx.jobs = std_jobs(D)
    fx.write()


# ---------------------------------------------------------------------------------------------
def f11():
    fx = FixtureWriter(ROOT, "11_rerun_noalert", """
Re-run safety and ops contract: YIELD twice, late night-shift records (next day's file, WORK_DT of the
previous day) followed by JUDGE/YIELD re-run (MERGE updates, delete+insert, report overwritten, ALERT
appears). No ALERT file when there are no alerts. YIELD on a day without data -> header/trailer only.
Invalid calls must exit non-zero: impossible date, unknown JOB_ID, 7-digit date.
""")
    adv23, ter23, adv24 = [], [], []
    for i in range(1, 11):
        base = kst("20250323080000") + 5 * i * M
        for step, off in (("FT1", 0), ("FT2", 3)):
            adv23.append(Att("D250323N%04d" % i, "L25032301", "C512A100", step, base + off * H, oper="김민준"))
    for i in range(1, 11):
        base = kst("20250323150000") + 5 * i * M
        for step, off in (("FT1", 0), ("FT2", 2)):
            ter23.append(Att("D250323M%04d" % i, "L25032302", "E3840A01", step, base + off * H, oper="Kim"))
    adv24.append(Att("D250323N0003", "L25032301", "C512A100", "FT2", "20250324020000", res="F"))  # WORK_DT 0323
    adv24.append(Att("D250323N0004", "L25032301", "C512A100", "FT2", "20250324030000", res="F"))  # WORK_DT 0323
    adv24.append(Att("D250323N0011", "L25032301", "C512A100", "FT1", "20250324040000"))           # WORK_DT 0323
    for i in range(1, 6):
        adv24.append(Att("D250324Q%04d" % i, "L25032401", "C1T0A200", "FT1",
                         kst("20250324090000") + 10 * i * M))                                     # WORK_DT 0324
    fx.add("ADV_20250323_01.dat", adv_file("20250323", [a.adv() for a in adv23]))
    fx.add("TER_20250323_01.csv", ter_file([a.ter() for a in ter23]))
    fx.add("ADV_20250324_01.dat", adv_file("20250324", [a.adv() for a in adv24]))
    fx.seed = seed()
    fx.jobs = [["LOAD", "20250323"], ["JUDGE", "20250323"], ["YIELD", "20250323"], ["YIELD", "20250323"],
               ["LOAD", "20250324"], ["JUDGE", "20250323"], ["YIELD", "20250323"],
               ["JUDGE", "20250324"], ["YIELD", "20250324"], ["YIELD", "20250325"],
               ["JUDGE", "20250230"], ["REPORT", "20250323"], ["LOAD", "2025032"]]
    fx.write()


# ---------------------------------------------------------------------------------------------
def f12():
    fx = FixtureWriter(ROOT, "12_full_day_mixed", """
Production-like day (seeded random): 2 ADV + 2 TER files, ~140 devices in 5 lots / 4 products, retests up
to 4 attempts, rule hits, aborts, ES samples, SN-prefixed TER serials, a few rejects, duplicates across
files (LAST wins) and night-shift records belonging to the previous work day (JUDGE/YIELD for 0324 and 0325).
""")
    D = "20250325"
    rnd = random.Random(20250325)
    lots = [("L25032501", "C512A100", 40), ("L25032502", "C1T0A200", 35), ("L25032503", "E3840A01", 30),
            ("L25032504", "E7680B02", 25), ("L25032505", "C512A100", 9)]
    files = {"ADV_01": [], "ADV_02": [], "TER_01": [], "TER_02": []}
    raw_ser = {}
    dups = []
    n_es = 0
    for li, (lot_id, prod, n) in enumerate(lots):
        for i in range(1, n + 1):
            sn = "D%s%03d" % (lot_id[1:], i)
            if rnd.random() < 0.04 and n_es < 4:
                sn = "ES%s%02d" % (lot_id[3:], i)
                n_es += 1
            vendor = "ADV" if rnd.random() < 0.6 else "TER"
            fkey = vendor + ("_01" if li < 2 else "_02")
            # night shift of previous work day for ~8% devices
            if rnd.random() < 0.08:
                t = kst("20250325000000") + rnd.randint(0, 200) * M
            else:
                t = kst("20250325060000") + rnd.randint(0, 660) * M
            for step in ("FT1", "BI", "FT2"):
                n_try = rnd.choices([1, 2, 3, 4], weights=[88, 8, 3, 1])[0]
                for k in range(n_try):
                    last = (k == n_try - 1)
                    if last:
                        res = rnd.choices("PFA", weights=[96, 3, 1])[0]
                    else:
                        res = rnd.choices("FPA", weights=[80, 15, 5])[0]
                    kw = {}
                    r = rnd.random()
                    base = Att(sn, lot_id, prod, step, t)
                    if r < 0.012:
                        kw["read"] = round(base.read * rnd.uniform(0.6, 0.8), 1)
                    elif r < 0.020:
                        kw["temp"] = rnd.randint(84, 90)
                    elif r < 0.028:
                        kw["bad"] = rnd.choice([12, 18, 22, 35, 55])
                    elif r < 0.040:
                        kw["ecc"] = rnd.randint(4800, 7000)
                    elif r < 0.046:
                        kw["lat"] = rnd.randint(110, 140)
                    kw["read"] = kw.get("read", round(base.read + rnd.uniform(-15, 15), 1))
                    kw["write"] = round(base.write + rnd.uniform(-15, 15), 1)
                    a = Att(sn, lot_id, prod, step, t, res=res, dur=rnd.randint(8, 25),
                            oper=rnd.choice(OPERS), **kw)
                    files[fkey].append(a)
                    if vendor == "TER" and rnd.random() < 0.3:
                        raw_ser[id(a)] = "SN-" + sn if rnd.random() < 0.7 else sn[:7] + "-" + sn[7:]
                    if rnd.random() < 0.03:
                        dups.append((fkey, a))
                    t += rnd.randint(25, 70) * M
    # duplicates re-sent in the "other" file of the same vendor family with changed result/measure
    for fkey, a in dups:
        other = {"ADV_01": "ADV_02", "ADV_02": "ADV_01", "TER_01": "TER_02", "TER_02": "TER_01"}[fkey]
        b = Att(a.serial, a.lot, a.prod, a.step, a.start, end=a.end, res="F" if a.res == "P" else "P",
                oper=a.oper, read=a.read, write=a.write, lat=a.lat, bad=a.bad, ecc=a.ecc + 1, temp=a.temp)
        files[other].append(b)
    out_adv = {}
    for fkey in ("ADV_01", "ADV_02"):
        recs = [a.adv() for a in files[fkey]]
        out_adv[fkey] = recs
    # a few corrupted records
    out_adv["ADV_01"].insert(5, files["ADV_01"][5].adv(res="X"))
    out_adv["ADV_01"].insert(17, files["ADV_01"][17].adv(read="0A1234"))
    out_adv["ADV_02"].insert(9, files["ADV_02"][9].adv(start="20250325250000"))
    for fkey in ("ADV_01", "ADV_02"):
        fx.add("ADV_%s_%s.dat" % (D, fkey[-2:]), adv_file(D, out_adv[fkey]))
    for fkey in ("TER_01", "TER_02"):
        lines = [a.ter(serial=raw_ser.get(id(a))) for a in files[fkey]]
        lines.insert(7, files[fkey][7].ter(read="n/a"))
        fx.add("TER_%s_%s.csv" % (D, fkey[-2:]), ter_file(lines, bom=(fkey == "TER_01")))
    fx.seed = seed()
    fx.jobs = [["LOAD", D], ["JUDGE", "20250324"], ["JUDGE", D], ["YIELD", "20250324"], ["YIELD", D]]
    fx.write()


ALL = [f01, f02, f03, f04, f05, f06, f07, f08, f09, f10, f11, f12]

if __name__ == "__main__":
    sel = sys.argv[1:]
    for f in ALL:
        if not sel or any(f.__name__ == s for s in sel):
            f()
            print("generated", f.__name__)
