#!/usr/bin/env python3
"""
Generate hidden/provided_on_request/ : what the operator hands over when asked.
  samples/      2 ADV + 2 TER realistic production files of 2024-11-07 (not used by any fixture)
  master_data/  CSV exports of TB_PRODUCT, TB_BIN_RULE, TB_BIN_CODE, TB_SYS_CONFIG
                (production master data - deliberately different from every fixture seed)
"""
import csv
import datetime as dt
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fxlib import Att, adv_file, kst, ter_file  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "provided_on_request"

PRODUCTS = [
    ("C256A110", "클라이언트 SATA 256GB", "CLIENT", "94.00", "Y", "2016-02-11 10:22:31"),
    ("C512B300", "클라이언트 SATA 512GB 2세대", "CLIENT", "95.00", "Y", "2017-06-02 14:05:10"),
    ("C1T0N100", "클라이언트 NVMe 1TB 표준형", "CLIENT", "93.00", "Y", "2018-03-19 09:41:55"),
    ("C2T0N210", "클라이언트 NVMe 2TB 고성능", "CLIENT", "92.50", "Y", "2021-08-23 16:30:02"),
    ("E1920C05", "엔터프라이즈 SAS 1.92TB", "ENT", "97.50", "Y", "2016-05-30 11:12:44"),
    ("E3840D11", "엔터프라이즈 NVMe 3.84TB 2세대", "ENT", "97.00", "Y", "2020-11-09 13:20:18"),
    ("E7680D20", "데이터센터 U.2 7.68TB", "ENT", "96.00", "Y", "2022-04-14 08:55:37"),
    ("C128S900", "보급형 SATA 128GB (단종)", "CLIENT", "90.00", "N", "2015-09-01 09:00:00"),
    ("T0000001", "테스트용 더미 제품", "ETC", "", "N", "2015-09-01 09:00:00"),
]
BIN_CODES = [
    ("1", "양품", "Y"), ("2", "양품(B급)", "Y"), ("3", "READ 미달", "N"), ("4", "WRITE 미달", "N"),
    ("5", "불량블록 과다", "N"), ("6", "온도 이상", "N"), ("7", "기능 불량", "N"), ("8", "테스트 중단", "N"),
    ("9", "폐기(SCRAP)", "N"),
]
RULES = [
    ("RB010_SCRAP", "*", "BAD_BLK", ">", "80", "9", "10", "Y", "불량블록 80 초과 폐기"),
    ("RT020_TEMP", "*", "TEMP_MAX", ">=", "88", "6", "20", "Y", "최고온도 88도 이상"),
    ("RT021_TEMP_E", "E3840D11", "TEMP_MAX", ">=", "83", "6", "20", "Y", "3.84T 2세대 온도 83도 이상"),
    ("RR030_C256", "C256A110", "READ_MBPS", "<", "480", "3", "30", "Y", "256G READ 480 미만"),
    ("RR031_C512", "C512B300", "READ_MBPS", "<", "500", "3", "30", "Y", "512G READ 500 미만"),
    ("RR032_C1T", "C1T0N100", "READ_MBPS", "<", "1550", "3", "30", "Y", "1TB READ 1550 미만"),
    ("RR033_C2T", "C2T0N210", "READ_MBPS", "<", "3000", "3", "30", "Y", "2TB READ 3000 미만"),
    ("RR039_ALL", "*", "READ_MBPS", "<", "400", "3", "30", "Y", "READ 400 미만 공통"),
    ("RW040_ALL", "*", "WRITE_MBPS", "<", "350", "4", "40", "Y", "WRITE 350 미만 공통"),
    ("RW041_E192", "E1920C05", "WRITE_MBPS", "<", "900", "4", "40", "Y", "1.92T WRITE 900 미만"),
    ("RL050_E768", "E7680D20", "LAT_US", ">", "110", "2", "50", "Y", "7.68T 지연 110us 초과 B급"),
    ("RE060_ECC", "*", "ECC_CNT", ">=", "6000", "2", "60", "Y", "ECC 6000 이상 B급"),
    ("RB070_BAD", "*", "BAD_BLK", ">", "15", "5", "70", "Y", "불량블록 15 초과"),
    ("RX005_OLD", "*", "TEMP_MAX", ">", "75", "6", "5", "N", "구 온도 기준 (2016.08 폐기)"),
    ("RX006_TEST", "T0000001", "READ_MBPS", "<", "99999", "7", "1", "N", "테스트용"),
]
CONFIG = [
    ("RETENTION_DAYS", "90", "테스트결과 보관일수"),
    ("MES_IF_DIR", "/data/tlog/outbox", "MES 연계 디렉토리 (참고용)"),
    ("ALERT_MAIL_GROUP", "quality-yield", "수율 경보 메일 그룹 (메일 스크립트 사용)"),
]


