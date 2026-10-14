package kr.co.dhsemi.tlog.load.parser;

import java.io.UnsupportedEncodingException;
import java.math.BigDecimal;
import java.util.Date;

import org.apache.commons.lang.StringUtils;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.common.TlogRecordException;
import kr.co.dhsemi.tlog.vo.TestResultVO;

/**
 * ADV 장비 로그 파서 (고정길이 140 byte, MS949)
 *
 * <pre>
 * 2015.09 kimjh  최초작성
 * 2016.06 kimjh  레이아웃 V2 (FW버전 8자리, filler 10) - 구 레이아웃은 AdvParserV1 참고
 * </pre>
 */
public class AdvRecordParser {

    /** 레코드 길이 (byte) */
    public static final int REC_LEN = 140;

    private static final String ENC = Constants.ENC_ADV;

    public TestResultVO parse(String line, String fileNm) throws TlogRecordException {
        byte[] b;
        try {
            b = line.getBytes(ENC);
        } catch (UnsupportedEncodingException e) {
            throw new TlogRecordException(Constants.ERR_LENGTH, e.getMessage());
        }

        // 길이 체크 (byte 기준)
        if (b.length != REC_LEN || line.charAt(0) != 'D') {
            throw new TlogRecordException(Constants.ERR_LENGTH, "len=" + b.length);
        }

        TestResultVO vo = new TestResultVO();
        vo.setVendorCd(Constants.VENDOR_ADV);
        vo.setSrcFileNm(fileNm);

        // 시리얼
        String serial = CommonUtil.normSerial(CommonUtil.substrByte(b, 1, 16, ENC));
        if (StringUtils.isEmpty(serial)) {
            throw new TlogRecordException(Constants.ERR_SERIAL);
        }
        vo.setSerial(serial);

        vo.setLotId(StringUtils.trim(CommonUtil.substrByte(b, 17, 10, ENC)));
        vo.setProdCd(StringUtils.trim(CommonUtil.substrByte(b, 27, 8, ENC)));

        // STEP
        String step = StringUtils.trim(CommonUtil.substrByte(b, 35, 4, ENC));
        if (!isValidStep(step)) {
            throw new TlogRecordException(Constants.ERR_STEP, step);
        }
        vo.setStepCd(step);

        // 시작/종료 일시 (현지 시각)
        Date startDt = CommonUtil.parseDt14(CommonUtil.substrByte(b, 39, 14, ENC));
        Date endDt = CommonUtil.parseDt14(CommonUtil.substrByte(b, 53, 14, ENC));
        if (startDt == null || endDt == null) {
            throw new TlogRecordException(Constants.ERR_DATE);
        }
        if (endDt.before(startDt)) {
            throw new TlogRecordException(Constants.ERR_DATE_RANGE);
        }
        vo.setStartDtm(CommonUtil.formatDt14(startDt));
        vo.setEndDtm(CommonUtil.formatDt14(endDt));
        vo.setWorkDt(CommonUtil.getWorkDt(startDt));

        vo.setTesterId(StringUtils.trim(CommonUtil.substrByte(b, 67, 8, ENC)));
        vo.setOperNm(StringUtils.trim(CommonUtil.substrByte(b, 75, 10, ENC)));

        // 결과
        String rslt = StringUtils.trim(CommonUtil.substrByte(b, 85, 2, ENC));
        if (!Constants.RSLT_PASS.equals(rslt) && !Constants.RSLT_FAIL.equals(rslt)
                && !Constants.RSLT_ABORT.equals(rslt)) {
            throw new TlogRecordException(Constants.ERR_RESULT, rslt);
        }
        vo.setResultCd(rslt);

        // 측정값
        String read = CommonUtil.substrByte(b, 87, 6, ENC);
        String write = CommonUtil.substrByte(b, 93, 6, ENC);
        String lat = CommonUtil.substrByte(b, 99, 6, ENC);
        String bad = CommonUtil.substrByte(b, 105, 5, ENC);
        String ecc = CommonUtil.substrByte(b, 110, 8, ENC);
        String temp = CommonUtil.substrByte(b, 118, 4, ENC);
        if (!StringUtils.isNumeric(read) || !StringUtils.isNumeric(write) || !StringUtils.isNumeric(lat)
                || !StringUtils.isNumeric(bad) || !StringUtils.isNumeric(ecc)) {
            throw new TlogRecordException(Constants.ERR_NUMBER);
        }
        char sign = temp.charAt(0);
        if ((sign != '+' && sign != '-') || !StringUtils.isNumeric(temp.substring(1))) {
            throw new TlogRecordException(Constants.ERR_NUMBER, temp);
        }
        // 소수 1자리 내포 (005123 -> 512.3)
        vo.setReadMbps(new BigDecimal(read).movePointLeft(1));
        vo.setWriteMbps(new BigDecimal(write).movePointLeft(1));
        vo.setLatUs(Integer.valueOf(lat));
        vo.setBadBlk(Integer.valueOf(bad));
        vo.setEccCnt(Integer.valueOf(ecc));
        int t = Integer.parseInt(temp.substring(1));
        if (sign == '-') {
            t = -t;
        }
        vo.setMaxTempC(Integer.valueOf(t));

        vo.setFwVer(StringUtils.trim(CommonUtil.substrByte(b, 122, 8, ENC)));
        // 130 ~ 139 filler
        return vo;
    }

    public static boolean isValidStep(String step) {
        for (int i = 0; i < Constants.STEP_LIST.length; i++) {
            if (Constants.STEP_LIST[i].equals(step)) {
                return true;
            }
        }
        return false;
    }
}
