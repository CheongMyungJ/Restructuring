package kr.co.dhsemi.tlog.common;

import java.io.Closeable;
import java.io.File;
import java.io.UnsupportedEncodingException;
import java.math.BigDecimal;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;

import org.apache.commons.lang.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 공통 유틸리티
 *
 * <pre>
 * 2015.08 kimjh  최초작성 (날짜/문자열)
 * 2016.03 parksy byte 단위 자르기/패딩 추가 (MES 리포트)
 * 2016.11 leedw  CSV split, BOM 처리 추가 (TER 장비 도입)
 * 2017.02 leedw  파일 이동 공통화
 * </pre>
 */
public class CommonUtil {

    private static final Logger logger = LoggerFactory.getLogger(CommonUtil.class);

    public static final SimpleDateFormat DT14_FMT = new SimpleDateFormat("yyyyMMddHHmmss");
    public static final SimpleDateFormat YMD_FMT = new SimpleDateFormat("yyyyMMdd");
    public static final SimpleDateFormat LOG_FMT = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

    static {
        DT14_FMT.setLenient(false);
        YMD_FMT.setLenient(false);
    }

    /** 근무조 기준 시각 (06시) */
    private static final int SHIFT_START_HOUR = 6;

    private CommonUtil() {
    }

    /* ==================================================================
     * 환경
     * ================================================================== */

    public static String getTlogHome() {
        String home = System.getenv("TLOG_HOME");
        if (home == null || home.trim().length() == 0) {
            // 구 서버 경로
            home = "/app/tlog/data";
        }
        return home;
    }

    public static File getDir(String sub) {
        return new File(getTlogHome(), sub);
    }

    public static String getProperty(String key, String def) {
        String val = System.getProperty(key);
        if (val == null || val.trim().length() == 0) {
            return def;
        }
        return val.trim();
    }

    /* ==================================================================
     * 날짜
     * ================================================================== */

    /**
     * yyyyMMddHHmmss 문자열을 Date 로 변환 (오류시 null)
     */
    public static Date parseDt14(String str) {
        if (str == null || str.length() != 14 || !StringUtils.isNumeric(str)) {
            return null;
        }
        try {
            return DT14_FMT.parse(str);
        } catch (ParseException e) {
            return null;
        }
    }

    public static String formatDt14(Date dt) {
        if (dt == null) {
            return null;
        }
        return DT14_FMT.format(dt);
    }

    public static boolean isValidYmd(String ymd) {
        if (ymd == null || ymd.length() != 8 || !StringUtils.isNumeric(ymd)) {
            return false;
        }
        try {
            YMD_FMT.parse(ymd);
            return true;
        } catch (ParseException e) {
            return false;
        }
    }

    /**
     * 근무일자 산출.
     * 근무조는 06시 시작이므로 06시 이전 시작건은 전일 근무조(야간)로 본다.
     */
    public static String getWorkDt(Date startDt) {
        Calendar cal = Calendar.getInstance();
        cal.setTime(startDt);
        if (cal.get(Calendar.HOUR_OF_DAY) < SHIFT_START_HOUR) {
            cal.add(Calendar.DATE, -1);
        }
        return YMD_FMT.format(cal.getTime());
    }

    /**
     * yyyyMMdd 에 일수 더하기
     */
    public static String addDays(String ymd, int days) {
        try {
            Calendar cal = Calendar.getInstance();
            cal.setTime(YMD_FMT.parse(ymd));
            cal.add(Calendar.DATE, days);
            return YMD_FMT.format(cal.getTime());
        } catch (ParseException e) {
            logger.warn("addDays 실패 : " + ymd);
            return ymd;
        }
    }

    public static String getToday() {
        return YMD_FMT.format(new Date());
    }

    public static String getNow() {
        return LOG_FMT.format(new Date());
    }

    /* ==================================================================
     * 문자열
     * ================================================================== */

    public static String nvl(String str, String def) {
        if (str == null) {
            return def;
        }
        return str;
    }

    public static boolean isEmpty(String str) {
        return str == null || str.trim().length() == 0;
    }

    /**
     * 시리얼 정규화
     * - 공백제거, 대문자
     * - TER 장비는 앞에 SN 붙여서 보내는 경우 있음 -> 제거
     * - 하이픈 제거
     */
    public static String normSerial(String serial) {
        if (serial == null) {
            return "";
        }
        String s = serial.trim().toUpperCase();
        if (s.startsWith("SN")) {
            s = s.substring(2);
        }
        s = StringUtils.remove(s, '-');
        return s;
    }