def export(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    (OUT / "master_data" / name).write_text(buf.getvalue(), encoding="utf-8")


def master():
    (OUT / "master_data").mkdir(parents=True, exist_ok=True)
    export("TB_PRODUCT.csv", ["PROD_CD", "PROD_NM", "PROD_GRP", "ALERT_YIELD", "USE_YN", "REG_DTM"], PRODUCTS)
    export("TB_BIN_CODE.csv", ["BIN_NO", "BIN_NM", "PASS_YN"], BIN_CODES)
    export("TB_BIN_RULE.csv", ["RULE_ID", "PROD_CD", "ITEM_CD", "OPER_CD", "THRESHOLD", "BIN_NO", "PRIORITY",
                               "USE_YN", "RULE_DESC"], RULES)
    export("TB_SYS_CONFIG.csv", ["CFG_KEY", "CFG_VAL", "CFG_DESC"], CONFIG)


def samples():
    d = OUT / "samples"
    d.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(20241107)
    opers = ["오세훈", "한지우", "서민재", "문채원", "백승호", "장예린", "권도윤", "노하은"]

    def device_attempts(sn, lot, prod, start):
        out, t = [], start
        for step in ("FT1", "BI", "FT2"):
            tries = rnd.choices([1, 2, 3], weights=[90, 8, 2])[0]
            for k in range(tries):
                res = "P" if k == tries - 1 and rnd.random() < 0.95 else rnd.choice("FFFA")
                a = Att(sn, lot, prod, step, t, res=res, dur=rnd.randint(10, 22), oper=rnd.choice(opers),
                        tester="ADVT0%d" % rnd.randint(1, 4))
                a.read = round(a.read + rnd.uniform(-20, 20), 1)
                a.write = round(a.write + rnd.uniform(-20, 20), 1)
                a.ecc = a.ecc + rnd.randint(-150, 150)
                a.temp = a.temp + rnd.randint(-3, 4)
                out.append(a)
                t += dt.timedelta(minutes=rnd.randint(30, 80))
        return out

    adv1, adv2, ter1, ter2 = [], [], [], []
    for i in range(1, 9):
        adv1 += device_attempts("K241107A%04d" % i, "L24110701", "C1T0N100",
                                kst("20241107070000") + dt.timedelta(minutes=11 * i))
    for i in range(1, 7):
        adv2 += device_attempts("K241107B%04d" % i, "L24110702", "C512B300",
                                kst("20241107131500") + dt.timedelta(minutes=9 * i))
    for i in range(1, 7):
        ter1 += device_attempts("K241107C%04d" % i, "L24110703", "E3840D11",
                                kst("20241107083000") + dt.timedelta(minutes=13 * i))
    for i in range(1, 6):
        ter2 += device_attempts("K241107D%04d" % i, "L24110704", "E7680D20",
                                kst("20241107190000") + dt.timedelta(minutes=12 * i))
    adv1.insert(0, Att("K241106Z0007", "L24110601", "C1T0N100", "FT2", "20241107023000", oper="권도윤"))  # night shift
    (d / "ADV_20241107_01.dat").write_bytes(adv_file("20241107", [a.adv() for a in adv1], create_time="235810"))
    (d / "ADV_20241107_02.dat").write_bytes(adv_file("20241107", [a.adv() for a in adv2], create_time="235902"))
    lines1 = [a.ter(serial=("SN-" + a.serial) if k % 3 == 0 else None, tester="TER-11")
              for k, a in enumerate(ter1)]
    (d / "TER_20241107_01.csv").write_bytes(ter_file(lines1, bom=True, eof="auto"))
    lines2 = [a.ter(tester="TER-12") for a in ter2]
    (d / "TER_20241107_02.csv").write_bytes(ter_file(lines2, bom=False, eof=None, eol="\n"))


if __name__ == "__main__":
    master()
    samples()
    print("written", OUT)
