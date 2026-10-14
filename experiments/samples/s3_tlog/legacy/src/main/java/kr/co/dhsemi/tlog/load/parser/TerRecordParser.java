package kr.co.dhsemi.tlog.load.parser;

import java.math.BigDecimal;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.TimeZone;

import org.apache.commons.lang.StringUtils;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.common.TlogRecordException;
import kr.co.dhsemi.tlog.vo.TestResultVO;

/**
 * TER 장비 로그 파서 (CSV, UTF-8)
 *
 * <pre>
 * 2016.11 leedw  최초작성 (AdvRecordParser 참고)
 * 2017.01 leedw  SN 접두어, 따옴표 필드 대응
 * </pre>
 *
 * 컬럼 : SERIAL,LOT,PRODUCT,STEP,START_UTC,END_UTC,TESTER,OPERATOR,RESULT,
 *        READ_MBPS,WRITE_MBPS,LAT_US,BAD_BLK,ECC_CNT,TEMP_F,FW
 */
public class TerRecordParser {

    public static final int COL_CNT = 16;

    /** TER 장비 시각은 UTC (ISO-8601) */
    private static final SimpleDateFormat UTC_FMT = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'");

    static {
        UTC_FMT.setTimeZone(TimeZone.getTimeZone("UTC"));
        UTC_FMT.setLenient(false);
    }

    public TestResultVO parse(String line, String fileNm) throws TlogRecordException {
        String[] col = CommonUtil.splitCsv(line);

        // 컬럼수 체크
        if (col.length != COL_CNT) {
            throw new TlogRecordException(Constants.ERR_LENGTH, "cols=" + col.length);
        }

        TestResultVO vo = new TestResultVO();
        vo.setVendorCd(Constants.VENDOR_TER);
        vo.setSrcFileNm(fileNm);

        // 시리얼
        String serial = CommonUtil.normSerial(col[0]);
        if (StringUtils.isEmpty(serial)) {
            throw new TlogRecordException(Constants.ERR_SERIAL);
        }
        vo.setSerial(serial);

        vo.setLotId(StringUtils.trim(col[1]));
        vo.setProdCd(StringUtils.trim(col[2]));

        // STEP
        String step = StringUtils.trim(col[3]);
        if (!AdvRecordParser.isValidStep(step)) {
            throw new TlogRecordException(Constants.ERR_STEP, step);
        }
        vo.setStepCd(step);

        // 시작/종료 일시 : UTC -> KST
        Date startDt = parseUtc(col[4]);
        Date endDt = parseUtc(col[5]);
        if (startDt == null || endDt == null) {
            throw new TlogRecordException(Constants.ERR_DATE);
        }
        if (endDt.before(startDt)) {
            throw new TlogRecordException(Constants.ERR_DATE_RANGE);
        }
        vo.setStartDtm(CommonUtil.formatDt14(startDt));
        vo.setEndDtm(CommonUtil.formatDt14(endDt));
        vo.setWorkDt(CommonUtil.getWorkDt(startDt));

        vo.setTesterId(StringUtils.trim(col[6]));
        // 작업자명 : DB 컬럼 10byte 초과분 절삭
        vo.setOperNm(CommonUtil.cutByte(StringUtils.trim(col[7]), 10, Constants.ENC_DB));

        // 결과
        String rslt = StringUtils.trim(col[8]);
        if ("PASS".equals(rslt)) {
            vo.setResultCd(Constants.RSLT_PASS);
        } else if ("FAIL".equals(rslt)) {
            vo.setResultCd(Constants.RSLT_FAIL);
        } else if ("ABORT".equals(rslt)) {
            vo.setResultCd(Constants.RSLT_ABORT);
        } else {
            throw new TlogRecordException(Constants.ERR_RESULT, rslt);
        }

        // 측정값
        try {
            vo.setReadMbps(new BigDecimal(StringUtils.trim(col[9])).setScale(1, BigDecimal.ROUND_HALF_UP));
            vo.setWriteMbps(new BigDecimal(StringUtils.trim(col[10])).setScale(1, BigDecimal.ROUND_HALF_UP));
            vo.setLatUs(Integer.valueOf(Integer.parseInt(StringUtils.trim(col[11]))));
            vo.setBadBlk(Integer.valueOf(Integer.parseInt(StringUtils.trim(col[12]))));
            vo.setEccCnt(Integer.valueOf(Integer.parseInt(StringUtils.trim(col[13]))));
            // 화씨 -> 섭씨
            vo.setMaxTempC(Integer.valueOf(CommonUtil.fahrenheitToCelsius(new BigDecimal(StringUtils.trim(col[14])))));
        } catch (NumberFormatException e) {
            throw new TlogRecordException(Constants.ERR_NUMBER, e.getMessage());
        }

        vo.setFwVer(StringUtils.trim(col[15]));
        return vo;
    }

    private Date parseUtc(String str) {
        String s = StringUtils.trim(str);
        if (s == null || !s.matches("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z")) {
            return null;
        }
        try {
            Date d = UTC_FMT.parse(s);
            // d = new Date(d.getTime() + 9 * 60 * 60 * 1000L);   // 2016.12 +9h 보정 제거 (이중 보정 이슈)
            return d;
        } catch (ParseException e) {
            return null;
        }
    }
}