    /**
     * CSV 한 줄 분리 (쌍따옴표 처리)
     */
    public static String[] splitCsv(String line) {
        List<String> list = new ArrayList<String>();
        if (line == null) {
            return new String[0];
        }
        StringBuffer sb = new StringBuffer();
        boolean inQuote = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (inQuote) {
                if (c == '"') {
                    if (i + 1 < line.length() && line.charAt(i + 1) == '"') {
                        sb.append('"');
                        i++;
                    } else {
                        inQuote = false;
                    }
                } else {
                    sb.append(c);
                }
            } else {
                if (c == '"') {
                    inQuote = true;
                } else if (c == ',') {
                    list.add(sb.toString());
                    sb.setLength(0);
                } else {
                    sb.append(c);
                }
            }
        }
        list.add(sb.toString());
        return list.toArray(new String[list.size()]);
    }

    /**
     * UTF-8 BOM 제거
     */
    public static String stripBom(String str) {
        if (str != null && str.length() > 0 && str.charAt(0) == '﻿') {
            return str.substring(1);
        }
        return str;
    }

    public static int getByteLength(String str, String enc) {
        if (str == null) {
            return 0;
        }
        try {
            return str.getBytes(enc).length;
        } catch (UnsupportedEncodingException e) {
            return str.length();
        }
    }

    /**
     * byte 배열에서 문자열 추출 (고정길이 레코드용)
     */
    public static String substrByte(byte[] buf, int offset, int len, String enc) {
        try {
            return new String(buf, offset, len, enc);
        } catch (UnsupportedEncodingException e) {
            return new String(buf, offset, len);
        }
    }

    /**
     * byte 길이 기준 자르기 (한글 깨짐 방지 - 2byte 문자 중간에서 자르지 않음)
     */
    public static String cutByte(String str, int maxByte, String enc) {
        if (str == null) {
            return "";
        }
        if (getByteLength(str, enc) <= maxByte) {
            return str;
        }
        StringBuffer sb = new StringBuffer();
        int len = 0;
        for (int i = 0; i < str.length(); i++) {
            String ch = str.substring(i, i + 1);
            int chLen = getByteLength(ch, enc);
            if (len + chLen > maxByte) {
                break;
            }
            sb.append(ch);
            len += chLen;
        }
        return sb.toString();
    }

    /**
     * byte 길이 기준 오른쪽 공백 패딩 (초과시 자름)
     */
    public static String rpadByte(String str, int len, String enc) {
        String s = cutByte(nvl(str, ""), len, enc);
        StringBuffer sb = new StringBuffer(s);
        int cur = getByteLength(s, enc);
        while (cur < len) {
            sb.append(' ');
            cur++;
        }
        return sb.toString();
    }

    /**
     * 숫자 0 패딩
     */
    public static String lpadZero(long num, int len) {
        return StringUtils.leftPad(String.valueOf(num), len, '0');
    }

    /* ==================================================================
     * 숫자
     * ================================================================== */

    /**
     * 화씨 -> 섭씨 변환 (소수 첫째자리에서 반올림하여 정수)
     */
    public static int fahrenheitToCelsius(BigDecimal f) {
        BigDecimal c = f.subtract(new BigDecimal("32"))
                        .multiply(new BigDecimal("5"))
                        .divide(new BigDecimal("9"), 0, BigDecimal.ROUND_HALF_UP);
        return c.intValue();
    }

    public static int toInt(String str, int def) {
        try {
            return Integer.parseInt(str.trim());
        } catch (Exception e) {
            return def;
        }
    }

    /* ==================================================================
     * 파일
     * ================================================================== */

    /**
     * 파일 이동 (대상 디렉토리 없으면 생성, 동일 파일 있으면 덮어씀)
     */
    public static boolean moveFile(File src, File destDir) {
        try {
            if (!destDir.exists()) {
                destDir.mkdirs();
            }
            File dest = new File(destDir, src.getName());
            if (dest.exists()) {
                dest.delete();
            }
            return src.renameTo(dest);
        } catch (Exception e) {
            logger.error("파일 이동 실패 : " + src.getAbsolutePath(), e);
            return false;
        }
    }

    public static void closeQuietly(Closeable c) {
        if (c != null) {
            try {
                c.close();
            } catch (Exception e) {
                // ignore
            }
        }
    }

//    /**
//     * 구 MES 연계용 날짜 포맷 (yyyy/MM/dd) - 2016.11 사용안함
//     */
//    public static String toMesDate(String ymd) {
//        return ymd.substring(0, 4) + "/" + ymd.substring(4, 6) + "/" + ymd.substring(6, 8);
//    }
}
